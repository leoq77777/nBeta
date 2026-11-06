"""Aggregate published ESPN box scores; a box-score index is not causal impact."""
import csv
import json
import math
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from pipeline.config import canonical_team

URL = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event='


def parse_box(payload, game_id):
    boxes = payload.get('boxscore', {}).get('players', [])
    if len(boxes) != 2:
        raise ValueError(f'{game_id}: missing teams in box score')
    rows = []
    for box in boxes:
        groups = box.get('statistics', [])
        if not groups:
            raise ValueError(f'{game_id}: missing statistics')
        group = groups[0]
        names = group.get('names', group.get('labels', []))
        required = ('MIN', 'PTS', 'FG', 'FT', 'AST', 'TO', 'STL', 'BLK', 'OREB', 'DREB', 'PF')
        if not all(k in names for k in required):
            raise ValueError(f'{game_id}: missing box score fields')
        for player in group.get('athletes', []):
            if player.get('didNotPlay') or not player.get('stats'):
                continue
            data = dict(zip(names, player['stats']))
            if data.get('MIN') in ('--', '', None):
                continue
            try:
                mins = str(data['MIN']).split(':')
                minutes = float(mins[0]) + (float(mins[1]) / 60 if len(mins) > 1 else 0)
                if minutes <= 0:
                    continue
                fgm, fga = map(int, data['FG'].split('-'))
                ftm, fta = map(int, data['FT'].split('-'))
                pts, ast, tov, stl, blk, orb, drb, pf = (int(data[k]) for k in ('PTS','AST','TO','STL','BLK','OREB','DREB','PF'))
            except (ValueError, KeyError, IndexError) as exc:
                raise ValueError(f'{game_id}: malformed player statistics') from exc
            a = player['athlete']
            # Hollinger Game Score: descriptive box-score production, not adjusted impact.
            score = pts + .4*fgm - .7*fga - .4*(fta-ftm) + .7*orb + .3*drb + stl + .7*ast + .7*blk - .4*pf - tov
            rows.append(dict(id=str(a['id']), name=a['displayName'], team=canonical_team(box['team']['abbreviation']), minutes=minutes, points=pts, assists=ast, rebounds=orb+drb, fgm=fgm, fga=fga, ftm=ftm, fta=fta, steals=stl, blocks=blk, turnovers=tov, score=score, shots=[]))
    if not rows:
        raise ValueError(f'{game_id}: empty box score')
    by_id = {p['id']: p for p in rows}
    for play in payload.get('plays', []):
        if not play.get('shootingPlay') or play.get('pointsAttempted') not in (2, 3):
            continue
        participants = play.get('participants') or []
        shooter = by_id.get(str(participants[0].get('athlete', {}).get('id'))) if participants else None
        coordinate = play.get('coordinate') or {}
        x, y = coordinate.get('x'), coordinate.get('y')
        # ESPN coordinates are feet from the hoop end, with x centered at 25.
        if shooter is not None and all(isinstance(v, (int, float)) and math.isfinite(v) for v in (x, y)) and 0 <= x <= 50 and -5.25 <= y <= 94:
            shooter['shots'].append(dict(x=x, y=y, made=bool(play.get('scoringPlay'))))
    return rows


def build_player_stats(seed, cache):
    cache.mkdir(parents=True, exist_ok=True)
    with (seed / 'schedule.csv').open(newline='') as f:
        games = [g for g in csv.DictReader(f) if g['status'] == 'final']
    games.sort(key=lambda g: (g['date'], g['id']))
    if not games:
        raise ValueError('no finalized games')
    cutoff = sorted(g['date'] for g in games)[max(0, len(games)-45)]
    def fetch(g):
        path = cache / (g['id'] + '.json')
        if path.exists() and g['date'] < cutoff:
            return parse_box(json.loads(path.read_text()), g['id'])
        request = Request(URL + g['id'], headers={'User-Agent':'n-Beta/1.0 (NBA research dashboard)'})
        with urlopen(request, timeout=20) as response:
            payload = json.load(response)
        rows = parse_box(payload, g['id'])
        path.write_text(json.dumps(payload))
        return rows
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(fetch, games))
    totals = defaultdict(lambda: defaultdict(float))
    shots = defaultdict(list)
    for rows in results:
        for row in rows:
            p = totals[row['id']]
            p.update(id=row['id'], name=row['name'], team=row['team'])
            p['gp'] += 1
            shots[row['id']].extend(row['shots'])
            for key in ('minutes','points','assists','rebounds','fgm','fga','ftm','fta','steals','blocks','turnovers','score'):
                p[key] += row[key]
    players = []
    for p in totals.values():
        gp = int(p['gp'])
        attempts = p['fga'] + .44*p['fta']
        players.append(dict(id=p['id'], name=p['name'], team=p['team'], gp=gp,
            mpg=round(p['minutes']/gp,1), ppg=round(p['points']/gp,1), apg=round(p['assists']/gp,1),
            rpg=round(p['rebounds']/gp,1), ts=round(p['points']/(2*attempts),4) if attempts else None,
            spg=round(p['steals']/gp,1), bpg=round(p['blocks']/gp,1), topg=round(p['turnovers']/gp,1),
            fg=round(p['fgm']/p['fga'],4) if p['fga'] else None,
            ft=round(p['ftm']/p['fta'],4) if p['fta'] else None,
            fga=int(p['fga']), shots=shots[p['id']],
            game_score=round(p['score']/gp,2), total_game_score=round(p['score'],2)))
    return dict(source='ESPN game box scores', season_games=len(games), games_collected=len(results),
        through=max(g['date'] for g in games), checked_at=datetime.now(timezone.utc).isoformat(), players=players)
