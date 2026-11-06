"""Frozen Additive single-game inference. No sklearn/scipy dependency at serving time."""
from __future__ import annotations
import gzip,hashlib,heapq,json,math,re
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
from .additive_features import make_features,team_features,build_inputs,roster_summary,StateFilter,ndtr
from .config import canonical_team
from .verify_seed import name_key


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def matrices(games,boxes,asof=None):
    X,audit=make_features(games,asof=asof);t,ta=team_features(games,boxes,asof=asof)
    data,pa=build_inputs(games,boxes,asof=asof);r,_=roster_summary(data)
    margin=np.c_[X,t[:,0]-t[:,1],r[:,0]-r[:,1],data['history'][:,0]-data['history'][:,1]]
    total=np.c_[X,(t[:,0]+t[:,1])/2,abs(t[:,0]-t[:,1]),(r[:,0]+r[:,1])/2]
    if not np.isfinite(margin).all() or not np.isfinite(total).all():raise ValueError('Nonfinite Additive features')
    return X,margin,total,dict(context=audit,team=ta,player=pa)


def replay(games,X,config,h0,asof=None):
    state=StateFilter(config,h0);pending=[];pred=[]
    for i,g in enumerate(games):
        cutoff=g['tip_ts']-86400
        if asof is not None:cutoff=min(cutoff,asof)
        while pending and pending[0][0]<=cutoff:
            _,j=heapq.heappop(pending);old=games[j]
            state.advance(old['available_ts'],old['season']);state.update(old,X[j])
        state.advance(cutoff,g['season']);pred.append(state.predict(g,X[i]))
        heapq.heappush(pending,(g['available_ts'],i))
    return np.array(pred)


def linear(model,X):
    z=(X-np.array(model['mean']))/np.array(model['scale'])
    return z@np.array(model['coef'])+model['intercept']


def predict(model,games,boxes,asof=None):
    X,fm,ft,audit=matrices(games,boxes,asof)
    base=replay(games,X,model['filter'],model['h0'],asof)
    correction=linear(model['margin'],fm);total=linear(model['total'],ft)
    mu=base[:,1]+correction
    p=np.array([ndtr(m/s) for m,s in zip(mu,base[:,2])])
    return dict(p=p,mean=mu,sd=base[:,2],total=total,base=base,fm=fm,ft=ft,audit=audit)


def raw_boxes(payload,game,aliases):
    accepted={};held=[]
    for team in payload.get('boxscore',{}).get('players',[]):
        ab=canonical_team(team['team']['abbreviation']);players={};reason=None
        if ab not in (game['home'],game['away']):raise ValueError('Box matchup differs')
        section=team.get('statistics',[{}])[0];labels=section.get('names',section.get('labels',[]))
        for p in section.get('athletes',[]):
            dnp=bool(p.get('didNotPlay'));v=dict(zip(labels,p.get('stats',[])))
            def scalar(key):
                value=v.get(key)
                if value in (None,'','--','-'):
                    if dnp:return 0.
                    raise ValueError('unknown statistic')
                parts=str(value).split(':');return float(parts[0])+(float(parts[1])/60 if len(parts)>1 else 0)
            def pair(key):
                value=v.get(key)
                if value in (None,'','--','-'):
                    if dnp:return [0.,0.]
                    raise ValueError('unknown shots')
                return [float(x) for x in str(value).split('-')]
            try:
                values=[scalar('MIN'),scalar('PTS'),*pair('FG'),*pair('3PT'),*pair('FT'),*[scalar(k) for k in ('REB','AST','STL','BLK','TO','PF')]]
                if len(values)!=14 or not np.isfinite(values).all() or min(values)<0:raise ValueError('invalid statistic')
                if any(values[i]>values[i+1] for i in (2,4,6)):raise ValueError('made exceeds attempts')
                if dnp and any(values):raise ValueError('nonzero DNP')
                if values[0]==0 and any(values[1:]):raise ValueError('events without reliable minutes')
            except (ValueError,TypeError):reason='unknown_or_invalid_player_stats';break
            athlete=p['athlete'];pid=aliases.get(str(athlete['id']),str(athlete['id']))
            row=dict(id=pid,name=athlete['displayName'],position=athlete.get('position',{}).get('abbreviation',''),played=not dnp and values[0]>0,stats=values)
            if pid in players and players[pid]['stats']!=values:reason='alias_conflict';break
            players[pid]=row
        names=[name_key(p['name']) for p in players.values()]
        if len(names)!=len(set(names)):reason='ambiguous_identity'
        rows=list(players.values());mins=sum(p['stats'][0] for p in rows);pts=sum(p['stats'][1] for p in rows)
        status=payload.get('header',{}).get('competitions',[{}])[0].get('status',{})
        period=status.get('period')
        if period is None:
            label=' '.join(str(status.get('type',{}).get(k,'')) for k in ('detail','shortDetail','altDetail'))
            overtime=re.search(r'(?:(\d+)\s*)?OT\b',label)
            period=4+(int(overtime.group(1) or 1) if overtime else 0)
        expected_minutes=240+25*max(0,int(period)-4)
        expected=game['hs'] if ab==game['home'] else game['away_score']
        if not rows or pts!=expected or abs(mins-expected_minutes)>len(rows)+1:reason=reason or 'score_or_minutes_not_conserved'
        if reason:held.append(dict(game_id=game['id'],team=ab,reason=reason))
        else:accepted[ab]=rows
    return accepted,held


def activate(root,snapshot,now=None):
    bundle=root/'models/active';path=bundle/'model.json'
    if not path.exists():
        if bundle.is_symlink() or bundle.exists():raise ValueError('Configured Additive bundle missing')
        return None
    now=(now or datetime.now(timezone.utc)).astimezone(timezone.utc);asof=now.timestamp();model=json.loads(path.read_text())
    if sha(bundle/'history.json.gz')!=model['history_sha256']:raise ValueError('Additive history integrity mismatch')
    if sha(Path(__file__).with_name('additive_features.py'))!=model['feature_code_sha256']:raise ValueError('Additive feature code mismatch')
    history=json.load(gzip.open(bundle/'history.json.gz','rt'));games=history['games'];boxes=history['boxes'];ids={g['id'] for g in games}
    schedule=json.loads((snapshot/'data/schedule.json').read_text());sources=[];held=[];team_count=0;live=[]
    for g in schedule:
        tip=datetime.fromisoformat(g['tip'].replace('Z','+00:00')).timestamp()
        if g['id'] in ids:raise ValueError('Live game overlaps frozen training history')
        final=g['status']=='final';season=datetime.fromtimestamp(tip,timezone.utc).year+(datetime.fromtimestamp(tip,timezone.utc).month>=8)
        row=dict(id=g['id'],season=season,tip=g['tip'],tip_ts=tip,date=g['date'],home=g['home'],away=g['away'],neutral=int(g.get('neutral') or 0),
                 hs=int(g['hs']) if final else None,away_score=int(g['as']) if final else None,margin=int(g['hs'])-int(g['as']) if final else None,total=int(g['hs'])+int(g['as']) if final else None,available_ts=tip+21600 if final else float('inf'))
        live.append(row)
        if final:
            cache=root/'player-box-cache'/f"{g['id']}.json"
            if not cache.exists():raise ValueError(f"Required live player box missing: {g['id']}")
            payload=json.loads(cache.read_text());b,h=raw_boxes(payload,row,history['aliases']);boxes[g['id']]=b;held.extend(h);team_count+=len(b)
            sources.append(dict(game_id=g['id'],sha256=sha(cache),retrieved_at=datetime.fromtimestamp(cache.stat().st_mtime,timezone.utc).isoformat()))
    finals=sum(g['status']=='final' for g in schedule)
    if not finals or team_count/(2*finals)<.9:raise ValueError('Insufficient validated live Additive player data')
    games=sorted(games+live,key=lambda g:(g['tip_ts'],g['id']))
    forecast=predict(model,games,boxes,asof)
    lookup={g['id']:i for i,g in enumerate(games)};legacy=json.loads((snapshot/'data/prediction_traces.json').read_text())
    (snapshot/'data/legacy_prediction_traces.json').write_text(json.dumps(legacy,allow_nan=False))
    traces=[];model_sha=sha(path);group_slices={'context_residual':(0,13),'team_process':(13,33),'players':(33,54),'team_history':(54,66)}
    for g in schedule:
        if g['status']=='final':continue
        i=lookup[g['id']];mu=float(forecast['mean'][i]);sd=float(forecast['sd'][i]);tm=float(forecast['total'][i]);ts=model['total_sd'];rho=model['rho'];prob=float(np.clip(forecast['p'][i],1e-6,1-1e-6))
        z=(forecast['fm'][i]-np.array(model['margin']['mean']))/np.array(model['margin']['scale']);terms=z*np.array(model['margin']['coef'])
        contributions={k:float(terms[a:b].sum()) for k,(a,b) in group_slices.items()}
        baseline=float(forecast['base'][i,1]);team=baseline+model['margin']['intercept']+contributions['context_residual']+contributions['team_process']+contributions['team_history']
        stage=[dict(name=n,mean=m,p_home=float(np.clip(ndtr(m/sd),1e-6,1-1e-6))) for n,m in [('dynamic_baseline',baseline),('team_features',team),('additive',mu)]]
        idx=forecast['audit']['context'][i];pidx=forecast['audit']['player'][i]
        trace=dict(game_id=g['id'],date=g['date'],tip=g['tip'],home=g['home'],away=g['away'],model_name='Additive v1',artifact_sha256=model_sha,
          inputs=dict(home_b2b=int(forecast['fm'][i,2]),away_b2b=int(forecast['fm'][i,3]),feature_cutoff=min(games[i]['tip_ts']-86400,asof),latest_result_available=idx['latest_feature_result_available'],latest_player_available=pidx['latest_player_source_available'],group_contributions=contributions,margin_features=forecast['fm'][i].tolist(),total_features=forecast['ft'][i].tolist()),
          distribution=dict(family='normal_margin',sd=sd),stages=stage,joint_score=dict(total_mean=tm,total_sd=ts,rho=rho,home_mean=(tm+mu)/2,away_mean=(tm-mu)/2),unsupported_stages=['true_lineup_interactions'])
        traces.append(trace)
        g.update(legacy_p_home=g['p_home'],legacy_spread=g['spread'],p_home=round(prob,6),spread=round(-mu,3),prediction_model='Additive v1',prediction_model_sha256=model_sha,home_score_mean=round((tm+mu)/2,2),away_score_mean=round((tm-mu)/2,2),total_mean=round(tm,2),total_sd=round(ts,3),margin_sd=round(sd,3))
        if g.get('market_spread') is not None:g['edge_pts']=round(float(g['market_spread'])-float(g['spread']),3)
    (snapshot/'data/schedule.json').write_text(json.dumps(schedule,indent=2,allow_nan=False));(snapshot/'data/prediction_traces.json').write_text(json.dumps(traces,indent=2,allow_nan=False))
    import csv
    with (snapshot/'data/schedule.csv').open('w',newline='') as f:
        fields=list(dict.fromkeys(k for g in schedule for k in g));writer=csv.DictWriter(f,fields);writer.writeheader();writer.writerows(schedule)
    metadata=dict(model_name='Additive v1',artifact_sha256=model_sha,training_games=model['training_games'],training_through=model['training_through'],generated_at=now.isoformat(),season_simulation_model='legacy_student_t',live_validated_team_boxes=team_count,live_held_team_boxes=held,sources=sources,feature_audit_sha256=hashlib.sha256(json.dumps(forecast['audit'],sort_keys=True).encode()).hexdigest())
    (snapshot/'data/additive_model.json').write_text(json.dumps(metadata,indent=2,allow_nan=False))
    return metadata
