import tempfile
import shutil
import unittest
from pathlib import Path
from pipeline.config import ModelConfig
from pipeline.data_fetcher import load_dataset, compute_stint_garbage_time_weight
from pipeline.model import compute_audit_and_calibration, student_t_cdf, compute_context_adjustment
from pipeline.build_daily import build_all

ROOT = Path(__file__).resolve().parents[1]

class PipelineTests(unittest.TestCase):
    def test_calibration_uses_observations(self):
        games = [dict(status='final', p_home=.8, hs=90, **{'as':100}),
                 dict(status='final', p_home=.8, hs=110, **{'as':100})]
        _, audit, bins = compute_audit_and_calibration(games, ModelConfig())
        self.assertEqual(audit[0]['games'], 2)
        self.assertAlmostEqual(audit[0]['brier'], .34, places=4)
        self.assertEqual(sum(x['n'] for x in bins), 2)
        self.assertAlmostEqual(next(x for x in bins if x['n'])['actual'], .5)

    def test_empty_audit(self):
        _, audit, bins = compute_audit_and_calibration([], ModelConfig())
        self.assertTrue(all(x['games'] == 0 for x in audit))
        self.assertTrue(all(x['logloss'] is None for x in audit))
        self.assertEqual(sum(x['n'] for x in bins), 0)

    def test_aliases_apply_config(self):
        ds = load_dataset(ROOT/'data/seed', ModelConfig())
        self.assertIn('UTA', ds['teams_meta'])
        self.assertIn('NOP', ds['teams_meta'])
        self.assertNotIn('UTAH', ds['teams_meta'])
        self.assertTrue(all(g['home'] in ds['teams_meta'] for g in ds['schedule']))
        self.assertTrue(all(p['abbr'] in ds['teams_meta'] for p in ds['players']))

    def test_distribution_symmetry(self):
        self.assertEqual(student_t_cdf(0, 7.5), .5)
        self.assertAlmostEqual(student_t_cdf(2, 7.5) + student_t_cdf(-2, 7.5), 1)
        self.assertEqual(compute_context_adjustment({'neutral':1}, ModelConfig()), 0)

    def test_smoke_build(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT/'data/seed', root/'data/seed')
            build_all(root, n_sims=200)
            teams = json.loads((root/'data/teams.json').read_text())
            schedule = json.loads((root/'data/schedule.json').read_text())
            for t in teams:
                count = sum(t['abbr'] in (g['home'],g['away']) for g in schedule)
                self.assertAlmostEqual(float(t['proj_w']) + float(t['proj_l']), count)
            self.assertAlmostEqual(sum(float(t['p_title']) for t in teams), 1, places=3)

    def test_observed_market_zero_is_preserved(self):
        import csv, json
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            shutil.copytree(ROOT/'data/seed',root/'data/seed')
            path=root/'data/seed/schedule.csv'
            with path.open() as f:
                reader=csv.DictReader(f); fields=reader.fieldnames+['market_spread']; data=list(reader)
            data[0]['market_spread']='0'
            with path.open('w',newline='') as f:
                writer=csv.DictWriter(f,fields); writer.writeheader(); writer.writerows(data)
            build_all(root,n_sims=40)
            games=json.loads((root/'data/schedule.json').read_text())
            self.assertEqual(games[0]['market_spread'],0)
            self.assertEqual(games[0]['edge_pts'],-games[0]['spread'])
            self.assertIsNone(games[1]['market_spread'])
            pmf=json.loads((root/'data/win_dist.json').read_text())
            for ab in {r['abbr'] for r in pmf}:
                self.assertAlmostEqual(sum(r['p_prior'] for r in pmf if r['abbr']==ab),1)

    def test_invalid_seed_rejected(self):
        import csv
        with tempfile.TemporaryDirectory() as tmp:
            seed=Path(tmp)/'seed'
            shutil.copytree(ROOT/'data/seed',seed)
            path=seed/'schedule.csv'
            with path.open() as f:
                reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
            rows[1]['id']=rows[0]['id']
            with path.open('w',newline='') as f:
                writer=csv.DictWriter(f,fields);writer.writeheader();writer.writerows(rows)
            with self.assertRaises(ValueError):
                load_dataset(seed,ModelConfig())

    def test_student_t_known_values(self):
        import math
        for z in [-2,-.5,0,.5,2]:
            self.assertAlmostEqual(student_t_cdf(z,1),.5+math.atan(z)/math.pi,places=7)

    def test_seed_verifier_normalizes_source_formats(self):
        from pipeline.verify_seed import event_row, name_key
        row=event_row(dict(id='x',date='2026-11-03T01:00Z',competitions=[dict(status={'type':{'completed':True}},competitors=[
            dict(homeAway='home',team={'abbreviation':'UTAH'},score={'value':102.0}),
            dict(homeAway='away',team={'abbreviation':'NO'},score='99')])]))
        self.assertEqual((row['date'],row['home'],row['away'],row['hs'],row['away_score']),('2026-11-02','UTA','NOP',102,99))
        self.assertTrue(row['completed'])
        self.assertEqual(name_key('Nikola Jokić'),name_key('Nikola Jokic'))

    def test_invalid_sims(self):
        with self.assertRaises(ValueError):
            build_all(ROOT, n_sims=0)

if __name__ == '__main__':
    unittest.main()
