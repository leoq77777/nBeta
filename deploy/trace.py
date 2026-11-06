"""Append-only pregame forecast evidence and stage residual diagnostics."""
from __future__ import annotations
import fcntl
import hashlib
import json
import math
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def timestamp(value):
    date=datetime.fromisoformat(value.replace('Z','+00:00'))
    if date.tzinfo is None:raise ValueError('Naive timestamp')
    return date.astimezone(timezone.utc)


def load_events(path):
    events=[];previous='0'*64
    if not path.exists():return events
    with path.open() as f:
        for line in f:
            event=json.loads(line);body={k:v for k,v in event.items() if k!='sha256'}
            if event['previous_sha256']!=previous or digest(body)!=event['sha256']:
                raise ValueError('Forward ledger integrity check failed')
            previous=event['sha256'];events.append(event)
    return events


def evaluate(events):
    forecasts=defaultdict(list);results={}
    for event in events:
        if event['kind']=='forecast':forecasts[event['trace']['game_id']].append(event)
        elif event['kind']=='result':results[event['game_id']]=event
    scored=[];excluded=[]
    for gid,result in results.items():
        actual_tip=timestamp(result['tip']);eligible=[]
        for event in forecasts.get(gid,[]):
            trace=event['trace'];recorded=timestamp(event['recorded_at']);original_tip=timestamp(trace['tip'])
            if (trace['home'],trace['away'])!=(result['home'],result['away']):continue
            if recorded<=min(original_tip,actual_tip)-timedelta(hours=24):eligible.append(event)
        if not eligible:
            excluded.append(dict(game_id=gid,reason='no_valid_T_minus_24h_forecast'));continue
        # One most recent eligible forecast per immutable model version, never cherry-pick by outcome.
        by_version={}
        for event in sorted(eligible,key=lambda e:(e['recorded_at'],e['snapshot_id'])):
            by_version[event['model_version']]=event
        for event in by_version.values():
            trace=event['trace'];y=int(result['home_score']>result['away_score']);margin=result['home_score']-result['away_score'];stages=[];previous=None
            for stage in trace['stages']:
                p=stage['p_home'];error=margin-stage['mean'];ll=-math.log(p if y else 1-p)
                row=dict(name=stage['name'],mean=stage['mean'],p_home=p,error=error,
                         standardized_error=error/trace['distribution']['sd'],logloss=ll,brier=(p-y)**2,squared_error=error**2)
                if previous:
                    row['delta_logloss']=ll-previous['logloss'];row['delta_squared_error']=error**2-previous['squared_error']
                stages.append(row);previous=row
            scored.append(dict(game_id=gid,date=result['date'],home=result['home'],away=result['away'],
                model_version=event['model_version'],forecast_sha256=event['sha256'],result_sha256=result['sha256'],
                predicted_at=event['recorded_at'],forecast_tip=trace['tip'],actual_tip=result['tip'],
                home_score=result['home_score'],away_score=result['away_score'],outcome=y,
                inputs=trace['inputs'],stages=stages))
    return scored,excluded


def aggregate(rows):
    if not rows:return dict(games=0)
    n=len(rows);bins=[]
    for i in range(10):
        group=[r for r in rows if i/10<=r['p_home']<(i+1)/10 or (i==9 and r['p_home']==1)]
        if group:bins.append(dict(bin=i,n=len(group),predicted=sum(r['p_home'] for r in group)/len(group),observed=sum(r['outcome'] for r in group)/len(group)))
    return dict(games=n,logloss=sum(r['logloss'] for r in rows)/n,brier=sum(r['brier'] for r in rows)/n,
        margin_mae=sum(abs(r['error']) for r in rows)/n,mean_error=sum(r['error'] for r in rows)/n,
        standardized_bias=sum(r['standardized_error'] for r in rows)/n,
        standardized_second_moment=sum(r['standardized_error']**2 for r in rows)/n,
        ece=sum(b['n']*abs(b['predicted']-b['observed']) for b in bins)/n,bins=bins,
        delta_logloss=sum(r.get('delta_logloss',0) for r in rows)/n,
        delta_squared_error=sum(r.get('delta_squared_error',0) for r in rows)/n)


def report(events):
    games,excluded=evaluate(events);groups=defaultdict(list);teams=defaultdict(list);strata=defaultdict(list)
    for g in games:
        for stage in g['stages']:
            row=dict(stage,outcome=g['outcome']);key=(g['model_version'],stage['name']);groups[key].append(row)
            for label in ['all', 'b2b' if g['inputs'].get('home_b2b') or g['inputs'].get('away_b2b') else 'non_b2b']:
                strata[(*key,label)].append(row)
        last=g['stages'][-1]
        for side,sign in [('home',1),('away',-1)]:
            teams[(g['model_version'],g[side])].append(dict(game_id=g['game_id'],date=g['date'],error=sign*last['error'],standardized_error=sign*last['standardized_error']))
    return dict(schema=1,activation=events[0]['recorded_at'] if events else None,ledger_head=events[-1]['sha256'] if events else None,
        forecast_records=sum(e['kind']=='forecast' for e in events),result_records=sum(e['kind']=='result' for e in events),
        eligible_games=len({g['game_id'] for g in games}),evaluated_forecasts=len(games),excluded=excluded,
        stage_metrics=[dict(model_version=k[0],stage=k[1],**aggregate(v)) for k,v in groups.items()],
        strata=[dict(model_version=k[0],stage=k[1],group=k[2],**aggregate(v)) for k,v in strata.items()],
        team_residuals=[dict(model_version=k[0],team=k[1],games=len(v),mean_error=sum(r['error'] for r in v)/len(v),history=v) for k,v in teams.items()],
        largest_errors=sorted(games,key=lambda g:g['stages'][-1]['logloss'],reverse=True)[:20],
        limitations=['Primary cohort requires actual recording at or before T-24h. No historical backfill.',
        'Stages are ordered ablations with shared variance, not causal attributions.',
        'Production heuristic model only; Additive, matchup interactions and score totals are not deployed.',
        'Snapshot seed priors/player values/injuries are not independently point-in-time validated.',
        'Hash chain checks integrity but is not an independent trusted timestamp.',
        'Small sample diagnostics are descriptive; no automatic model or weight updates.']),games


def update_trace(root, snapshot, version, app, now=None):
    now=(now or datetime.now(timezone.utc)).astimezone(timezone.utc);stamp=now.isoformat()
    traces=json.loads((snapshot/'data/prediction_traces.json').read_text())
    schedule=json.loads((snapshot/'data/schedule.json').read_text())
    code_files=['pipeline/model.py','pipeline/config.py','pipeline/data_fetcher.py','pipeline/build_daily.py','deploy/trace.py']
    source=dict(code={p:hashlib.sha256((app/p).read_bytes()).hexdigest() for p in code_files},
                seed={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((snapshot/'data/seed').glob('*.csv'))})
    model_version=digest(source['code']);folder=root/'forward_ledger';folder.mkdir(exist_ok=True)
    path=folder/'events.jsonl'
    with (folder/'lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);events=load_events(path);keys={e['event_id'] for e in events};pending=[]
        def add(body):
            if body['event_id'] in keys:return
            keys.add(body['event_id']);body=dict(body,recorded_at=stamp,previous_sha256=(pending[-1] if pending else events[-1])['sha256'] if pending or events else '0'*64)
            pending.append(dict(body,sha256=digest(body)))
        if not events:add(dict(kind='activation',event_id='activation',policy='T-24h; latest eligible forecast per model version',schema=1))
        activation=timestamp((events or pending)[0]['recorded_at'])
        add(dict(kind='snapshot',event_id='snapshot:'+version,snapshot_id=version,model_version=model_version,source=source))
        scheduled={g['id']:g for g in schedule}
        for trace in traces:
            gid=trace['game_id'];g=scheduled[gid];tip=timestamp(trace['tip'])
            if g['status']=='final' or tip<=now or tip>now+timedelta(days=7):continue
            stages=trace['stages'];dist=trace['distribution']
            if not stages or dist['sd']<=0 or dist['df']<=2:raise ValueError('Invalid trace distribution')
            if any(not math.isfinite(s['mean']) or not 0<s['p_home']<1 for s in stages):raise ValueError('Invalid trace prediction')
            if abs(stages[-1]['p_home']-float(g['p_home']))>.000501 or abs(stages[-1]['mean']+float(g['spread']))>.050001:
                raise ValueError('Trace and published forecast mismatch')
            add(dict(kind='forecast',event_id=f'forecast:{version}:{gid}',snapshot_id=version,model_version=model_version,trace=trace,
                     cutoff=(tip-timedelta(hours=24)).isoformat(),eligible_at_capture=now<=tip-timedelta(hours=24)))
        for g in schedule:
            if g['status']!='final' or timestamp(g['tip'])<activation:continue
            hs,away=int(g['hs']),int(g['as'])
            if hs==away or min(hs,away)<0 or timestamp(g['tip'])>now:raise ValueError('Invalid final result')
            body=dict(kind='result',game_id=g['id'],date=g['date'],tip=g['tip'],home=g['home'],away=g['away'],home_score=hs,away_score=away)
            latest=next((e for e in reversed(events+pending) if e['kind']=='result' and e['game_id']==g['id']),None)
            if latest and all(latest[k]==v for k,v in body.items()):continue
            add(dict(body,event_id=f"result:{g['id']}:{version}"))
        # Evaluate first; invalid events cannot partially append before validation completes.
        summary,scored=report(events+pending)
        for name,value in [('trace_report',summary),('trace_games',scored)]:
            (snapshot/f'data/{name}.json').write_bytes(canonical(value))
        with path.open('a') as f:
            for event in pending:f.write(canonical(event).decode()+'\n')
            f.flush();os.fsync(f.fileno())
        return summary
