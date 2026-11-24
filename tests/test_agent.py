import os
import subprocess
import tempfile
from pathlib import Path
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta
from unittest.mock import Mock,patch

from agent import daily,editorial,learning,research
from agent.publisher import Rejected
from agent.store import Ledger

NOW=datetime(2026,11,24,17,tzinfo=learning.TZ)
DRAFT=dict(text='A city can tell the time by its loudspeakers.',topic='public space',
           argument='sound as a clock',format='observation',kind='evergreen')


class Pipeline(unittest.TestCase):
    def setUp(self):
        self.store=Mock()
        self.store.pending.return_value=[]
        self.store.slot.return_value=None
        self.store.memory.return_value=[]
        self.pub=Mock()
        self.pub.send.return_value='123'
        self.gen=Mock(return_value=DRAFT)

    def run_agent(self):
        return daily.run(self.store,self.pub,self.gen,lambda:NOW,force=True)

    def test_acknowledged(self):
        self.assertEqual(self.run_agent(),'published')
        self.store.finish.assert_called_once_with(NOW.date(),'123')

    def test_ambiguous_send_holds_slot(self):
        self.pub.send.side_effect=TimeoutError
        with self.assertRaises(TimeoutError):
            self.run_agent()
        self.store.failure.assert_not_called()
        self.store.pending.return_value=[{'day':str(NOW.date()),'draft':DRAFT}]
        self.store.slot.return_value={'state':'sending'}
        self.pub.reconcile.return_value=None
        self.assertEqual(self.run_agent(),'sending')
        self.pub.reconcile.return_value='123'
        self.run_agent()
        self.store.finish.assert_called_once()
        self.pub.send.assert_called_once()

    def test_active_worker_or_already_published(self):
        self.store.claim.return_value=False
        self.assertEqual(self.run_agent(),'occupied')
        self.store.slot.return_value={'state':'published'}
        self.assertEqual(self.run_agent(),'published')
        self.gen.assert_not_called()
        self.pub.send.assert_not_called()

    def test_explicit_rejection(self):
        self.pub.send.side_effect=Rejected('x_rejected_429')
        with self.assertRaises(Rejected):
            self.run_agent()
        self.assertEqual(self.store.failure.call_args.args[-1],'sending')

    def test_lost_lease_and_db_down(self):
        self.store.intent.return_value=False
        self.assertEqual(self.run_agent(),'lost_lease')
        self.store.intent.side_effect=RuntimeError('ledger_unavailable')
        with self.assertRaises(RuntimeError):
            self.run_agent()
        self.pub.send.assert_not_called()

    def test_midnight(self):
        with self.assertRaises(ValueError):
            daily.run(self.store,self.pub,self.gen,Mock(side_effect=[NOW,NOW+timedelta(days=1)]),True)
        self.pub.send.assert_not_called()

    def test_no_approval_or_publication_in_shadow(self):
        with patch('sys.argv',['bot.py','--dry-run']),patch.object(daily,'draft',return_value={'quality':15,'text':'ok'}),patch.object(daily,'Ledger') as ledger,patch('agent.publisher.Publisher') as publisher:
            daily.main()
            ledger.assert_not_called()
            publisher.assert_not_called()


class Editorial(unittest.TestCase):
    def test_sources_and_freshness(self):
        body=b'<rss><channel><item><title>City study</title><link>https://bbc.com/a</link><pubDate>Tue, 24 Nov 2026 03:00:00 GMT</pubDate></item></channel></rss>'
        self.assertEqual(len(research.parse_feed(body,'BBC','bbc.co.uk',NOW)),1)
        self.assertFalse(research.parse_feed(body,'BBC','bbc.co.uk',NOW+timedelta(days=6)))
        self.assertFalse(research.parse_feed(body.replace(b'bbc.com',b'evilbbc.com'),'BBC','bbc.co.uk',NOW))

    def test_relevance_and_verification(self):
        i=dict(topic='air',argument='why measurement matters',format='question',kind='timely',
               source_ids=[0,1],fit=5,insight=4,freshness=4,evidence=['air measurements']*2)
        s=[dict(source=k,headline='air measurements',summary='') for k in ['A','B']]
        self.assertEqual(len(editorial.ranked_topics({'ideas':[i]},s,['sport'])),1)
        for refs,trends in [(s,[]),([s[0],s[0]],['sport'])]:
            self.assertFalse(editorial.ranked_topics({'ideas':[i]},refs,trends))
        i['evidence'][0]='fabricated quote'
        self.assertFalse(editorial.ranked_topics({'ideas':[i]},s,['sport']))

    def test_semantic_veto_and_quality(self):
        model=Mock()
        idea={**DRAFT,'fit':5,'insight':5,'freshness':2,'source_ids':[]}
        review=dict(index=0,voice=5,insight=5,originality=5,verified=True,personal_supported=True,
                    distinct=False,policy_ok=True)
        def attempt():
            model.ask.side_effect=[{'ideas':[idea]},{'texts':[DRAFT['text']]},{'reviews':[review]}]
            return editorial.choose(model,[],[],[],[],{},Mock())
        with self.assertRaises(ValueError):
            attempt()
        review['distinct']=True
        self.assertEqual(attempt()['quality'],15)
        self.assertFalse(editorial.acceptable_text(DRAFT['text'],[DRAFT]))

    def test_learning_and_schedule(self):
        row={**DRAFT,'time':NOW.isoformat(),'metrics':{'impression_count':100,'like_count':3,'reply_count':0,'retweet_count':1}}
        self.assertFalse(learning.preferences([row]*5))
        self.assertEqual(learning.preferences([row]*6)['format:observation'],.04)
        t=daily.target(NOW.date(),{},'seed')
        self.assertEqual(t,daily.target(NOW.date(),{},'seed'))
        self.assertTrue(12<=t.hour<16)
        self.assertEqual(t.utcoffset(),timedelta(hours=5,minutes=30))


class GitLedger(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name) / 'checkout'
        remote = Path(tmp.name) / 'origin.git'
        subprocess.run(['git', 'init', '--bare', '-q', remote], check=True)
        subprocess.run(['git', 'init', '-q', self.repo], check=True)
        subprocess.run(['git', '-C', self.repo, 'remote', 'add', 'origin', remote], check=True)
        key = patch.dict(os.environ, AGENT_STATE_KEY='integration-test-key')
        key.start()
        self.addCleanup(key.stop)
        self.store = Ledger('42', self.repo)

    def test_concurrent_lease_and_recovery(self):
        store = self.store
        day=datetime.now(learning.TZ).date()
        owners=[str(i) for i in range(8)]
        with ThreadPoolExecutor(8) as pool:
            wins=list(pool.map(lambda o:store.claim(day,o),owners))
        self.assertEqual(sum(wins),1)
        owner=owners[wins.index(True)]
        self.assertFalse(store.intent(day,'other',DRAFT))
        self.assertTrue(store.intent(day,owner,DRAFT))
        restart=Ledger('42', self.repo)
        self.assertEqual(restart.pending()[0]['draft'],DRAFT)
        restart.finish(day,'1234')
        restart.save_metrics('1234', {'like_count': 7})
        self.assertEqual(restart.memory()[0]['metrics'], {'like_count': 7})
        self.assertFalse(restart.claim(day,'new'))
        self.assertEqual(restart.slot(day)['tweet_id'],'1234')


    def test_wrong_key_fails_closed(self):
        day = datetime.now(learning.TZ).date()
        self.assertTrue(self.store.claim(day, 'owner'))
        self.assertTrue(self.store.intent(day, 'owner', DRAFT))
        raw = self.store.git('show', self.store.ref.replace('refs/heads/', 'refs/remotes/origin/') + ':ledger.enc').stdout
        self.assertNotIn(DRAFT['text'].encode(), raw)
        from cryptography.fernet import InvalidToken
        with patch.dict(os.environ, AGENT_STATE_KEY='wrong-key'), self.assertRaises(InvalidToken):
            Ledger('42', self.repo).claim(day, 'new')


class Transport(unittest.TestCase):
    def test_reconciliation_paginates_and_requires_an_exact_match(self):
        from agent.publisher import Publisher
        pub=Publisher.__new__(Publisher)
        pub.account='123'
        pub.read=Mock(side_effect=[{'data':[{'text':'different','id':'1'}],'meta':{'next_token':'next'}},
                                  {'data':[{'text':DRAFT['text'],'id':'2'}]}])
        self.assertEqual(pub.reconcile({'intent_at':NOW.isoformat(),'draft':DRAFT}),'2')
        self.assertEqual(pub.read.call_args.args[1]['pagination_token'],'next')

    def test_mismatched_identity(self):
        from agent.publisher import Publisher
        pub=Publisher.__new__(Publisher)
        pub.account='123'
        pub.read=Mock(return_value={'data':{'id':'456'}})
        with self.assertRaisesRegex(ValueError,'identity_mismatch'):
            pub.verify()

    def test_missing_metrics_stay_unknown(self):
        store=Mock()
        store.memory.return_value=[{**DRAFT,'time':(NOW-timedelta(days=3)).isoformat(),'id':'123'}]
        pub=Mock()
        pub.read.return_value={'data':[{'id':'123','public_metrics':{'like_count':0}}]}
        learning.collect(store,pub,NOW)
        store.save_metrics.assert_called_once_with('123', {'like_count':0})
