import argparse
import hashlib
import json
import os
import uuid
from datetime import datetime,time,timedelta

from agent.editorial import Model,choose
from agent.learning import TZ,collect,preferences
from agent.research import discover
from agent.store import Ledger


def clock():
    return datetime.now(TZ)


def log(event,**fields):
    print(json.dumps(dict(event=event,**fields)),flush=True)


def target(day,strategy,seed):
    start=int(os.getenv('POST_START_HOUR','12'))
    end=int(os.getenv('POST_END_HOUR','16'))
    if not 0<=start<end<=23:
        raise ValueError('invalid_window')
    bits=int.from_bytes(hashlib.sha256(f'{seed}:{day}'.encode()).digest()[:8],'big')
    hour=start+bits%(end-start)
    eligible={int(k[5:]):v for k,v in strategy.items() if k.startswith('hour:') and start<=int(k[5:])<end}
    if len(eligible)>=2 and bits%4:
        hour=max(eligible,key=eligible.get)
    return datetime.combine(day,time(hour,(bits//97)%60),tzinfo=TZ)


def trend_exclusions():
    import requests
    from bot import x_bearer_token
    headers={'Authorization':'Bearer '+x_bearer_token()}
    names=[]
    for place in (23424848,1):
        r=requests.get(f'https://api.x.com/2/trends/by/woeid/{place}',headers=headers,
                       params={'max_trends':50},timeout=(4,10))
        r.raise_for_status()
        batch=[t['trend_name'] for t in r.json().get('data',[]) if t.get('trend_name')]
        if not batch:
            return []
        names.extend(batch)
    return list(dict.fromkeys(names))


def draft(store,day,memory,shadow=False):
    try:
        trends=trend_exclusions()
    except Exception:
        trends=[]
    record=(lambda kind,detail:None) if shadow else (lambda kind,detail:store.event(day,kind,detail))
    return choose(Model(),discover(clock()),trends,memory,
                  store.candidates() if store else [],preferences(memory),record)


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
    if not force and instant<target(day,preferences(memory),os.getenv('SCHEDULE_SEED','daily')):
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
    except Exception as exc:
        kind=str(exc) if isinstance(exc,ValueError) and str(exc) in ('quality_threshold','account_identity_mismatch','day_closed') else type(exc).__name__
        store.failure(day,owner,kind,'working')
        store.event(day,'failed_before_send',{'cause':kind})
        raise
    try:
        ident=publisher.send(selected['text'],media_id)
    except Rejected as exc:
        store.failure(day,owner,str(exc),'sending')
        store.event(day,'rejected',{'cause':str(exc)})
        raise
    except Exception:
        store.event(day,'uncertain',{})
        raise
    store.finish(day,ident)
    return 'published'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--trending',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--force',action='store_true',help='bypass target time, retaining the daily limit')
    args=parser.parse_args()
    account=os.getenv('X_ACCOUNT_ID','1703345238167924736')
    if args.dry_run or os.getenv('DRY_RUN','').lower()=='true':
        from bot import HISTORY_FILE,load_json
        memory=list(reversed(load_json(HISTORY_FILE,{'posts':[]})['posts']))
        # Only the local interactive preview may display the selected post.
        post=draft(None,clock().date(),memory,True)
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
        pub.verify()
        collect(store,pub,clock())
        return
    result=run(store,pub,force=args.force)
    log(result)
    if result=='published':
        try:
            collect(store,pub,clock())
        except Exception as exc:
            log('metrics_deferred',cause=type(exc).__name__)
