"""Compare seed snapshots with ESPN public records without modifying model inputs.

Run: python -m pipeline.verify_seed [--refresh]
Evidence is cached under data/verification and is excluded from the Pages bundle.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import unicodedata
import urllib.request
from zoneinfo import ZoneInfo
from .config import canonical_team

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/'

def name_key(name):
    return ''.join(c.lower() for c in unicodedata.normalize('NFKD',name) if c.isalnum())

def event_row(event):
    c=event['competitions'][0]
    sides={x['homeAway']:x for x in c['competitors']}
    def score(side):
        value=sides[side].get('score')
        return int(float(value.get('value',value.get('displayValue',0)) if isinstance(value,dict) else value or 0))
    tip=event['date']
    return dict(id=str(event['id']), date=datetime.fromisoformat(tip.replace('Z','+00:00')).astimezone(ZoneInfo('America/New_York')).date().isoformat(),
                tip=tip, home=canonical_team(sides['home']['team']['abbreviation']), away=canonical_team(sides['away']['team']['abbreviation']),
                hs=score('home'), away_score=score('away'), completed=c.get('status',event.get('status',{})).get('type',{}).get('completed',False))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh',action='store_true',help='Refetch external evidence instead of using cache')
    args=parser.parse_args()
    seed=ROOT/'data/seed'; out=ROOT/'data/verification';out.mkdir(exist_ok=True)
    def rows(n):
        with (seed/f'{n}.csv').open() as f:
            return list(csv.DictReader(f))
    ts,gs,ps,history=map(rows,['teams','schedule','players','history'])
    run=rows('run')[0]
    year=int(run['season'][:4])+1
    records=[]
    def fetch(key,endpoint):
        path=out/f'{key}.json.gz'; url=endpoint if endpoint.startswith('https://') else BASE+endpoint
        if path.exists() and not args.refresh:
            with gzip.open(path,'rt') as f: envelope=json.load(f)
        else:
            try:
                req=urllib.request.Request(url,headers={'User-Agent':'nBeta-SeedVerification/1.0'})
                with urllib.request.urlopen(req,timeout=20) as response: payload=json.load(response)
                envelope=dict(url=url,fetched_at=datetime.now(timezone.utc).isoformat(),payload=payload)
                with gzip.open(path,'wt') as f:json.dump(envelope,f)
            except Exception as exc:
                return dict(key=key,url=url,error=str(exc))
        return dict(key=key,url=url,fetched_at=envelope['fetched_at'],payload=envelope['payload'],file=str(path.relative_to(ROOT)))
    def team_task(t):
        ab=t['abbr'].lower()
        return fetch('schedule-'+ab,f'teams/{ab}/schedule?season={year}&seasontype=2'), fetch('roster-'+ab,f'teams/{ab}/roster?season={year}')
    with ThreadPoolExecutor(max_workers=4) as pool:
        for schedule,roster in pool.map(team_task,ts): records.extend([schedule,roster])
    print('Retrieved schedule/roster evidence:',len(records),flush=True)
    external={}; identities={}; failures=[]; conflicts=[]
    for rec in records:
        if 'error' in rec: failures.append({k:v for k,v in rec.items() if k!='payload'});continue
        payload=rec['payload']
        if rec['key'].startswith('schedule-'):
            for event in payload.get('events',[]):
                r=event_row(event)
                if r['id'] in external and external[r['id']]!=r:conflicts.append(r['id'])
                external[r['id']]=r
        else:
            team=canonical_team(payload['team']['abbreviation'])
            for player in payload.get('athletes',[]): identities[str(player['id'])]=dict(name=player['displayName'],team=team)
    mismatches=[]; final_matches=0; fixture_matches=0; status_changes=[]; tip_changes=[]
    for g in gs:
        ext=external.get(g['id'])
        if not ext:mismatches.append(dict(id=g['id'],issue='ID not found in fetched schedules'));continue
        fields={k:(g[k],ext[k]) for k in ['date','home','away'] if (canonical_team(g[k]) if k in ['home','away'] else g[k])!=ext[k]}
        if fields:mismatches.append(dict(id=g['id'],issue='fixture mismatch',fields=fields));continue
        fixture_matches+=1
        if datetime.fromisoformat(g['tip'].replace('Z','+00:00')) != datetime.fromisoformat(ext['tip'].replace('Z','+00:00')):
            tip_changes.append(dict(id=g['id'],seed=g['tip'],current=ext['tip']))
        if g['status']=='final':
            if ext['completed'] and (int(g['hs']),int(g['as']))==(ext['hs'],ext['away_score']):final_matches+=1
            else:mismatches.append(dict(id=g['id'],issue='final score/status mismatch',seed=[g['hs'],g['as']],current=[ext['hs'],ext['away_score'],ext['completed']]))
        elif ext['completed']:status_changes.append(g['id'])
    player_mismatch=[]; identities_matched=0; teams_matched=0
    for p in ps:
        ext=identities.get(p['athlete_id'])
        if not ext:player_mismatch.append(dict(id=p['athlete_id'],name=p['name'],issue='not on fetched current rosters'));continue
        if name_key(ext['name'])==name_key(p['name']):identities_matched+=1
        else:player_mismatch.append(dict(id=p['athlete_id'],name=p['name'],issue='name mismatch',current=ext['name']))
        if canonical_team(p['abbr'])==ext['team']:teams_matched+=1
        else:player_mismatch.append(dict(id=p['athlete_id'],name=p['name'],issue='current team differs',seed=p['abbr'],current=ext['team']))
    # Use only games already final in the original snapshot, never later results.
    final_ids=[g['id'] for g in gs if g['status']=='final']
    with ThreadPoolExecutor(max_workers=4) as pool:
        box_records=list(pool.map(lambda gid:fetch('box-'+gid,'summary?event='+gid),final_ids))
    records.extend(box_records)
    gp=Counter();minutes=defaultdict(float);missing_boxes=[]
    for rec in box_records:
        if 'error' in rec:
            failures.append({k:v for k,v in rec.items() if k!='payload'});missing_boxes.append(rec['key']);continue
        boxes=rec['payload'].get('boxscore',{}).get('players',[])
        if len(boxes)!=2:missing_boxes.append(rec['key']);continue
        for box in boxes:
            ab=canonical_team(box['team']['abbreviation'])
            seen=set()
            for stats in box.get('statistics',[]):
                names=stats.get('names',stats.get('labels',[]))
                idx=names.index('MIN') if 'MIN' in names else names.index('minutes') if 'minutes' in names else None
                if idx is None:continue
                for player in stats.get('athletes',[]):
                    pid=str(player['athlete']['id'])
                    if pid in seen or player.get('didNotPlay') or not player.get('stats'):continue
                    seen.add(pid)
                    raw=player['stats'][idx]
                    try:
                        parts=str(raw).split(':')
                        mins=float(parts[0])+(float(parts[1])/60 if len(parts)>1 else 0)
                    except ValueError:continue
                    key=(ab,pid);gp[key]+=1;minutes[key]+=mins
    stat_differences=[];gp_matched=0;mpg_compatible=0
    for player in ps:
        key=(canonical_team(player['abbr']),player['athlete_id'])
        actual_gp=gp[key];actual_mpg=minutes[key]/actual_gp if actual_gp else 0
        same_gp=int(float(player['gp']))==actual_gp
        # Box score minutes are often whole-minute rounded; allow 0.55 minute per game.
        same_mpg=not player['mpg'] or abs(float(player['mpg'])-actual_mpg)<=.55
        gp_matched+=same_gp;mpg_compatible+=same_mpg and bool(player['mpg'])
        if not same_gp or not same_mpg:
            stat_differences.append(dict(id=player['athlete_id'],name=player['name'],seed_gp=int(float(player['gp'])),box_gp=actual_gp,seed_mpg=float(player['mpg']) if player['mpg'] else None,box_mpg=round(actual_mpg,3)))
    wins=Counter();losses=Counter();counts=Counter();date_errors=[]
    for g in gs:
        counts.update([canonical_team(g['home']),canonical_team(g['away'])])
        if g['status']=='final':
            winner,loser=(g['home'],g['away']) if int(g['hs'])>int(g['as']) else(g['away'],g['home'])
            wins[winner]+=1;losses[loser]+=1
        if datetime.fromisoformat(g['tip'].replace('Z','+00:00')).astimezone(ZoneInfo('America/New_York')).date().isoformat()!=g['date']:date_errors.append(g['id'])
    upstream_commits=fetch('upstream-commits','https://api.github.com/repos/chronicaria/chronicaria.github.io/commits?path=data/teams.csv&per_page=100')
    upstream={}
    if 'payload' in upstream_commits and isinstance(upstream_commits['payload'],list) and upstream_commits['payload']:
        commits=upstream_commits['payload'];sha=commits[0]['sha']
        upstream_files=fetch('upstream-files','https://api.github.com/repos/chronicaria/chronicaria.github.io/contents/data?ref='+sha)
        if isinstance(upstream_files.get('payload'),list):
            remote={r['name']:r['sha'] for r in upstream_files['payload']}
            matches={}
            for p in seed.iterdir():
                if not p.is_file():continue
                body=p.read_bytes()
                digest=hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest()
                matches[p.name]=dict(local_git_blob_sha=digest,upstream_git_blob_sha=remote.get(p.name),exact_match=digest==remote.get(p.name))
            upstream=dict(repository='https://github.com/chronicaria/chronicaria.github.io',commit=sha,
                          commit_date=commits[0]['commit']['committer']['date'],file_matches=matches,
                          earliest_available_teams_commit=commits[-1]['commit']['committer']['date'],
                          caveat='Matching a published forecast export does not validate its priors, player value formula or historical availability.')
        records.append(upstream_files)
    records.append(upstream_commits)
    report=dict(verified_at=datetime.now(timezone.utc).isoformat(),seed_as_of=run['as_of'],season=run['season'],upstream=upstream,
        seed_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in seed.iterdir() if p.is_file()},
        internal=dict(teams=len(ts),games=len(gs),final_games=sum(g['status']=='final' for g in gs),players=len(ps),history_rows=len(history),
                      unique_game_ids=len(set(g['id'] for g in gs)),unique_player_ids=len(set(p['athlete_id'] for p in ps)),team_game_counts=dict(counts),et_date_errors=date_errors,
                      record_mismatches=[t['abbr'] for t in ts if(int(t['w']),int(t['l']))!=(wins[t['abbr']],losses[t['abbr']])],
                      metadata_games_left=int(run['games_left']),listed_games_left=sum(g['status']!='final' for g in gs),
                      first_history_matches_prior=sum(float(next(r for r in history if r['abbr']==t['abbr'] and r['date']==min(x['date'] for x in history))['rating'])==float(t['rating_prior']) for t in ts)),
        external=dict(fixtures_fetched=len(external),fixture_matches=fixture_matches,final_score_matches=final_matches,fixture_mismatches=mismatches,
                      source_conflicts=sorted(set(conflicts)),tip_changes=tip_changes,completed_since_snapshot=status_changes,
                      identities_matched=identities_matched,team_memberships_matched=teams_matched,player_mismatches=player_mismatch,
                      boxscores_fetched=len(box_records)-len(missing_boxes),missing_boxscores=missing_boxes,player_gp_matches=gp_matched,player_mpg_checked=sum(bool(p["mpg"]) for p in ps),player_mpg_compatible=mpg_compatible,player_stat_differences=stat_differences,fetch_failures=failures),
        not_verified=['preseason availability of rating_prior','bookmaker/timestamp provenance of vegas_total','player value formula or training data','historical injury status/probability/return-date snapshots','raw seed history ratings or seed model projections'],
        sources=[{k:v for k,v in r.items() if k!='payload'} for r in records])
    (out/'seed_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in report['external'].items() if k not in {'tip_changes','player_stat_differences'}},ensure_ascii=False,indent=2))
    print('Report:',out/'seed_audit.json')

if __name__=='__main__':main()
