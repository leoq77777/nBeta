"""Fail builds before export when probability or schedule contracts are violated."""
from collections import Counter, defaultdict
import math


def validate_artifacts(teams, schedule, win_dist):
    def require(ok, message):
        if not ok:
            raise ValueError(message)
    counts = Counter()
    for g in schedule:
        counts.update((g['home'], g['away']))
        require(0 <= float(g['p_home']) <= 1, 'Invalid game probability')
    require(len(teams) == 30, 'Expected 30 teams')
    funnel = ['p_playoffs','p_r2','p_cf','p_finals','p_title']
    for t in teams:
        require(math.isclose(float(t['proj_w'])+float(t['proj_l']), counts[t['abbr']], abs_tol=.11), 'Win/loss schedule mismatch')
        require(float(t['proj_w']) >= int(t['w'])-.1, 'Projected wins below realized wins')
        ps = [float(t[k]) for k in funnel]
        require(all(0 <= p <= 1 for p in ps) and ps == sorted(ps,reverse=True), 'Invalid playoff funnel')
        require(abs(sum(float(t[f'seed_{i}']) for i in range(1,16))-1) < .002, 'Seed probabilities do not sum to one')
    for key,total in zip(funnel,[16,8,4,2,1]):
        require(abs(sum(float(t[key]) for t in teams)-total)<.003, f'{key} total mismatch')
    require(abs(sum(float(t['proj_w']) for t in teams)-len(schedule))<1.6, 'Total projected wins mismatch')
    for t in teams:
        require(0 <= float(t['p_top6']) + float(t['p_playin']) <= 1.0002, 'Invalid qualification paths')
        require(float(t['p_top6']) <= float(t['p_playoffs']) + .0001, 'Top six must reach playoffs')
        final = [g for g in schedule if g['status']=='final' and t['abbr'] in (g['home'],g['away'])]
        require(int(t['w'])+int(t['l'])==len(final), 'Realized record mismatch')
    pmf = defaultdict(float)
    prior_pmf = defaultdict(float)
    for row in win_dist:
        require(float(row['p']) >= 0, 'Negative PMF')
        pmf[row['abbr']] += float(row['p'])
        if 'p_prior' in row:
            prior_pmf[row['abbr']] += float(row['p_prior'])
    require(set(pmf)=={t['abbr'] for t in teams}, 'Missing team PMF')
    require(all(abs(p-1)<.00001 for p in pmf.values()), 'PMF does not sum to one')
    require(all(abs(p-1)<.00001 for p in prior_pmf.values()), 'Prior PMF does not sum to one')
    require(abs(sum(float(t['rating']) for t in teams))<.2, 'Ratings not centered')
