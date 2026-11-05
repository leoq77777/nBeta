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
