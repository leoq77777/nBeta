"""Production feature definitions promoted verbatim from the accepted Additive experiment.
No training or target-game diagnostics are performed here.
"""

from __future__ import annotations

import math, heapq

from collections import Counter, defaultdict, deque

import numpy as np

def ndtr(x):
    return .5 * math.erfc(-float(x) / math.sqrt(2))

# Source SHA256 benchmark/data.py 5f15060151f239229cd87bdb2cb7aa6d5b080b43f0e3ba683ecc712daf4b5fa0

TEAMS=sorted(['ATL','BOS','BKN','CHA','CHI','CLE','DAL','DEN','DET','GS','HOU','IND','LAC','LAL','MEM','MIA','MIL','MIN','NOP','NY','OKC','ORL','PHI','PHX','POR','SAC','SA','TOR','UTA','WSH'])

def make_features(games,asof=None):
    """Only outcomes whose assumed availability precedes scheduled tip minus 24h."""
    hist=defaultdict(lambda:deque(maxlen=100));season_counts=Counter();pending=[]
    X=[];audit=[];previous_tip={}
    def update(g):
        year=g['season']
        for ab,m in [(g['home'],g['margin']),(g['away'],-g['margin'])]:
            hist[ab].append((g['tip_ts'],m,g['total'],int(m>0)))
            season_counts[(year,ab)]+=1
    for index,g in enumerate(games):
        cutoff=g['tip_ts']-24*3600
        if asof is not None:cutoff=min(cutoff,asof)
        while pending and pending[0][0]<=cutoff:
            _,_,completed=heapq.heappop(pending);update(completed)
        h=list(hist[g['home']]);a=list(hist[g['away']])
        def mean(rows,col,n,default):return float(np.mean([r[col] for r in rows[-n:]])) if rows else default
        # Known previous-game times determine schedule rest even if its score is not available.
        # Only already available results contribute performance/history features.
        prev_h=previous_tip.get(g['home']);prev_a=previous_tip.get(g['away'])
        rest_h=min(7,max(0,(g['tip_ts']-prev_h)/86400-1)) if prev_h is not None else 3
        rest_a=min(7,max(0,(g['tip_ts']-prev_a)/86400-1)) if prev_a is not None else 3
        h_b2b=int(prev_h is not None and g['tip_ts']-prev_h<36*3600)
        a_b2b=int(prev_a is not None and g['tip_ts']-prev_a<36*3600)
        X.append([1-g['neutral'],rest_h-rest_a,h_b2b,a_b2b,
                  *[mean(h,1,n,0)-mean(a,1,n,0) for n in [5,20,60]],
                  mean(h,3,20,.5)-mean(a,3,20,.5),
                  (mean(h,2,20,210)+mean(a,2,20,210))/2,
                  (float(np.std([r[1] for r in h[-20:]])) if len(h)>1 else 12)+(float(np.std([r[1] for r in a[-20:]])) if len(a)>1 else 12),
                  season_counts[(g['season'],g['home'])]-season_counts[(g['season'],g['away'])],
                  (season_counts[(g['season'],g['home'])]+season_counts[(g['season'],g['away'])])/164,
                  int(not g['neutral'] and g['home'] in {'DEN','UTA'})])
        latest=max([r[0]+6*3600 for r in h+a],default=0)
        if latest>cutoff:raise ValueError('Outcome leakage')
        audit.append(dict(id=g['id'],cutoff=cutoff,latest_feature_result_available=latest))
        previous_tip[g['home']]=g['tip_ts'];previous_tip[g['away']]=g['tip_ts']
        heapq.heappush(pending,(g['available_ts'],index,g))
    arr=np.asarray(X,dtype=float);arr[:,9]/=2
    return arr,audit

# Source SHA256 benchmark/player_data.py d71f584c693247c1fb49177aca7cf5ba94b9b9e4bdbe494a7a943b9bde00f1bf

PLAYER_FEATURES=['estimated_minutes','points36','fga36','fg_pct_shrunk','three_pa36','three_pct_shrunk','fta36','ft_pct_shrunk','reb36','ast36','stl36','blk36','tov36','fouls36','recent_minus_long_minutes','observed_games','days_since_seen','participation_5','position_G','position_F','position_C']

HISTORY_FEATURES=['current_win_pct_shrunk','current_games_fraction','current_mean_margin']+[f'lag{k}_{field}' for k in [1,2,3] for field in ['win_pct','margin','games_fraction']]

def build_inputs(games,boxes,slots=12,asof=None):
    """No current-game box row is inspected until AFTER its input has been constructed."""
    player_hist=defaultdict(lambda:deque(maxlen=20));minute_hist=defaultdict(lambda:deque(maxlen=20));last_team={};last_seen={};positions={};names={}
    pools=defaultdict(set);records=defaultdict(lambda:[0,0,0.]);pending=[]
    tokens=np.zeros((len(games),2,slots,len(PLAYER_FEATURES)),np.float32);weights=np.zeros((len(games),2,slots),np.float32);mask=np.ones((len(games),2,slots),bool)
    history=np.zeros((len(games),2,len(HISTORY_FEATURES)),np.float32);ids=np.full((len(games),2,slots),'',dtype='<U16');audit=[]
    def update(g):
        for team in [g['home'],g['away']]:
            margin=g['margin'] if team==g['home'] else -g['margin']
            r=records[(team,g['season'])];r[0]+=int(margin>0);r[1]+=1;r[2]+=margin
            obs=boxes.get(g['id'],{}).get(team)
            if not obs:continue
            present={p['id']:p for p in obs}
            for p in obs:
                pid=p['id']
                if pid in last_team and last_team[pid]!=team:pools[last_team[pid]].discard(pid)
                last_team[pid]=team;pools[team].add(pid);last_seen[pid]=g['available_ts'];positions[pid]=p['position'];names[pid]=p['name']
                if p['played']:player_hist[pid].append(p['stats'])
            for pid in pools[team]:minute_hist[(team,pid)].append(present[pid]['stats'][0] if pid in present else 0.)
    for i,g in enumerate(games):
        cutoff=min(g['tip_ts']-86400,asof) if asof is not None else g['tip_ts']-86400
        while pending and pending[0][0]<=cutoff:
            _,_,old=heapq.heappop(pending);update(old)
        latest=0
        for side,team in enumerate([g['home'],g['away']]):
            features=[]
            for pid in pools[team]:
                mh=list(minute_hist[(team,pid)]);recent=mh[-5:];long=float(np.mean(mh)) if mh else 0
                expected=.7*float(np.mean(recent))+.3*long if recent else 0
                if expected<=.01:continue
                ph=np.asarray(player_hist[pid],float)
                if not len(ph):continue
                sums=ph.sum(axis=0);minutes=max(sums[0],1);rate=lambda col:float(sums[col]/minutes*36)
                fg=(sums[2]+7)/(sums[3]+15);three=(sums[4]+1.75)/(sums[5]+5);ft=(sums[6]+3.5)/(sums[7]+5)
                pos=positions[pid]
                f=[expected,rate(1),rate(3),fg,rate(5),three,rate(7),ft,*[rate(c) for c in range(8,14)],float(np.mean(recent))-long,len(ph),min(365,(cutoff-last_seen[pid])/86400),float(np.mean(np.asarray(recent)>0)),int('G' in pos),int('F' in pos),int('C' in pos)]
                features.append((expected,pid,f));latest=max(latest,last_seen[pid])
            chosen=sorted(features,key=lambda x:(-x[0],x[1]))[:slots]
            total=sum(x[0] for x in chosen)
            for j,(expected,pid,f) in enumerate(chosen):
                tokens[i,side,j]=f;weights[i,side,j]=expected/total;mask[i,side,j]=False;ids[i,side,j]=pid
            r=records[(team,g['season'])]
            h=[(r[0]+4)/(r[1]+8),r[1]/82,r[2]/max(r[1],1)]
            for lag in [1,2,3]:
                old=records[(team,g['season']-lag)];h.extend([(old[0]+4)/(old[1]+8),old[2]/max(old[1],1),old[1]/82])
            history[i,side]=h
        if latest>cutoff:raise ValueError('Player feature leakage')
        audit.append(dict(id=g['id'],cutoff=cutoff,latest_player_source_available=latest,home_proxy_size=int((~mask[i,0]).sum()),away_proxy_size=int((~mask[i,1]).sum())))
        heapq.heappush(pending,(g['available_ts'],i,g))
    return dict(players=tokens,weights=weights,mask=mask,history=history,player_ids=ids),audit


# Source SHA256 benchmark/matchup.py 62ee1080e7213f98d055dab1b74d20d58fb4e366e902f49d17a5cd616edbcbb5

DEFAULT = np.array([110,88,.52,.36,.27,.55,.12,.08,.05,45.],float)

def profile(rows):
    s=np.sum([p['stats'] for p in rows],axis=0)
    if not np.isfinite(s).all() or s[0]<=0 or s[3]<=0:
        raise ValueError('Invalid accepted box')
    f=240/s[0]; fga=s[3]
    return np.array([s[1]*f,s[3]*f,(s[2]+.5*s[4])/fga,s[5]/fga,s[7]/fga,
                     s[9]/max(s[2],1),s[12]/max(fga+s[12],1),s[10]*f/100,s[11]*f/100,s[8]*f])

def team_features(games,boxes,asof=None):
    history=defaultdict(lambda:deque(maxlen=20));pending=[];out=[];audit=[];latest={}
    for i,g in enumerate(games):
        cutoff=min(g['tip_ts']-86400,asof) if asof is not None else g['tip_ts']-86400
        while pending and pending[0][0]<=cutoff:
            _,_,old=heapq.heappop(pending);b=boxes.get(old['id'],{})
            if old['home'] not in b or old['away'] not in b:continue
            h,a=profile(b[old['home']]),profile(b[old['away']])
            for team,v in [(old['home'],np.r_[h,a]),(old['away'],np.r_[a,h])]:
                history[team].append(v);latest[team]=old['available_ts']
        sides=[]
        for team in (g['home'],g['away']):
            v=list(history[team]);n=len(v)
            sides.append((np.sum(v,axis=0)+5*np.tile(DEFAULT,2))/(n+5) if n else np.tile(DEFAULT,2))
        out.append(sides)
        source=max(latest.get(g['home'],0),latest.get(g['away'],0))
        assert source<=cutoff
        audit.append(dict(id=g['id'],cutoff=cutoff,latest_box_available=source))
        heapq.heappush(pending,(g['available_ts'],i,g))
    return np.array(out),audit

def roster_summary(data):
    p=np.where(data['mask'][...,None],0,data['players']).astype(float)
    w=np.where(data['mask'],0,data['weights']).astype(float)
    w=w/np.maximum(w.sum(axis=2,keepdims=True),1e-12)
    mean=(p*w[...,None]).sum(axis=2)
    sd=np.sqrt(((p-mean[:,:,None,:])**2*w[...,None]).sum(axis=2))
    concentration=[]
    for k in (1,2,4,9):
        contribution=w*np.maximum(p[...,k],0)
        share=contribution/np.maximum(contribution.sum(axis=2,keepdims=True),1e-12)
        concentration.append((share**2).sum(axis=2))
    return mean,np.concatenate([sd,np.stack(concentration,axis=2)],axis=2)

# Source SHA256 benchmark/models.py a075263e340cf76cc6a162d818e640cc62da922e76a58086bec22fe0d5e191c5

INDEX={t:i for i,t in enumerate(TEAMS)}

class StateFilter:
    def __init__(self,config,h0=2.5):
        self.config=config;self.mean=np.zeros(31);self.mean[-1]=h0
        center=np.eye(30)-np.ones((30,30))/30
        self.cov=np.zeros((31,31));self.cov[:30,:30]=center*config['prior_sd']**2
        self.cov[-1,-1]=.5 if config['h_q'] else 0
        self.noise=config['obs_sd']**2;self.time=None;self.season=None
    def advance(self,when,season):
        if self.season is not None and season!=self.season:
            self.mean[:30]*=.65
            self.cov[:30,:]*=.65;self.cov[:,:30]*=.65
            center=np.eye(30)-np.ones((30,30))/30
            self.cov[:30,:30]+=center*self.config['prior_sd']**2
            self.noise=self.config['obs_sd']**2
            self.time=when
        self.season=season
        if self.time is None:self.time=when
        days=max(0,(when-self.time)/86400)
        if days:
            shrink=.999**(days/2);self.mean[:30]*=shrink
            self.cov[:30,:]*=shrink;self.cov[:,:30]*=shrink
            center=np.eye(30)-np.ones((30,30))/30
            self.cov[:30,:30]+=center*self.config['q']*days/2
            self.cov[-1,-1]+=self.config['h_q']*days
            self.time=when
    def observation(self,g,x):
        z=np.zeros(31);z[INDEX[g['home']]]=1;z[INDEX[g['away']]]=-1;z[-1]=1-g['neutral']
        # Fixed fatigue context is shared between the filter candidates.
        context=.38*np.clip(x[1],-3,3)+1.45*(x[3]-x[2])+.75*x[12]
        return z,context
    def predict(self,g,x):
        z,ctx=self.observation(g,x);mu=float(z@self.mean+ctx);var=float(z@self.cov@z+self.noise)
        return float(ndtr(mu/math.sqrt(var))),mu,math.sqrt(var)
    def update(self,g,x):
        z,ctx=self.observation(g,x);v=self.cov@z;s=float(z@v+self.noise)
        residual=g['margin']-float(z@self.mean+ctx)
        self.mean+=v*(residual/s)
        self.cov-=np.outer(v,v)/s;self.cov=(self.cov+self.cov.T)/2
        rate=self.config['noise_rate']
        if rate:
            noise_observation=max(36,min(900,residual**2-float(z@self.cov@z)))
            self.noise=(1-rate)*self.noise+rate*noise_observation
