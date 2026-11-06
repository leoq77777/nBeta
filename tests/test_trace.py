import copy
import json
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from deploy.trace import update_trace,load_events,evaluate,digest

APP=Path(__file__).resolve().parents[1]

class TraceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.now=datetime(2026,11,6,7,tzinfo=timezone.utc)
        self.snapshot=self.root/'snapshot';(self.snapshot/'data/seed').mkdir(parents=True)
        self.tip=self.now+timedelta(hours=36)
        self.game=dict(id='1',date='2026-11-07',tip=self.tip.isoformat(),home='BOS',away='NY',status='upcoming',p_home=.6,spread=-3)
        self.trace=dict(game_id='1',date=self.game['date'],tip=self.game['tip'],home='BOS',away='NY',inputs={'home_b2b':0},distribution={'sd':12.,'scale':10.,'df':7.5},stages=[dict(name='strength',mean=0.,p_home=.5),dict(name='context',mean=3.,p_home=.6)])
        self.save([self.game],[self.trace])
    def tearDown(self):self.tmp.cleanup()
    def save(self,games,traces):
        (self.snapshot/'data/schedule.json').write_text(json.dumps(games));(self.snapshot/'data/prediction_traces.json').write_text(json.dumps(traces))
    def feed(self,version,now):return update_trace(self.root,self.snapshot,version,APP,now)
    def test_append_idempotence_settlement_correction_and_stage_deltas(self):
        self.feed('v1',self.now);path=self.root/'forward_ledger/events.jsonl';first=path.read_bytes()
        self.feed('v1',self.now);self.assertEqual(first,path.read_bytes())
        final=dict(self.game,status='final',hs=100,**{'as':110});self.save([final],[])
        report=self.feed('v2',self.tip+timedelta(hours=6));self.assertEqual(report['eligible_games'],1)
        records=load_events(path);game=evaluate(records)[0][0];stages=game['stages']
        self.assertGreater(stages[-1]['delta_logloss'],0);self.assertEqual(stages[-1]['delta_squared_error'],69)
        self.assertEqual(game['forecast_sha256'],next(e for e in records if e['kind']=='forecast')['sha256'])
        final['hs']=120;self.save([final],[]);self.feed('v3',self.tip+timedelta(hours=7))
        records=load_events(path);self.assertEqual(sum(e['kind']=='result' for e in records),2)
        self.assertEqual(evaluate(records)[0][0]['outcome'],1)
        self.assertTrue(path.read_bytes().startswith(first))
    def test_late_forecast_not_admitted_to_primary_cohort(self):
        self.feed('late',self.tip-timedelta(hours=2));self.save([dict(self.game,status='final',hs=100,**{'as':90})],[])
        report=self.feed('final',self.tip+timedelta(hours=6));self.assertEqual(report['eligible_games'],0);self.assertEqual(len(report['excluded']),1)
    def test_result_without_forecast_cannot_be_backfilled(self):
        self.feed('armed',self.now);self.game['id']='2'
        self.save([dict(self.game,status='final',hs=100,**{'as':90})],[])
        r=self.feed('final',self.tip+timedelta(hours=6));self.assertEqual(r['eligible_games'],0)
    def test_invalid_prediction_cannot_append(self):
        self.trace['stages'][-1]['p_home']=.7;self.save([self.game],[self.trace])
        with self.assertRaises(ValueError):self.feed('invalid',self.now)
        self.assertFalse((self.root/'forward_ledger/events.jsonl').exists())
    def test_hash_chain_detects_tampering(self):
        self.feed('v1',self.now);path=self.root/'forward_ledger/events.jsonl'
        path.write_text(path.read_text().replace('"p_home":0.6','"p_home":0.9'))
        with self.assertRaises(ValueError):load_events(path)
    def test_earlier_reschedule_rechecks_cutoff(self):
        self.feed('v1',self.now);self.game['tip']=(self.now+timedelta(hours=20)).isoformat()
        self.save([dict(self.game,status='final',hs=100,**{'as':90})],[])
        r=self.feed('final',self.tip+timedelta(hours=6));self.assertEqual(r['eligible_games'],0)
