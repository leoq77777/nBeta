import unittest
from deploy.player_stats import parse_box

class PlayerStatsTests(unittest.TestCase):
    def test_game_score_and_dnp(self):
        names=['MIN','PTS','FG','FT','AST','TO','STL','BLK','OREB','DREB','PF']
        def team(abbr):
            return {'team':{'abbreviation':abbr},'statistics':[{'names':names,'athletes':[
                {'athlete':{'id':abbr,'displayName':abbr},'stats':['30','25','10-20','5-6','4','2','1','1','2','5','3']},
                {'athlete':{'id':'dnp','displayName':'DNP'},'stats':['--']*11}]}]}
        rows=parse_box({'boxscore':{'players':[team('A'),team('B')]}},'1')
        self.assertEqual(len(rows),2)
        self.assertAlmostEqual(rows[0]['score'], 25+.4*10-.7*20-.4+.7*2+.3*5+1+.7*4+.7-.4*3-2)
        self.assertEqual(rows[0]['minutes'],30)
    def test_incomplete_box_fails_closed(self):
        with self.assertRaises(ValueError):
            parse_box({'boxscore':{'players':[]}},'1')


class ShotLocationTests(unittest.TestCase):
    def test_only_located_field_goals_belong_to_shooter(self):
        def box(player_id):
            return {'team': {'abbreviation': 'BOS'}, 'statistics': [{
                'names': ['MIN','PTS','FG','FT','AST','TO','STL','BLK','OREB','DREB','PF'],
                'athletes': [{'athlete': {'id': player_id, 'displayName': player_id},
                              'stats': ['30','8','3-7','2-2','1','2','1','1','1','3','2']}]}]}
        def shot(x=25, y=0, points=2, participants=None, **extra):
            return dict(shootingPlay=True, pointsAttempted=points, scoringPlay=True,
                        coordinate={'x':x,'y':y}, participants=participants if participants is not None else
                        [{'athlete':{'id':'shooter'}},{'athlete':{'id':'assister'}}], **extra)
        payload={'boxscore':{'players':[box('shooter'),box('assister')]}, 'plays':[
            shot(), shot(x=0,y=24), shot(y=60), shot(points=1), shot(x=-214748340),
            shot(y=float('nan')), shot(x='25'), shot(participants=[]), shot(x=None)]}
        rows=parse_box(payload,'game')
        self.assertEqual(rows[0]['shots'], [{'x':25,'y':0,'made':True},
                                          {'x':0,'y':24,'made':True},
                                          {'x':25,'y':60,'made':True}])
        self.assertEqual(rows[1]['shots'], [])
        self.assertEqual(rows[0]['fgm'],3)
        self.assertEqual(rows[0]['steals'],1)

    def test_snapshot_aggregates_shots_and_season_rates(self):
        import io
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from deploy.player_stats import build_player_stats
        names=['MIN','PTS','FG','FT','AST','TO','STL','BLK','OREB','DREB','PF']
        boxes=[{'team':{'abbreviation':team},'statistics':[{'names':names,'athletes':[
            {'athlete':{'id':team,'displayName':team},'stats':['30','8','3-7','2-2','1','2','1','1','1','3','2']}]}]} for team in ['BOS','DET']]
        payload={'boxscore':{'players':boxes},'plays':[{'shootingPlay':True,'pointsAttempted':2,
            'scoringPlay':False,'coordinate':{'x':25,'y':0},'participants':[{'athlete':{'id':'BOS'}}]}]}
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'schedule.csv').write_text('id,date,status\n1,2026-10-20,final\n2,2026-10-22,final\n')
            with patch('deploy.player_stats.urlopen', side_effect=lambda *a,**kw:io.BytesIO(json.dumps(payload).encode())):
                result=build_player_stats(root,root/'cache')
        player=next(p for p in result['players'] if p['id']=='BOS')
        self.assertEqual(player['gp'],2)
        self.assertEqual(player['fga'],14)
        self.assertEqual(len(player['shots']),2)
        self.assertEqual(player['fg'],round(6/14,4))
        self.assertEqual(player['ft'],1)
        self.assertEqual(player['topg'],2)
