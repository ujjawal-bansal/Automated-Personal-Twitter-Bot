"""PostgreSQL ledger. SQL is static; values enter psql as quoted JSON data."""
import json
import os
import subprocess
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_slots (
 account text NOT NULL, day date NOT NULL, state text NOT NULL,
 owner text, lease_until timestamptz, attempts int NOT NULL DEFAULT 0,
 draft jsonb, intent_at timestamptz, tweet_id text, error text,
 PRIMARY KEY(account, day)
);
CREATE TABLE IF NOT EXISTS agent_memory (
 account text NOT NULL, tweet_id text NOT NULL, published timestamptz NOT NULL,
 item jsonb NOT NULL, metrics jsonb, PRIMARY KEY(account,tweet_id)
);
CREATE TABLE IF NOT EXISTS agent_events (
 account text NOT NULL, day date NOT NULL, at timestamptz NOT NULL DEFAULT now(),
 kind text NOT NULL, detail jsonb NOT NULL
);
"""


class Ledger:
    def __init__(self, url, account):
        self.url = url
        self.account = str(account)

    def sql(self, statement, **data):
        env = {k: os.environ[k] for k in ('PATH','HOME','LANG') if k in os.environ}
        env.update(PGDATABASE=self.url, PGCONNECT_TIMEOUT='8',
                   PGOPTIONS='-c statement_timeout=10000 -c lock_timeout=5000',
                   AGENT_DATA=json.dumps(dict(data, account=self.account)))
        # getenv keeps credentials and private drafts out of the process arguments.
        header = "\\getenv input AGENT_DATA\n"
        query = statement.replace('$data', "(:'input'::jsonb)").replace('$account', "(:'input'::jsonb->>'account')")
        proc = subprocess.run(['psql','-XqAt','-v','ON_ERROR_STOP=1'], input=header+query,
                              env=env, capture_output=True, text=True, timeout=20)
        if proc.returncode:
            raise RuntimeError('ledger_unavailable')
        return [json.loads(line) for line in proc.stdout.splitlines() if line]

    def initialise(self):
        self.sql(SCHEMA)
        posts = json.loads((Path(__file__).resolve().parents[1]/'data/history.json').read_text())['posts']
        self.sql("""INSERT INTO agent_memory SELECT $account,p->>'id',(p->>'time')::timestamptz,p-'metrics',p->'metrics'
          FROM jsonb_array_elements($data->'posts') p ON CONFLICT DO NOTHING;""", posts=posts)

    def slot(self, day):
        return next(iter(self.sql("SELECT to_jsonb(s) FROM agent_slots s WHERE account=$account AND day=($data->>'day')::date",day=str(day))),None)

    def claim(self, day, owner):
        return bool(self.sql("""INSERT INTO agent_slots AS s(account,day,state,owner,lease_until,attempts)
          SELECT $account,($data->>'day')::date,'working',$data->>'owner',now()+interval '12 minutes',1
          WHERE NOT EXISTS (SELECT 1 FROM agent_memory WHERE account=$account AND
          (published AT TIME ZONE 'Asia/Kolkata')::date=($data->>'day')::date)
          ON CONFLICT (account,day) DO UPDATE SET owner=excluded.owner,lease_until=excluded.lease_until,
          attempts=s.attempts+1 WHERE s.state='working' AND s.lease_until<=now() AND s.attempts<3
          RETURNING to_json(true)""", day=str(day),owner=owner))

    def intent(self, day, owner, draft):
        return bool(self.sql("""UPDATE agent_slots SET state='sending',draft=$data->'draft',intent_at=clock_timestamp()
          WHERE account=$account AND day=($data->>'day')::date AND owner=$data->>'owner' AND state='working'
          AND lease_until>now() AND day=(now() AT TIME ZONE 'Asia/Kolkata')::date RETURNING to_json(true)""",
          day=str(day),owner=owner,draft=draft))

    def finish(self, day, tweet_id):
        self.sql("""WITH saved AS (UPDATE agent_slots SET state='published',tweet_id=$data->>'id'
          WHERE account=$account AND day=($data->>'day')::date AND state='sending'
          RETURNING account,tweet_id,intent_at,draft)
          INSERT INTO agent_memory SELECT account,tweet_id,intent_at,draft,NULL FROM saved
          ON CONFLICT DO NOTHING""", day=str(day),id=str(tweet_id))

    def failure(self,day,owner,kind,from_state):
        self.sql("""UPDATE agent_slots SET state=CASE WHEN attempts>=3 THEN 'skipped' ELSE 'working' END,
          error=$data->>'kind',lease_until=now()+interval '30 minutes'
          WHERE account=$account AND day=($data->>'day')::date AND owner=$data->>'owner'
          AND state=$data->>'state'""",day=str(day),owner=owner,kind=kind,state=from_state)

    def event(self,day,kind,detail):
        self.sql("INSERT INTO agent_events(account,day,kind,detail) VALUES ($account,($data->>'day')::date,$data->>'kind',$data->'detail')",
                 day=str(day),kind=kind,detail=detail)

    def memory(self):
        return self.sql("""SELECT item || jsonb_build_object('metrics',metrics,'time',published,'id',tweet_id)
          FROM agent_memory WHERE account=$account ORDER BY published DESC""")

    def candidates(self):
        return self.sql("""SELECT detail FROM agent_events WHERE account=$account AND kind='evaluation'
                           ORDER BY at DESC LIMIT 24""")

    def pending(self):
        return self.sql("""SELECT to_jsonb(s) FROM agent_slots s WHERE account=$account AND state='sending'
                           AND intent_at>now()-interval '7 days' ORDER BY day DESC""")
