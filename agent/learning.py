from collections import defaultdict
from datetime import datetime,timedelta
from statistics import median
from zoneinfo import ZoneInfo

TZ=ZoneInfo('Asia/Kolkata')


def collect(store,x,now):
    pending=[p['id'] for p in store.memory() if p.get('format') and p.get('metrics') is None
             and now-datetime.fromisoformat(p['time'])>=timedelta(hours=48)][:50]
    if not pending:
        return
    for p in x.read('tweets',{'ids':','.join(pending),'tweet.fields':'public_metrics'}).get('data',[]):
        m=p.get('public_metrics')
        if isinstance(m,dict) and m:
            store.save_metrics(p['id'], m)


def preferences(memory):
    groups=defaultdict(list)
    for p in memory:
        m=p.get('metrics') or {}
        if not p.get('format') or not m.get('impression_count'):
            continue
        fields=('like_count','reply_count','retweet_count')
        if any(m.get(k) is None for k in fields):
            continue
        rate=sum(m[k] for k in fields)/m['impression_count']
        hour=datetime.fromisoformat(p['time']).astimezone(TZ).hour
        for label in ('format:'+p['format'],'hour:'+str(hour),'topic:'+p['topic']):
            groups[label].append(rate)
    return {key:round(median(values),4) for key,values in groups.items() if len(values)>=6}
