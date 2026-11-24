"""Keep the posting ledger encrypted on a dedicated Git branch."""
import base64
import hashlib
import json
import os
import subprocess
import zlib
from datetime import datetime, timedelta
from pathlib import Path

from cryptography.fernet import Fernet

from zoneinfo import ZoneInfo

TZ = ZoneInfo('Asia/Kolkata')

ROOT = Path(__file__).resolve().parents[1]


def fingerprint(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def compact(state, day):
    """Read the previous ledger format without dropping today's send intent."""
    if 'topics' in state:
        topics = state['topics']
        slot = state['slot']
    else:
        posts = sorted(state['posts'], key=lambda p: datetime.fromisoformat(p['time']))
        topics = [p['topic'] for p in posts if p.get('topic')]
        slot = state['slots'].get(day)
        if slot is None and posts:
            last = posts[-1]
            if datetime.fromisoformat(last['time']).astimezone(TZ).date().isoformat() == day:
                slot = dict(day=day, state='published', tweet_id=last['id'])
    if slot and slot['day'] != day:
        slot = None
    if slot and 'draft' in slot:
        slot = slot.copy()
        draft = slot.pop('draft')
        if slot['state'] == 'sending':
            slot.update(topic=draft['topic'], digest=fingerprint(draft['text']))
    result = dict(slot=slot, topics=topics[-10:])
    if state.get('feedback'):
        result['feedback'] = state['feedback']
    return result


class Ledger:
    def __init__(self, account, repo=ROOT):
        if not str(account).isdecimal():
            raise ValueError('invalid_account')
        self.repo = repo
        self.ref = 'refs/heads/agent-state-' + str(account)
        secret = os.getenv('AGENT_STATE_KEY') or os.environ['X_API_SECRET']
        if not secret:
            raise ValueError('missing_state_key')
        key = hashlib.sha256(('x-agent-state-v1/' + str(account) + '/' + secret).encode()).digest()
        self.cipher = Fernet(base64.urlsafe_b64encode(key))

    def git(self, *args, data=None, check=True):
        cmd = ['git', '-c', 'user.name=X agent', '-c', 'user.email=agent@localhost', *args]
        result = subprocess.run(cmd, cwd=self.repo, input=data, capture_output=True,
                                env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'}, timeout=45)
        if check and result.returncode:
            raise RuntimeError('state_git_unavailable')
        return result

    def load(self):
        day = datetime.now(TZ).date().isoformat()
        ref = self.git('ls-remote', '--exit-code', 'origin', self.ref, check=False)
        if ref.returncode == 2:
            posts = json.loads((ROOT / 'data/history.json').read_text())['posts']
            return None, compact(dict(posts=posts, slots={}), day)
        if ref.returncode:
            raise RuntimeError('state_remote_unavailable')
        head = ref.stdout.split()[0].decode()
        self.git('fetch', '--quiet', '--no-tags', 'origin', head)
        encrypted = self.git('show', head + ':ledger.enc').stdout
        return head, compact(json.loads(zlib.decompress(self.cipher.decrypt(encrypted))), day)

    def update(self, change):
        # A lease compares the exact previously observed ref. Competing writers must
        # reload and re-evaluate their transition before they can win.
        for _ in range(4):
            parent, state = self.load()
            if not change(state):
                return False
            encoded = json.dumps(state, ensure_ascii=False, separators=(',', ':')).encode()
            encrypted = self.cipher.encrypt(zlib.compress(encoded))
            blob = self.git('hash-object', '-w', '--stdin', data=encrypted).stdout.strip()
            tree = self.git('mktree', data=b'100644 blob ' + blob + b'\tledger.enc\n').stdout.strip().decode()
            head = self.git('commit-tree', tree, '-m', 'Update posting state').stdout.strip().decode()
            push = self.git('push', f'--force-with-lease={self.ref}:{parent or ''}',
                            'origin', head + ':' + self.ref, check=False)
            if push.returncode == 0:
                return True
            # Only a confirmed competing update is retryable. Ambiguous writes
            # fail closed; an unacknowledged intent cannot cause a second send.
            remote = self.git('ls-remote', 'origin', self.ref).stdout.split()
            if not remote or remote[0].decode() in (parent, head):
                raise RuntimeError('state_write_unconfirmed')
        raise RuntimeError('state_contention')

    def slot(self, day):
        slot = self.load()[1]['slot']
        return slot if slot and slot['day'] == str(day) else None

    def claim(self, day, owner):
        def reserve(state):
            now = datetime.now(TZ)
            slot = state['slot']
            if slot and (slot['state'] != 'working' or slot['attempts'] >= 3
                         or datetime.fromisoformat(slot['lease_until']) > now):
                return False
            if day != now.date():
                return False
            state['slot'] = dict(day=str(day), owner=owner, state='working',
                                            attempts=slot['attempts'] + 1 if slot else 1,
                                            lease_until=(now + timedelta(minutes=12)).isoformat())
            return True
        return self.update(reserve)

    def intent(self, day, owner, draft):
        def prepare(state):
            slot = state['slot']
            now = datetime.now(TZ)
            if not slot or slot['owner'] != owner or slot['state'] != 'working':
                return False
            if now.date() != day or datetime.fromisoformat(slot['lease_until']) <= now:
                return False
            slot.update(state='sending', topic=draft['topic'], digest=fingerprint(draft['text']),
                        intent_at=now.isoformat())
            return True
        return self.update(prepare)

    def finish(self, day, tweet_id):
        def acknowledge(state):
            slot = state['slot']
            if not slot or slot['day'] != str(day) or slot['state'] != 'sending':
                return False
            state['topics'] = (state['topics'] + [slot['topic']])[-10:]
            state['slot'] = dict(day=str(day), state='published', tweet_id=str(tweet_id))
            return True
        self.update(acknowledge)

    def failure(self, day, owner, kind, from_state):
        def release(state):
            slot = state['slot']
            if not slot or slot['owner'] != owner or slot['state'] != from_state:
                return False
            slot.update(state='skipped' if slot['attempts'] >= 3 else 'working', error=kind,
                        lease_until=(datetime.now(TZ) + timedelta(minutes=30)).isoformat())
            return True
        self.update(release)

    def memory(self):
        return [dict(topic=topic) for topic in reversed(self.load()[1]['topics'])]

    def pending(self):
        slot = self.load()[1]['slot']
        return [slot] if slot and slot['state'] == 'sending' else []

    def feedback(self):
        return self.load()[1].get('feedback', [])

    def set_feedback(self, subject, decision, note):
        subject, note = subject.strip(), note.strip()
        if not 0 < len(subject) <= 80 or not 0 < len(note) <= 400:
            raise ValueError('Use a subject of 1–80 characters and a note of 1–400 characters.')
        if decision not in ('approved', 'rejected', 'edited', 'updated'):
            raise ValueError('invalid_feedback_decision')

        def save(state):
            notes = [item for item in state.get('feedback', [])
                     if item['subject'].casefold() != subject.casefold()]
            if len(notes) >= 24:
                raise ValueError('There are 24 active notes. Replace or remove one first.')
            notes.append(dict(subject=subject, decision=decision, note=note,
                              date=datetime.now(TZ).date().isoformat()))
            state['feedback'] = notes
            return True
        return self.update(save)

    def forget_feedback(self, subject):
        def forget(state):
            current = state.get('feedback', [])
            kept = [item for item in current if item['subject'].casefold() != subject.strip().casefold()]
            if len(kept) == len(current):
                return False
            state['feedback'] = kept
            return True
        return self.update(forget)
