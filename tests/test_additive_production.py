import copy,gzip,hashlib,json,tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
import numpy as np
from pipeline.additive import activate,raw_boxes,matrices,sha
from deploy.trace import update_trace,load_events
APP=Path(__file__).resolve().parents[1]

class AdditiveProductionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.snapshot=self.root/'snapshot'
        (self.snapshot/'data').mkdir(parents=True);(self.root/'player-box-cache').mkdir();(self.root/'models/active').mkdir(parents=True)
        self.now=datetime(2026,11,6,7,tzinfo=timezone.utc);self.tip=self.now+timedelta(hours=48)
        self.final=dict(id='f',date='2026-11-04',tip='2026-11-04T23:00:00+00:00',home='BOS',away='NY',status='final',neutral=0,hs=100,**{'as':90},p_home=.5,spread=0)
        self.future=dict(id='u',date='2026-11-08',tip=self.tip.isoformat(),home='BOS',away='NY',status='upcoming',neutral=0,hs='',**{'as':''},p_home=.5,spread=0,market_spread=None)
        names=['MIN','PTS','FG','3PT','FT','REB','AST','STL','BLK','TO','PF']
        def team(ab,points):
            return dict(team={'abbreviation':ab},statistics=[dict(names=names,athletes=[dict(athlete=dict(id=str(i+(100 if ab=='BOS' else 200)),displayName=ab+str(i),position={'abbreviation':'G'}),didNotPlay=False,stats=['48',str(points),('8-16' if points==20 else '7-16'),'0-4','4-5','10','4','1','1','2','2']) for i in range(5)])])
        self.raw=dict(boxscore=dict(players=[team('BOS',20),team('NY',18)]),header=dict(competitions=[dict(status={'period':4})]))
        (self.root/'player-box-cache/f.json').write_text(json.dumps(self.raw))
        self.history=gzip.compress(json.dumps(dict(games=[],boxes={},aliases={})).encode(),mtime=0)
        (self.root/'models/active/history.json.gz').write_bytes(self.history)
        def linear(n,intercept):return dict(mean=[0.]*n,scale=[1.]*n,coef=[0.]*n,intercept=intercept)
        model=dict(name='Additive v1',training_games=0,training_through='fixture',history_sha256=hashlib.sha256(self.history).hexdigest(),feature_code_sha256=sha(APP/'pipeline/additive_features.py'),filter=dict(q=.08,prior_sd=2,obs_sd=14,h_q=.003,noise_rate=.01),h0=2.5,margin=linear(66,.2),total=linear(74,220),total_sd=18,rho=.1)
        (self.root/'models/active/model.json').write_text(json.dumps(model))
        self.oldtrace=dict(game_id='u',date=self.future['date'],tip=self.future['tip'],home='BOS',away='NY',inputs={},distribution=dict(sd=12,scale=10,df=7.5),stages=[dict(name='context',mean=0,p_home=.5)])
        (self.snapshot/'data/schedule.json').write_text(json.dumps([self.final,self.future]));(self.snapshot/'data/prediction_traces.json').write_text(json.dumps([self.oldtrace]))
    def tearDown(self):self.tmp.cleanup()
    def test_activation_and_two_model_forward_settlement(self):
        meta=activate(self.root,self.snapshot,self.now);self.assertEqual(meta['model_name'],'Additive v1')
        games=json.load(open(self.snapshot/'data/schedule.json'));g=games[1]
        self.assertEqual(g['prediction_model'],'Additive v1');self.assertAlmostEqual(g['home_score_mean']+g['away_score_mean'],g['total_mean'],places=2)
        self.assertEqual(g['legacy_p_home'],.5);self.assertNotEqual(g['p_home'],.5)
        report=update_trace(self.root,self.snapshot,'pre',APP,self.now);self.assertEqual(report['forecast_records'],2)
        g.update(status='final',hs=115,**{'as':105});(self.snapshot/'data/schedule.json').write_text(json.dumps(games))
        (self.snapshot/'data/prediction_traces.json').write_text('[]');(self.snapshot/'data/legacy_prediction_traces.json').write_text('[]')
        report=update_trace(self.root,self.snapshot,'post',APP,self.tip+timedelta(hours=6))
        self.assertEqual(report['eligible_games'],1);self.assertEqual(report['evaluated_forecasts'],2)
        self.assertEqual(report['score_metrics'][0]['games'],1)
        self.assertEqual({m['model_name'] for m in report['stage_metrics']},{'Additive v1','Legacy Student-t'})
    def test_artifact_and_input_fail_closed(self):
        (self.root/'models/active/history.json.gz').write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError,'integrity'):activate(self.root,self.snapshot,self.now)
        self.assertNotIn('prediction_model',json.load(open(self.snapshot/'data/schedule.json'))[1])
    def test_unknown_stats_are_quarantined_not_zero_filled(self):
        raw=copy.deepcopy(self.raw);raw['boxscore']['players'][0]['statistics'][0]['athletes'][0]['stats'][0]='--'
        boxes,held=raw_boxes(raw,dict(id='f',home='BOS',away='NY',hs=100,away_score=90),{})
        self.assertNotIn('BOS',boxes);self.assertIn('NY',boxes);self.assertTrue(held)
    def test_no_bundle_uses_explicit_legacy_path(self):
        (self.root/'models/active/model.json').unlink()
        with self.assertRaisesRegex(ValueError,'missing'):activate(self.root,self.snapshot,self.now)

    def test_overtime_label_preserves_valid_team_minutes(self):
        raw=copy.deepcopy(self.raw)
        raw['header']['competitions'][0]['status']={'type':{'detail':'Final/OT'}}
        for team in raw['boxscore']['players']:
            for p in team['statistics'][0]['athletes']:p['stats'][0]='53'
        boxes,held=raw_boxes(raw,dict(id='f',home='BOS',away='NY',hs=100,away_score=90),{})
        self.assertEqual(set(boxes),{'BOS','NY'});self.assertEqual(held,[])
