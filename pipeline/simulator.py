"""
Vectorized Two-Stage Monte Carlo Season & Playoff Simulator for n-Beta (n-Bet-a).

Runs 100,000 full-season simulations in seconds using NumPy vectorization:
- Stage 1 (Epistemic Parameter Uncertainty): Draws each team's true baseline strength
  from its Kalman posterior N(mu_i, gamma^2 * sigma_i^2) in each simulated universe.
- Stage 2 (In-season Schedule + Injury Recovery): Simulates all remaining regular-season
  games with heavy-tailed Student-t game noise, in-season rating updates, Play-In
  Tournament (seeds 7–10), and Best-of-7 NBA Playoff series with Playoff Regime Switching
  (star rotation compression).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Tuple

import numpy as np

from .config import TEAM_VOLATILITY_MULT, ModelConfig
from .model import compute_context_adjustment


def _series_win_prob_matrix(
    r_high: np.ndarray,
    r_low: np.ndarray,
    hca_high: float,
    hca_low: float,
    sigma_game: float,
    df: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    Vectorized simulation of a 2-2-1-1-1 Best-of-7 NBA Playoff series across N universes.
    Home pattern for higher seed: [1, 1, 0, 0, 1, 0, 1].
    Returns boolean array of length N (True if higher seed wins 4 games first).
    """
    n_sims = r_high.shape[0]
    wins_high = np.zeros(n_sims, dtype=np.int8)
    wins_low = np.zeros(n_sims, dtype=np.int8)
    active = np.ones(n_sims, dtype=bool)

    scale = sigma_game * np.sqrt((df - 2.0) / df)
    home_pattern = (True, True, False, False, True, False, True)

    for is_high_home in home_pattern:
        if not np.any(active):
            break
        n_act = int(np.sum(active))
        if is_high_home:
            expected_diff = (r_high[active] - r_low[active]) + hca_high
        else:
            expected_diff = (r_high[active] - r_low[active]) - hca_low

        noise = rng.standard_t(df=df, size=n_act) * scale
        high_won_game = (expected_diff + noise) > 0.0

        idx = np.flatnonzero(active)
        wins_high[idx[high_won_game]] += 1
        wins_low[idx[~high_won_game]] += 1
        active = (wins_high < 4) & (wins_low < 4)

    return wins_high >= 4


def run_two_stage_monte_carlo(
    teams_meta: Dict[str, Dict[str, Any]],
    kalman_state: Dict[str, Any],
    team_injury_summary: Dict[str, Dict[str, Any]],
    schedule: List[Dict[str, Any]],
    cfg: ModelConfig,
) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Execute N = cfg.n_sims (100,000) two-stage Monte Carlo simulations of the remainder
    of the regular season, Play-In tournament, and 4-round NBA Playoffs.
    """
    rng = np.random.default_rng(cfg.random_seed)
    n_sims = cfg.n_sims
    if n_sims <= 0:
        raise ValueError("n_sims must be positive")

    abbrs = sorted(teams_meta.keys())
    n_teams = len(abbrs)
    abbr_to_idx = {ab: i for i, ab in enumerate(abbrs)}

    mu_vec = np.array([kalman_state["mu"][ab] for ab in abbrs], dtype=np.float64)
    sd_vec = np.array([kalman_state["sd"][ab] for ab in abbrs], dtype=np.float64)
    active_vec = np.array([kalman_state["active_rating"][ab] for ab in abbrs], dtype=np.float64)
    cur_wins = np.array([kalman_state["wins"][ab] for ab in abbrs], dtype=np.int32)

    # Star leverage bonus in playoffs (centered around league average top-2 star value)
    top2_vals = np.array([team_injury_summary.get(ab, {}).get("top2_star_value", 2.0) for ab in abbrs])
    star_playoff_bonus = (cfg.playoff_star_leverage - 1.0) * (top2_vals - np.mean(top2_vals)) * 2.2

    # Stage 1: Sample Epistemic Team Ratings across N = 100,000 universes
    # Shape: (n_teams, n_sims)
    epistemic_sd = (cfg.sim_epistemic_scale * sd_vec)[:, None]
    sim_ratings = mu_vec[:, None] + rng.normal(0.0, 1.0, size=(n_teams, n_sims)) * epistemic_sd
    sim_wins = np.broadcast_to(cur_wins[:, None], (n_teams, n_sims)).copy()

    upcoming_games = [g for g in schedule if g["status"] != "final"]
    first_date = min((g["date"] for g in upcoming_games), default="2026-11-04")
    dt_first = datetime.strptime(first_date, "%Y-%m-%d")

    df = cfg.student_t_df
    injury_gap = (mu_vec - active_vec)[:, None]  # Positive gap when injured players are out

    # Pre-sample stochastic Weibull recovery horizon (in days) for each team's injured stars
    recovery_tau = rng.weibull(cfg.injury_recovery_weibull_k, size=(n_teams, n_sims)) * 18.0 + 4.0

    # Stage 2: Step through all remaining regular-season games
    for g in upcoming_games:
        h_idx = abbr_to_idx[g["home"]]
        a_idx = abbr_to_idx[g["away"]]
        days_ahead = max(0.0, float((datetime.strptime(g["date"], "%Y-%m-%d") - dt_first).days))

        # Smooth injury discount decay based on each universe's stochastic recovery horizon
        disc_h = injury_gap[h_idx] * np.exp(-days_ahead / recovery_tau[h_idx])
        disc_a = injury_gap[a_idx] * np.exp(-days_ahead / recovery_tau[a_idx])

        r_h = sim_ratings[h_idx] - disc_h
        r_a = sim_ratings[a_idx] - disc_a

        ctx = compute_context_adjustment(g, cfg, is_playoffs=False)
        exp_diff = (r_h - r_a) + ctx

        vol_mult = 0.5 * (TEAM_VOLATILITY_MULT.get(g["home"], 1.0) + TEAM_VOLATILITY_MULT.get(g["away"], 1.0))
        scale = cfg.base_game_sd * vol_mult * np.sqrt((df - 2.0) / df)

        margin = exp_diff + rng.standard_t(df=df, size=n_sims) * scale
        home_won = margin > 0.0

        sim_wins[h_idx, home_won] += 1
        sim_wins[a_idx, ~home_won] += 1

        # Mild in-simulation game-by-game rating evolution (matching reference architecture)
        capped_innov = np.clip(margin - exp_diff, -cfg.mov_cap, cfg.mov_cap)
        delta = (cfg.sim_in_season_k / cfg.obs_noise_sigma) * capped_innov
        sim_ratings[h_idx] += delta
        sim_ratings[a_idx] -= delta

    # End-of-regular-season rating mean
    rating_end = np.mean(sim_ratings, axis=1)

    # Playoff & Seeding Funnel Counters: shape (n_teams,)
    seed_counts = np.zeros((n_teams, 15), dtype=np.int32)
    top6_counts = np.zeros(n_teams, dtype=np.int32)
    playin_counts = np.zeros(n_teams, dtype=np.int32)
    playoffs_counts = np.zeros(n_teams, dtype=np.int32)
    r2_counts = np.zeros(n_teams, dtype=np.int32)
    cf_counts = np.zeros(n_teams, dtype=np.int32)
    finals_counts = np.zeros(n_teams, dtype=np.int32)
    title_counts = np.zeros(n_teams, dtype=np.int32)

    # Best regular-season record across the whole league (tie-broken by tiny jitter)
    tie_jitter = rng.uniform(-0.01, 0.01, size=(n_teams, n_sims))
    wins_with_tb = sim_wins + tie_jitter
    best_team_per_sim = np.argmax(wins_with_tb, axis=0)
    best_counts = np.bincount(best_team_per_sim, minlength=n_teams)

    # Apply Playoff Regime Switching (rotation compression boosts star-heavy teams)
    playoff_ratings = sim_ratings + star_playoff_bonus[:, None]
    po_hca = cfg.home_court_advantage + cfg.playoff_hca_boost

    conf_indices = {
        "East": np.array([abbr_to_idx[ab] for ab in abbrs if teams_meta[ab]["conf"] == "East"], dtype=np.int32),
        "West": np.array([abbr_to_idx[ab] for ab in abbrs if teams_meta[ab]["conf"] == "West"], dtype=np.int32),
    }

    sim_range = np.arange(n_sims)
    conf_champs: Dict[str, np.ndarray] = {}
    conf_champ_wins: Dict[str, np.ndarray] = {}

    for conf_name, c_idx in conf_indices.items():
        # Rank the 15 teams in this conference for each of the 100,000 simulations
        conf_wins = wins_with_tb[c_idx, :]  # (15, n_sims)
        order = np.argsort(-conf_wins, axis=0)  # (15, n_sims)
        seeded_teams = c_idx[order]  # seeded_teams[s_rank, sim_id] = global team index

        for s_rank in range(15):
            t_in_rank = seeded_teams[s_rank]
            counts = np.bincount(t_in_rank, minlength=n_teams)
            seed_counts[:, s_rank] += counts
            if s_rank < 6:
                top6_counts += counts
                playoffs_counts += counts
            elif s_rank < 10:
                playin_counts += counts

        # Play-In Tournament (Seeds 7, 8, 9, 10 -> indices 6, 7, 8, 9)
        t7, t8, t9, t10 = seeded_teams[6], seeded_teams[7], seeded_teams[8], seeded_teams[9]
        r7 = playoff_ratings[t7, sim_range]
        r8 = playoff_ratings[t8, sim_range]
        r9 = playoff_ratings[t9, sim_range]
        r10 = playoff_ratings[t10, sim_range]

        scale_pi = cfg.base_game_sd * np.sqrt((df - 2.0) / df)
        # 7 vs 8 game (at 7)
        w7v8 = ((r7 - r8 + po_hca) + rng.standard_t(df=df, size=n_sims) * scale_pi) > 0.0
        seed7_winner = np.where(w7v8, t7, t8)
        loser_7v8 = np.where(w7v8, t8, t7)

        # 9 vs 10 game (at 9)
        w9v10 = ((r9 - r10 + po_hca) + rng.standard_t(df=df, size=n_sims) * scale_pi) > 0.0
        winner_9v10 = np.where(w9v10, t9, t10)

        # 8th seed game: loser of 7v8 hosts winner of 9v10
        r_host8 = playoff_ratings[loser_7v8, sim_range]
        r_vis8 = playoff_ratings[winner_9v10, sim_range]
        w8_game = ((r_host8 - r_vis8 + po_hca) + rng.standard_t(df=df, size=n_sims) * scale_pi) > 0.0
        seed8_winner = np.where(w8_game, loser_7v8, winner_9v10)

        playoffs_counts += np.bincount(seed7_winner, minlength=n_teams)
        playoffs_counts += np.bincount(seed8_winner, minlength=n_teams)

        # First Round Brackets: (1 vs 8), (4 vs 5), (3 vs 6), (2 vs 7)
        s1, s2, s3, s4, s5, s6 = (
            seeded_teams[0], seeded_teams[1], seeded_teams[2],
            seeded_teams[3], seeded_teams[4], seeded_teams[5],
        )
        s7, s8 = seed7_winner, seed8_winner

        def play_round_pair(team_a: np.ndarray, team_b: np.ndarray) -> np.ndarray:
            # Higher regular-season wins gets home-court advantage
            wa = wins_with_tb[team_a, sim_range]
            wb = wins_with_tb[team_b, sim_range]
            a_is_high = wa >= wb
            high_t = np.where(a_is_high, team_a, team_b)
            low_t = np.where(a_is_high, team_b, team_a)
            r_hi = playoff_ratings[high_t, sim_range]
            r_lo = playoff_ratings[low_t, sim_range]
            hi_wins = _series_win_prob_matrix(r_hi, r_lo, po_hca, po_hca, cfg.base_game_sd, df, rng)
            return np.where(hi_wins, high_t, low_t)

        # Round 1
        r2_18 = play_round_pair(s1, s8)
        r2_45 = play_round_pair(s4, s5)
        r2_36 = play_round_pair(s3, s6)
        r2_27 = play_round_pair(s2, s7)
        for adv in (r2_18, r2_45, r2_36, r2_27):
            r2_counts += np.bincount(adv, minlength=n_teams)

        # Conference Semifinals (Round 2)
        cf_top = play_round_pair(r2_18, r2_45)
        cf_bot = play_round_pair(r2_36, r2_27)
        for adv in (cf_top, cf_bot):
            cf_counts += np.bincount(adv, minlength=n_teams)

        # Conference Finals
        c_champ = play_round_pair(cf_top, cf_bot)
        finals_counts += np.bincount(c_champ, minlength=n_teams)
        conf_champs[conf_name] = c_champ
        conf_champ_wins[conf_name] = wins_with_tb[c_champ, sim_range]

    # NBA Finals (East Champion vs West Champion, home court to better regular-season record)
    e_champ = conf_champs["East"]
    w_champ = conf_champs["West"]
    e_high = conf_champ_wins["East"] >= conf_champ_wins["West"]
    f_high = np.where(e_high, e_champ, w_champ)
    f_low = np.where(e_high, w_champ, e_champ)
    r_f_hi = playoff_ratings[f_high, sim_range]
    r_f_lo = playoff_ratings[f_low, sim_range]
    f_hi_won = _series_win_prob_matrix(r_f_hi, r_f_lo, po_hca, po_hca, cfg.base_game_sd, df, rng)
    nba_champ = np.where(f_hi_won, f_high, f_low)
    title_counts += np.bincount(nba_champ, minlength=n_teams)

    # Compile team simulation summaries & win distributions
    sim_summary: Dict[str, Dict[str, Any]] = {}
    win_dist_rows: List[Dict[str, Any]] = []

    for i, ab in enumerate(abbrs):
        w_samples = sim_wins[i]
        proj_w = float(np.mean(w_samples))
        scheduled_games = sum(ab in (g["home"], g["away"]) for g in schedule)
        proj_l = scheduled_games - proj_w
        p10, p50, p90 = np.percentile(w_samples, [10, 50, 90])

        # Win distribution PMF across 0..82 wins
        win_hist = np.bincount(w_samples, minlength=83) / float(n_sims)
        for w_val in range(scheduled_games + 1):
            p_val = float(win_hist[w_val])
            win_dist_rows.append({
                "abbr": ab,
                "wins": w_val,
                "p": round(p_val, 8),
            })

        team_sim: Dict[str, Any] = {
            "proj_w": round(proj_w, 1),
            "proj_l": round(proj_l, 1),
            "w_p10": int(round(p10)),
            "w_p50": int(round(p50)),
            "w_p90": int(round(p90)),
            "p_top6": round(top6_counts[i] / n_sims, 4),
            "p_playin": round(playin_counts[i] / n_sims, 4),
            "p_playoffs": round(playoffs_counts[i] / n_sims, 4),
            "p_r2": round(r2_counts[i] / n_sims, 4),
            "p_cf": round(cf_counts[i] / n_sims, 4),
            "p_finals": round(finals_counts[i] / n_sims, 4),
            "p_title": round(title_counts[i] / n_sims, 4),
            "p_best": round(best_counts[i] / n_sims, 4),
            "rating_end": round(float(rating_end[i]), 2),
        }
        for s_rank in range(15):
            team_sim[f"seed_{s_rank + 1}"] = round(seed_counts[i, s_rank] / n_sims, 4)

        sim_summary[ab] = team_sim

    return sim_summary, win_dist_rows
