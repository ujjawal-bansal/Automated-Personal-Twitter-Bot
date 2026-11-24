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

from agent.learning import TZ

ROOT = Path(__file__).resolve().parents[1]


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
        ref = self.git('ls-remote', '--exit-code', 'origin', self.ref, check=False)
        if ref.returncode == 2:
            posts = json.loads((ROOT / 'data/history.json').read_text())['posts']
            return None, dict(posts=posts, slots={}, events=[])
        if ref.returncode:
            raise RuntimeError('state_remote_unavailable')
        head = ref.stdout.split()[0].decode()
        self.git('fetch', '--quiet', '--no-tags', 'origin', head)
        encrypted = self.git('show', head + ':ledger.enc').stdout
        return head, json.loads(zlib.decompress(self.cipher.decrypt(encrypted)))

    def update(self, change):
        # A normal push accepts only a fast-forward. Competing writers must
        # reload and re-evaluate their transition before they can win.
        for _ in range(4):
            parent, state = self.load()
            if not change(state):
                return False
            encoded = json.dumps(state, ensure_ascii=False, separators=(',', ':')).encode()
            encrypted = self.cipher.encrypt(zlib.compress(encoded))
            blob = self.git('hash-object', '-w', '--stdin', data=encrypted).stdout.strip()
            tree = self.git('mktree', data=b'100644 blob ' + blob + b'\tledger.enc\n').stdout.strip().decode()
            parents = ['-p', parent] if parent else []
            head = self.git('commit-tree', tree, *parents, '-m', 'Update posting state').stdout.strip().decode()
            push = self.git('push', 'origin', head + ':' + self.ref, check=False)
            if push.returncode == 0:
                return True
            # Only a confirmed competing update is retryable. Ambiguous writes
            # fail closed; an unacknowledged intent cannot cause a second send.
            remote = self.git('ls-remote', 'origin', self.ref).stdout.split()
            if not remote or remote[0].decode() in (parent, head):
                raise RuntimeError('state_write_unconfirmed')
        raise RuntimeError('state_contention')

    def slot(self, day):
        return self.load()[1]['slots'].get(str(day))

    def claim(self, day, owner):
        def reserve(state):
            now = datetime.now(TZ)
            slot = state['slots'].get(str(day))
            if slot and (slot['state'] != 'working' or slot['attempts'] >= 3
                         or datetime.fromisoformat(slot['lease_until']) > now):
                return False
            if any(datetime.fromisoformat(p['time']).astimezone(TZ).date() == day for p in state['posts']):
                return False
            state['slots'][str(day)] = dict(day=str(day), owner=owner, state='working',
                                            attempts=slot['attempts'] + 1 if slot else 1,
                                            lease_until=(now + timedelta(minutes=12)).isoformat())
            return True
        return self.update(reserve)

    def intent(self, day, owner, draft):
        def prepare(state):
            slot = state['slots'].get(str(day))
            now = datetime.now(TZ)
            if not slot or slot['owner'] != owner or slot['state'] != 'working':
                return False
            if now.date() != day or datetime.fromisoformat(slot['lease_until']) <= now:
                return False
            slot.update(state='sending', draft=draft, intent_at=now.isoformat())
            return True
        return self.update(prepare)

    def finish(self, day, tweet_id):
        def acknowledge(state):
            slot = state['slots'][str(day)]
            if slot['state'] != 'sending':
                return False
            state['posts'].append(dict(slot.pop('draft'), id=str(tweet_id), time=slot['intent_at'], metrics=None))
            slot.update(state='published', tweet_id=str(tweet_id))
            return True
        self.update(acknowledge)

    def failure(self, day, owner, kind, from_state):
        def release(state):
            slot = state['slots'].get(str(day))
            if not slot or slot['owner'] != owner or slot['state'] != from_state:
                return False
            slot.update(state='skipped' if slot['attempts'] >= 3 else 'working', error=kind,
                        lease_until=(datetime.now(TZ) + timedelta(minutes=30)).isoformat())
            return True
        self.update(release)

    def event(self, day, kind, detail):
        def append(state):
            state['events'].append(dict(day=str(day), kind=kind, detail=detail))
            state['events'] = state['events'][-100:]
            return True
        self.update(append)

    def memory(self):
        return sorted(self.load()[1]['posts'], key=lambda p: datetime.fromisoformat(p['time']), reverse=True)

    def candidates(self):
        return [e['detail'] for e in reversed(self.load()[1]['events']) if e['kind'] == 'evaluation'][:24]

    def pending(self):
        cutoff = datetime.now(TZ) - timedelta(days=7)
        return [s for s in self.load()[1]['slots'].values() if s['state'] == 'sending'
                and datetime.fromisoformat(s['intent_at']) > cutoff]

    def save_metrics(self, tweet_id, metrics):
        def save(state):
            for post in state['posts']:
                if post['id'] == tweet_id and post.get('metrics') is None:
                    post['metrics'] = metrics
                    return True
            return False
        self.update(save)
