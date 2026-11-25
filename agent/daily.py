import argparse
import hashlib
import json
import os
import uuid
from datetime import datetime,time,timedelta

from agent.editorial import Model, ModelTemporarilyUnavailable, choose
from agent.research import discover
from agent.store import Ledger, TZ, compact


def clock():
    return datetime.now(TZ)


def log(event,**fields):
    print(json.dumps(dict(event=event,**fields)),flush=True)


def target(day,seed):
    start=int(os.getenv('POST_START_HOUR','12'))
    end=int(os.getenv('POST_END_HOUR','16'))
    if not 0<=start<end<=23:
        raise ValueError('invalid_window')
    bits=int.from_bytes(hashlib.sha256(f'{seed}:{day}'.encode()).digest()[:8],'big')
    hour=start+bits%(end-start)
    return datetime.combine(day,time(hour,(bits//97)%60),tzinfo=TZ)


def trend_signals():
    import requests
    from bot import x_bearer_token
    headers={'Authorization':'Bearer '+x_bearer_token()}
    names=[]
    for place in (23424848,1):
        try:
            r=requests.get(f'https://api.x.com/2/trends/by/woeid/{place}',headers=headers,
                           params={'max_trends':50},timeout=(4,10))
            r.raise_for_status()
            batch=[t['trend_name'] for t in r.json().get('data',[]) if t.get('trend_name')]
        except (requests.RequestException, ValueError):
            continue
        names.extend(batch)
    return list(dict.fromkeys(names))


def draft(store,day,memory,shadow=False):
    try:
        trends=trend_signals()
    except Exception:
        trends=[]
    feedback = store.feedback() if store else []
    return choose(Model(),discover(clock()),trends,memory,feedback)


def run(store,publisher,generate=draft,now=clock,force=False):
    from agent.publisher import Rejected
    instant=now()
    day=instant.date()
    for old in store.pending():
        ident=publisher.reconcile(old)
        if ident:
            store.finish(old['day'],ident)
            log('reconciled',day=old['day'])
    slot=store.slot(day)
    if slot and slot['state']!='working':
        return slot['state']
    memory=store.memory()
    if not force and instant<target(day,os.getenv('SCHEDULE_SEED','daily')):
        return 'early'
    if instant.hour==23 and instant.minute>=55:
        return 'day_closing'
    owner=uuid.uuid4().hex
    if not store.claim(day,owner):
        return 'occupied'
    try:
        publisher.verify()
        selected=generate(store,day,memory)
        media_id=publisher.attach(selected)
        current=now()
        if current.date()!=day or current>=datetime.combine(day,time(23,55),tzinfo=TZ):
            raise ValueError('day_closed')
        if not store.intent(day,owner,selected):
            return 'lost_lease'
    except ModelTemporarilyUnavailable:
        store.failure(day, owner, 'model_temporarily_unavailable', 'working')
        return 'generation_deferred'
    except Exception as exc:
        kind=str(exc) if isinstance(exc,ValueError) and str(exc) in ('quality_threshold','account_identity_mismatch','day_closed') else type(exc).__name__
        store.failure(day,owner,kind,'working')
        raise
    try:
        ident=publisher.send(selected['text'],media_id)
    except Rejected as exc:
        store.failure(day,owner,str(exc),'sending')
        raise
    store.finish(day,ident)
    return 'published'


def main():
    parser=argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--dry-run',action='store_true')
    mode.add_argument('--review', action='store_true')
    mode.add_argument('--preferences', action='store_true')
    parser.add_argument('--trending',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--force',action='store_true',help='bypass target time, retaining the daily limit')
    args=parser.parse_args()
    account=os.getenv('X_ACCOUNT_ID','1703345238167924736')
    if args.review or args.preferences:
        from agent.feedback import preferences, review
        if os.environ.get('GITHUB_ACTIONS'):
            raise ValueError('interactive_feedback_requires_local_terminal')
        store = Ledger(account)
        if args.preferences:
            preferences(store)
        else:
            review(store, draft(store, clock().date(), store.memory(), True))
        return
    if args.dry_run or os.getenv('DRY_RUN','').lower()=='true':
        if os.getenv('X_API_SECRET') or os.getenv('AGENT_STATE_KEY'):
            store = Ledger(account)
            memory = store.memory()
        else:
            from bot import HISTORY_FILE, load_json
            posts = load_json(HISTORY_FILE, {'posts': []})['posts']
            topics = compact(dict(posts=posts, slots={}), str(clock().date()))['topics']
            store = None
            memory = [dict(topic=t) for t in reversed(topics)]
        post = draft(store, clock().date(), memory, True)
        log('shadow_passed',quality=post['quality'])
        if not os.environ.get('GITHUB_ACTIONS'):
            print(post['text'])
        return
    if os.getenv('AGENT_ENABLED','').lower()!='true':
        log('disabled')
        return
    from agent.publisher import Publisher
    store=Ledger(account)
    pub=Publisher(account)
    if os.getenv('LEARN_ONLY','').lower()=='true':
        log('metrics_collection_disabled')
        return
    log(run(store,pub,force=args.force))
