import csv
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from deploy.feed import ingest

FIELDS=['id','date','tip','home','away','status','hs','as','p_home','spread','home_delta','neutral','note']
def event(gid='2', score=('110','100'), completed=True):
    return dict(id=gid,date='2026-11-05T03:00Z',season=dict(year=2027,type=2),competitions=[dict(neutralSite=False,notes=[],status=dict(type=dict(completed=completed,state='post' if completed else 'in')),competitors=[dict(homeAway='home',team=dict(abbreviation='BOS'),score=score[0]),dict(homeAway='away',team=dict(abbreviation='NY'),score=score[1])])])

class FeedTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.seed=self.root/'seed';self.seed.mkdir();self.evidence=self.root/'evidence'
        with (self.seed/'schedule.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows([dict(id='1',date='2026-11-02',tip='2026-11-03T00:00Z',home='BOS',away='NY',status='final',hs='99',**{'as':'90'}),dict(id='2',date='2026-11-04',tip='2026-11-05T03:00Z',home='BOS',away='NY',status='upcoming')])
        (self.seed/'run.csv').write_text('season\n2026–27\n');(self.seed/'teams.csv').write_text('abbr\nBOS\nNY\n')
        self.now=datetime(2026,11,5,9,tzinfo=timezone.utc)
    def tearDown(self):self.tmp.cleanup()
    def get(self,game):return lambda day:json.dumps(dict(events=[game] if day=='20261104' else [])).encode()
    def read(self):
        with (self.seed/'schedule.csv').open() as f:
            return list(csv.DictReader(f))
    def test_final_replay_and_idempotence(self):
        first=ingest(self.seed,self.evidence,self.now,self.get(event()));self.assertEqual(sum(c['kind']=='final' for c in first['changes']),1)
        self.assertEqual((self.read()[1]['status'],self.read()[1]['hs'],self.read()[1]['as']),('final','110','100'))
        second=ingest(self.seed,self.evidence,self.now,self.get(event()));self.assertEqual(second['changes'],[])
    def test_in_progress_not_finalized(self):
        result=ingest(self.seed,self.evidence,self.now,self.get(event(completed=False)));self.assertEqual(result['pending_game_ids'],['2']);self.assertEqual(result['unresolved_past_game_ids'],['2']);self.assertEqual(self.read()[1]['status'],'upcoming')
    def test_bad_score_or_matchup_does_not_write_schedule(self):
        original=(self.seed/'schedule.csv').read_bytes()
        with self.assertRaises(ValueError):ingest(self.seed,self.evidence,self.now,self.get(event(score=('100','100'))))
        self.assertEqual((self.seed/'schedule.csv').read_bytes(),original)
        g=event();g['competitions'][0]['competitors'][0]['team']['abbreviation']='NY'
        with self.assertRaises(ValueError):ingest(self.seed,self.evidence,self.now,self.get(g))
        self.assertEqual((self.seed/'schedule.csv').read_bytes(),original)
    def test_new_game_and_corrected_result(self):
        ingest(self.seed,self.evidence,self.now,self.get(event(gid='3')));self.assertEqual(len(self.read()),3)
        ingest(self.seed,self.evidence,self.now,self.get(event(gid='3',score=('111','100'))));self.assertEqual(self.read()[2]['hs'],'111')
    def test_duplicate_event_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'Duplicate scoreboard'):
            ingest(self.seed,self.evidence,self.now,lambda day:json.dumps({'events':[event(),event()] if day=='20261104' else []}).encode())
    def test_missing_feed_fails(self):
        with self.assertRaises(ValueError):ingest(self.seed,self.evidence,self.now,lambda day:b'{}')

if __name__=='__main__':unittest.main()
