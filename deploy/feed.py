"""Fetch recent ESPN scoreboards into a staged seed snapshot, without changing priors."""
from __future__ import annotations
import csv
import hashlib
import json
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from pipeline.config import canonical_team

EASTERN = ZoneInfo('America/New_York')
BASE = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates='


def fetch_day(day: str) -> bytes:
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(BASE + day, headers={'User-Agent': 'nBeta-ScoreFeed/1.0', 'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=15) as response:
                return response.read()
        except (OSError, ValueError) as exc:
            last = exc
            if attempt < 2:
                time.sleep(attempt + 1)
    raise RuntimeError(f'ESPN scoreboard {day} unavailable: {last}')


def ingest(seed: Path, evidence: Path, now: datetime | None = None, fetch=fetch_day) -> dict:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('now must be timezone-aware')
    today = now.astimezone(EASTERN).date()
    with (seed / 'schedule.csv').open(newline='') as f:
        reader = csv.DictReader(f)
        fields, rows = list(reader.fieldnames), list(reader)
    if not rows or len({r['id'] for r in rows}) != len(rows):
        raise ValueError('empty schedule or duplicate game IDs')
    by_id = {r['id']: r for r in rows}
    last_final = max(datetime.fromisoformat(r['date']).date() for r in rows if r['status'] == 'final')
    start = last_final - timedelta(days=2)
    if start > today:
        raise ValueError('snapshot data is dated in the future')
    with (seed / 'run.csv').open(newline='') as f:
        season = int(next(csv.DictReader(f))['season'][:4]) + 1
    with (seed / 'teams.csv').open(newline='') as f:
        teams = {canonical_team(r['abbr']) for r in csv.DictReader(f)}
    evidence.mkdir(parents=True, exist_ok=True)
    sources, changes, pending = [], [], []
    seen_ids = set()
    day = start
    while day <= today:
        day_code = day.strftime('%Y%m%d')
        body = fetch(day_code)
        payload = json.loads(body)
        if not isinstance(payload.get('events'), list):
            raise ValueError(f'Invalid scoreboard response: {day_code}')
        (evidence / (day_code + '.json')).write_bytes(body)
        sources.append(dict(date=day_code, url=BASE + day_code, sha256=hashlib.sha256(body).hexdigest(), events=len(payload['events'])))
        for event in payload['events']:
            es = event.get('season', {})
            if es.get('year') != season or es.get('type') != 2:
                continue
            competitions = event.get('competitions', [])
            if len(competitions) != 1:
                raise ValueError(f"Invalid competition count: {event.get('id')}")
            game = competitions[0]
            notes = ' '.join(str(n.get('headline', '')) for n in game.get('notes', [])).lower()
            if 'championship' in notes and ('cup' in notes or 'tournament' in notes):
                continue
            competitors = game.get('competitors', [])
            sides = {c.get('homeAway'): c for c in competitors}
            if len(competitors) != 2 or set(sides) != {'home', 'away'}:
                raise ValueError(f"Invalid teams: {event['id']}")
            home, away = (canonical_team(sides[s]['team']['abbreviation']) for s in ('home', 'away'))
            if home not in teams or away not in teams or home == away:
                raise ValueError(f"Unknown matchup: {event['id']}")
            tip = datetime.fromisoformat(event['date'].replace('Z', '+00:00'))
            event_day = tip.astimezone(EASTERN).date().isoformat()
            if event_day != day.isoformat():
                raise ValueError(f"Scoreboard date mismatch: {event['id']}")
            gid = str(event['id'])
            if gid in seen_ids:
                raise ValueError(f'Duplicate scoreboard game ID: {gid}')
            seen_ids.add(gid)
            status = game.get('status', event.get('status', {})).get('type', {})
            row = by_id.get(gid)
            if row is not None and (canonical_team(row['home']), canonical_team(row['away'])) != (home, away):
                raise ValueError(f'Matchup changed for {gid}')
            if row is None:
                row = {field: '' for field in fields}
                row.update(id=gid, home=home, away=away, status='upcoming', neutral='1' if game.get('neutralSite') else '0')
                rows.append(row)
                by_id[gid] = row
                changes.append(dict(id=gid, kind='new_game', date=event_day))
            if row['date'] != event_day or row['tip'] != event['date']:
                changes.append(dict(id=gid, kind='schedule_update', old_date=row['date'], date=event_day))
                row['date'], row['tip'] = event_day, event['date']
            if status.get('completed'):
                def score(side):
                    value = sides[side].get('score')
                    if isinstance(value, dict):
                        value = value.get('value', value.get('displayValue'))
                    if value is None:
                        raise ValueError(f'Missing final score: {gid}')
                    result = float(value)
                    if not result.is_integer() or result < 0:
                        raise ValueError(f'Invalid final score: {gid}')
                    return int(result)
                hs, away_score = score('home'), score('away')
                if hs == away_score:
                    raise ValueError(f'Tied final score: {gid}')
                if (row['status'], row['hs'], row['as']) != ('final', str(hs), str(away_score)):
                    changes.append(dict(id=gid, kind='final', date=event_day, home=home, away=away, home_score=hs, away_score=away_score))
                row.update(status='final', hs=str(hs), **{'as': str(away_score)})
            elif status.get('state') == 'in':
                pending.append(gid)
        day += timedelta(days=1)
    rows.sort(key=lambda r: (r['tip'], r['id']))
    with (seed / 'schedule.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    unresolved = [r['id'] for r in rows if r['status'] != 'final' and datetime.fromisoformat(r['date']).date() < today]
    result = dict(checked_at=now.astimezone(timezone.utc).isoformat(), source='ESPN scoreboard', start_date=start.isoformat(), end_date=today.isoformat(), changes=changes, pending_game_ids=pending, unresolved_past_game_ids=unresolved, sources=sources)
    (evidence / 'manifest.json').write_text(json.dumps(result, indent=2))
    return result
