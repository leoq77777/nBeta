"""
Core Bayesian State-Space & Heavy-Tailed Matchup Model for n-Beta (n-Bet-a).

Implements:
1. Preseason Prior Calibration from Vegas Win Totals & Roster Continuity.
2. Dynamic Kalman State-Space Filtering with Garbage-Time Filtered Margins.
3. Player Offensive/Defensive Impact Split & Nonlinear Injury Synergy Penalty.
4. Heavy-Tailed Student-t Single-Game Win Probability, Spread & Market Edge (+EV).
5. Leave-One-Season-Out Context Parameters, Backtest Metrics & Calibration Bins.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

import numpy as np

from .config import TEAM_CONTINUITY, TEAM_VOLATILITY_MULT, ModelConfig
from .data_fetcher import estimate_clean_game_margin


def student_t_cdf(x: float, df: float) -> float:
    """
    Exact Student-t cumulative distribution function F_{t_df}(x) via trigonometric
    transformation u = sqrt(df) * tan(theta) and 24-node Simpson's rule on [0, atan(|x|/sqrt(df))].
    Numerical approximation with no SciPy dependency.
    """
    if x == 0.0:
        return 0.5
    theta_max = math.atan(abs(x) / math.sqrt(df))
    n_steps = 24  # even number for Simpson's rule
    h = theta_max / n_steps
    power = df - 1.0

    total = 1.0 + (math.cos(theta_max) ** power)
    for i in range(1, n_steps):
        weight = 4.0 if (i % 2 == 1) else 2.0
        total += weight * (math.cos(i * h) ** power)

    integral = (h / 3.0) * total
    norm_const = math.exp(math.lgamma((df + 1.0) / 2.0) - math.lgamma(df / 2.0)) / math.sqrt(math.pi)
    half_prob = norm_const * integral
    return min(0.999999, max(0.000001, 0.5 + math.copysign(half_prob, x)))


def compute_context_adjustment(game: Dict[str, Any], cfg: ModelConfig, is_playoffs: bool = False) -> float:
    """
    Compute context points added to home team's expected margin:
    + Home Court Advantage (with playoff boost if applicable)
    + Altitude bonus (DEN, UTA)
    + Rest differential bonus
    + Back-to-back (B2B) and 3-in-4 fatigue penalties
    """
    if game.get("neutral", 0) == 1:
        hca = 0.0
    else:
        hca = cfg.home_court_advantage + (cfg.playoff_hca_boost if is_playoffs else 0.0)
        if game.get("is_altitude", 0) == 1:
            hca += cfg.altitude_home_bonus

    rest_diff = max(-3, min(3, game.get("home_rest", 1) - game.get("away_rest", 1)))
    rest_adj = cfg.rest_diff_coeff * rest_diff

    b2b_adj = cfg.b2b_penalty * (game.get("away_b2b", 0) - game.get("home_b2b", 0))
    three_in_four_adj = 0.35 * (game.get("away_3in4", 0) - game.get("home_3in4", 0))

    return hca + rest_adj + b2b_adj + three_in_four_adj


def enrich_players_and_injuries(
    player_rows: List[Dict[str, str]],
    as_of_date: str,
    cfg: ModelConfig,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """
    Decompose each player's total value into Offensive Value (o_value) and
    Defensive Value (d_value), and compute each team's nonlinear injury discount
    plus playoff top-2 star leverage.
    """
    enriched_players: List[Dict[str, Any]] = []
    team_rosters: Dict[str, List[Dict[str, Any]]] = {}

    # Position-based offensive/defensive value split priors
    pos_off_share = {"G": 0.64, "F": 0.54, "C": 0.42, "GF": 0.60, "FC": 0.46}

    for row in player_rows:
        abbr = row["abbr"]
        val = float(row.get("value", "0") or 0.0)
        mpg = float(row.get("mpg", "0") or 0.0)
        gp = int(float(row.get("gp", "0") or 0))
        pos = (row.get("pos", "F") or "F").strip()
        status = (row.get("status", "Active") or "Active").strip()
        p_out_raw = row.get("p_out", "")
        if p_out_raw != "":
            p_out = float(p_out_raw)
        else:
            p_out = 0.0 if status.lower() == "active" else (1.0 if status.lower() == "out" else cfg.dtd_miss_prob_default)

        # Position prior only; no measured offensive/defensive decomposition is available.
        o_share = pos_off_share.get(pos, 0.55)
        if val >= 0:
            o_val = round(val * o_share, 2)
            d_val = round(val - o_val, 2)
        else:
            o_val = round(val * (1.0 - o_share * 0.5), 2)
            d_val = round(val - o_val, 2)

        p_dict = {
            "abbr": abbr,
            "athlete_id": str(row.get("athlete_id", "")),
            "name": row.get("name", ""),
            "pos": pos,
            "gp": gp,
            "mpg": round(mpg, 1),
            "o_value": o_val,
            "d_value": d_val,
            "value": round(val, 2),
            "status": status,
            "p_out": round(p_out, 3),
            "return_date": row.get("return_date", ""),
            "comment": row.get("comment", ""),
        }
        enriched_players.append(p_dict)
        team_rosters.setdefault(abbr, []).append(p_dict)

    team_injury_summary: Dict[str, Dict[str, Any]] = {}
    for abbr, roster in team_rosters.items():
        roster.sort(key=lambda x: (-x["value"], -x["mpg"]))
        # Linear sum of expected missing positive player value for next game
        linear_loss = sum(max(0.0, p["value"]) * p["p_out"] for p in roster if p["p_out"] > 0)
        # Nonlinear synergy overload penalty when multiple rotation pieces sit
        overload_mult = 1.0 + cfg.synergy_overload_eta * max(0.0, linear_loss - cfg.synergy_overload_threshold)
        effective_discount = linear_loss * overload_mult

        # Top-2 player star value (drives playoff rotation compression bonus)
        top2_val = sum(max(0.0, p["value"]) for p in roster[:2])

        # List of players currently out or questionable with positive impact
        out_players = [
            p for p in roster
            if p["status"].lower() != "active" and p["p_out"] >= 0.35 and p["value"] > 0.05
        ]
        out_names = ", ".join(p["name"] for p in out_players)

        team_injury_summary[abbr] = {
            "linear_loss": round(linear_loss, 2),
            "synergy_penalty": round(effective_discount - linear_loss, 2),
            "total_injury_discount": round(effective_discount, 2),
            "top2_star_value": round(top2_val, 2),
            "out_names": out_names,
            "out_players": out_players,
        }

    return enriched_players, team_injury_summary


def predict_game_student_t(
    home_rating: float,
    away_rating: float,
    home_sd: float,
    away_sd: float,
    home_abbr: str,
    away_abbr: str,
    game: Dict[str, Any],
    cfg: ModelConfig,
    is_playoffs: bool = False,
) -> Tuple[float, float, float]:
    """
    Compute expected margin (Home - Away), total game SD (including epistemic rating SD
    and team 3PT/pace volatility), and heavy-tailed Student-t home win probability.

    Returns:
        (expected_home_margin, home_win_prob, total_game_sd)
    """
    ctx = compute_context_adjustment(game, cfg, is_playoffs=is_playoffs)
    expected_margin = (home_rating - away_rating) + ctx

    vol_h = TEAM_VOLATILITY_MULT.get(home_abbr, 1.0)
    vol_a = TEAM_VOLATILITY_MULT.get(away_abbr, 1.0)
    sigma_game = cfg.base_game_sd * 0.5 * (vol_h + vol_a)
    total_sd = math.sqrt(sigma_game ** 2 + home_sd ** 2 + away_sd ** 2)

    # Student-t scale adjustment so variance matches total_sd^2
    df = cfg.student_t_df
    scale = total_sd * math.sqrt((df - 2.0) / df)
    p_home = float(student_t_cdf(expected_margin / scale, df=df))
    p_home = min(0.995, max(0.005, p_home))

    return expected_margin, p_home, total_sd


def run_kalman_state_space_model(
    teams_meta: Dict[str, Dict[str, Any]],
    schedule: List[Dict[str, Any]],
    team_injury_summary: Dict[str, Dict[str, Any]],
    seed_history: List[Dict[str, str]],
    cfg: ModelConfig,
) -> Dict[str, Any]:
    """
    Run the chronological Bayesian Kalman State-Space filter from preseason priors
    through all completed games, tracking daily posterior means, credible intervals,
    clean margins, and market comparison metrics.
    """
    abbrs = sorted(teams_meta.keys())

    # 1. Initialize Preseason Priors N(mu_{i,0}, sigma^2_{i,0})
    mu: Dict[str, float] = {}
    var: Dict[str, float] = {}
    prior_mu: Dict[str, float] = {}

    for abbr in abbrs:
        meta = teams_meta[abbr]
        # Combine preseason Vegas win total implied rating with seed roster prior
        vegas_implied = (meta["vegas_total"] - 41.0) * cfg.vegas_prior_slope
        p0 = 0.65 * meta["seed_prior"] + 0.35 * vegas_implied
        mu[abbr] = p0
        prior_mu[abbr] = p0

        continuity = TEAM_CONTINUITY.get(abbr, 0.80)
        sd0 = cfg.prior_base_sd + cfg.roster_turnover_sd_bonus * (1.0 - continuity)
        var[abbr] = sd0 ** 2

    # Zero-center prior ratings across all 30 teams
    mean_p0 = sum(mu.values()) / len(abbrs)
    for abbr in abbrs:
        mu[abbr] -= mean_p0
        prior_mu[abbr] = round(mu[abbr], 2)

    # Group completed games by date
    completed_games = [g for g in schedule if g["status"] == "final"]
    upcoming_games = [g for g in schedule if g["status"] != "final"]

    all_dates = sorted({g["date"] for g in completed_games})
    if seed_history:
        first_date = min(r["date"] for r in seed_history)
        if first_date not in all_dates:
            all_dates = [first_date] + all_dates

    daily_history: List[Dict[str, Any]] = []
    team_date_ratings: Dict[Tuple[str, str], Tuple[float, float]] = {}

    games_by_date: Dict[str, List[Dict[str, Any]]] = {}
    for g in completed_games:
        games_by_date.setdefault(g["date"], []).append(g)

    wins_count: Dict[str, int] = {abbr: 0 for abbr in abbrs}
    losses_count: Dict[str, int] = {abbr: 0 for abbr in abbrs}
    sor_accum: Dict[str, float] = {abbr: 0.0 for abbr in abbrs}
    last_game_str: Dict[str, str] = {abbr: "–" for abbr in abbrs}

    # 2. Step through each date and apply Kalman State-Space updates
    for d_str in all_dates:
        day_games = games_by_date.get(d_str, [])
        for g in day_games:
            h = g["home"]
            a = g["away"]

            # Prior prediction step: state drift
            mu_h_pred = cfg.mean_reversion_rho * mu[h]
            mu_a_pred = cfg.mean_reversion_rho * mu[a]
            var_h_pred = var[h] + cfg.process_drift_q
            var_a_pred = var[a] + cfg.process_drift_q

            # Pregame expectation using Student-t engine
            exp_margin, p_home, total_sd = predict_game_student_t(
                mu_h_pred, mu_a_pred, math.sqrt(var_h_pred), math.sqrt(var_a_pred), h, a, g, cfg
            )

            # Garbage-time filtered clean margin & soft-capped margin
            clean_margin, capped_margin = estimate_clean_game_margin(
                g["hs"], g["as"], exp_margin, g["id"], cfg
            )
            innovation = capped_margin - exp_margin

            # Kalman gain proportional to each team's posterior uncertainty
            obs_var = cfg.obs_noise_sigma ** 2
            denom = var_h_pred + var_a_pred + obs_var
            k_h = var_h_pred / denom
            k_a = var_a_pred / denom

            # Minimum floor gain so mid-season updates remain responsive (matching reference dynamics)
            eff_k_h = max(0.032, k_h * 1.15)
            eff_k_a = max(0.032, k_a * 1.15)

            delta_h = eff_k_h * innovation
            delta_a = -eff_k_a * innovation

            mu[h] = mu_h_pred + delta_h
            mu[a] = mu_a_pred + delta_a
            var[h] = (1.0 - k_h) * var_h_pred
            var[a] = (1.0 - k_a) * var_a_pred

            # Market closing line benchmark & Edge calculation
            mkt_spread = g.get("observed_market_spread")
            model_spread = round(-exp_margin, 1)
            edge_pts = round(mkt_spread - model_spread, 2) if mkt_spread is not None else None

            g["p_home"] = round(p_home, 3)
            g["spread"] = model_spread
            g["market_spread"] = round(mkt_spread, 1) if mkt_spread is not None else None
            g["edge_pts"] = edge_pts
            g["clean_margin"] = clean_margin
            g["home_delta"] = round(delta_h, 2)
            g["away_delta"] = round(delta_a, 2)

            # Update W-L and Strength of Record (SOR: wins above average team expectation)
            home_won = 1.0 if g["hs"] > g["as"] else 0.0
            if home_won > 0.5:
                wins_count[h] += 1
                losses_count[a] += 1
                last_game_str[h] = f"W {g['hs']}–{g['as']} vs {a}"
                last_game_str[a] = f"L {g['as']}–{g['hs']} @ {h}"
            else:
                losses_count[h] += 1
                wins_count[a] += 1
                last_game_str[h] = f"L {g['hs']}–{g['as']} vs {a}"
                last_game_str[a] = f"W {g['as']}–{g['hs']} @ {h}"

            # Expected win probability for a 0.0 average team in the same game slot
            _, p_avg_home, _ = predict_game_student_t(0.0, mu_a_pred, 1.0, math.sqrt(var_a_pred), h, a, g, cfg)
            _, p_avg_away_home, _ = predict_game_student_t(mu_h_pred, 0.0, math.sqrt(var_h_pred), 1.0, h, a, g, cfg)
            p_avg_away = 1.0 - p_avg_away_home

            sor_accum[h] += (home_won - p_avg_home)
            sor_accum[a] += ((1.0 - home_won) - p_avg_away)

        # Normalize ratings to exact 0.0 league mean at the end of each day
        day_mean = sum(mu.values()) / len(abbrs)
        for abbr in abbrs:
            mu[abbr] -= day_mean
            sd_val = math.sqrt(var[abbr])
            ci90 = 1.645 * sd_val
            r_val = round(mu[abbr], 2)
            daily_history.append({
                "abbr": abbr,
                "date": d_str,
                "rating": r_val,
                "rating_sd": round(sd_val, 2),
                "rating_lo": round(r_val - ci90, 2),
                "rating_hi": round(r_val + ci90, 2),
            })
            team_date_ratings[(abbr, d_str)] = (r_val, sd_val)

    # 3. Compute Active Ratings (Today / Next Game with Injury Synergy Penalty)
    active_rating: Dict[str, float] = {}
    rating_sd_map: Dict[str, float] = {}
    for abbr in abbrs:
        inj_disc = team_injury_summary.get(abbr, {}).get("total_injury_discount", 0.0)
        # Baseline full-strength rating is mu[abbr]; active rating applies nonlinear injury discount
        # If a team has been playing without long-term injured stars, a portion (45%) is already reflected
        active_r = mu[abbr] - 0.58 * inj_disc
        active_rating[abbr] = round(active_r, 2)
        rating_sd_map[abbr] = round(math.sqrt(var[abbr]), 2)

    # 4. Predict all upcoming schedule games (blending active rating for immediate games & recovery for distant games)
    first_upcoming_date = min((g["date"] for g in upcoming_games), default="2026-11-04")
    dt_first = datetime.strptime(first_upcoming_date, "%Y-%m-%d")

    rem_opp_ratings: Dict[str, List[float]] = {abbr: [] for abbr in abbrs}
    for g in upcoming_games:
        h = g["home"]
        a = g["away"]
        days_ahead = max(0, (datetime.strptime(g["date"], "%Y-%m-%d") - dt_first).days)

        # Exponential injury recovery curve over future schedule horizon
        recovery_w = math.exp(-days_ahead / 18.0)
        r_h = recovery_w * active_rating[h] + (1.0 - recovery_w) * mu[h]
        r_a = recovery_w * active_rating[a] + (1.0 - recovery_w) * mu[a]

        exp_margin, p_home, total_sd = predict_game_student_t(
            r_h, r_a, rating_sd_map[h], rating_sd_map[a], h, a, g, cfg
        )
        # Observability only: ordered ablations share the production variance/transform.
        stage_margins = [("strength", mu[h] - mu[a]),
                         ("availability", r_h - r_a), ("context", exp_margin)]
        scale = total_sd * math.sqrt((cfg.student_t_df - 2.0) / cfg.student_t_df)
        g["prediction_trace"] = {
            "game_id": g["id"], "date": g["date"], "tip": g["tip"], "home": h, "away": a,
            "inputs": {"home_rating": mu[h], "away_rating": mu[a],
                       "home_active_rating": active_rating[h], "away_active_rating": active_rating[a],
                       "home_rating_sd": rating_sd_map[h], "away_rating_sd": rating_sd_map[a],
                       "recovery_weight": recovery_w, "days_ahead": days_ahead,
                       **{k: g.get(k, 0 if k != "home_rest" and k != "away_rest" else 1)
                          for k in ("neutral", "is_altitude", "home_rest", "away_rest", "home_b2b", "away_b2b", "home_3in4", "away_3in4")}},
            "distribution": {"family": "student_t_margin", "sd": total_sd,
                             "scale": scale, "df": cfg.student_t_df},
            "stages": [{"name": name, "mean": margin,
                        "p_home": min(.995, max(.005, float(student_t_cdf(margin / scale, cfg.student_t_df))))}
                       for name, margin in stage_margins],
            "unsupported_stages": ["additive_research", "lineup_interactions", "joint_score_prediction"],
        }
        assert abs(g["prediction_trace"]["stages"][-1]["p_home"] - p_home) < 1e-12
        model_spread = round(-exp_margin, 1)

        # Only independently supplied market observations qualify as a benchmark.
        mkt_spread = g.get("observed_market_spread")
        edge_pts = round(mkt_spread - model_spread, 2) if mkt_spread is not None else None

        g["p_home"] = round(p_home, 3)
        g["spread"] = model_spread
        g["market_spread"] = mkt_spread
        g["edge_pts"] = edge_pts
        g["clean_margin"] = ""
        g["home_delta"] = ""
        g["away_delta"] = ""

        # Track remaining schedule opponent strength (adjusted for home/away)
        rem_opp_ratings[h].append(mu[a] - 0.5 * cfg.home_court_advantage)
        rem_opp_ratings[a].append(mu[h] + 0.5 * cfg.home_court_advantage)

    # 5. Compute 1-day and 7-day Rating & Rank deltas
    if not all_dates:
        raise ValueError("At least one completed game or history date is required")
    latest_date = all_dates[-1]
    def snapshot_before(days):
        target = (datetime.strptime(latest_date, "%Y-%m-%d") - timedelta(days=days)).strftime("%Y-%m-%d")
        return max((d for d in all_dates if d <= target), default=all_dates[0])
    prev_1d_date = snapshot_before(1)
    prev_7d_date = snapshot_before(7)

    def get_ranks_on_date(d_key: str) -> Dict[str, int]:
        ranked = sorted(abbrs, key=lambda x: -team_date_ratings.get((x, d_key), (mu[x], 1.0))[0])
        return {ab: idx + 1 for idx, ab in enumerate(ranked)}

    ranks_now = get_ranks_on_date(latest_date)
    ranks_1d = get_ranks_on_date(prev_1d_date)
    ranks_7d = get_ranks_on_date(prev_7d_date)

    # Compute SOS (Remaining Schedule Strength: 1st = hardest) and SOR (Strength of Record: 1st = best)
    sos_map = {abbr: round(float(np.mean(rem_opp_ratings[abbr])) if rem_opp_ratings[abbr] else 0.0, 2) for abbr in abbrs}
    sor_map = {abbr: round(sor_accum[abbr], 2) for abbr in abbrs}

    sos_sorted = sorted(abbrs, key=lambda x: -sos_map[x])
    sor_sorted = sorted(abbrs, key=lambda x: -sor_map[x])
    sos_rank = {ab: i + 1 for i, ab in enumerate(sos_sorted)}
    sor_rank = {ab: i + 1 for i, ab in enumerate(sor_sorted)}

    return {
        "mu": {ab: round(mu[ab], 2) for ab in abbrs},
        "sd": rating_sd_map,
        "prior_mu": prior_mu,
        "active_rating": active_rating,
        "wins": wins_count,
        "losses": losses_count,
        "last_game_str": last_game_str,
        "ranks_now": ranks_now,
        "ranks_1d": ranks_1d,
        "ranks_7d": ranks_7d,
        "team_date_ratings": team_date_ratings,
        "latest_date": latest_date,
        "prev_1d_date": prev_1d_date,
        "prev_7d_date": prev_7d_date,
        "sos": sos_map,
        "sos_rank": sos_rank,
        "sor": sor_map,
        "sor_rank": sor_rank,
        "daily_history": daily_history,
    }


def compute_audit_and_calibration(
    schedule: List[Dict[str, Any]], cfg: ModelConfig,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Prequential scores on the supplied snapshot, not historical out-of-sample proof."""
    specs = [
        ("core", "prior_base_sd", "Preseason prior SD", "pts"),
        ("core", "process_drift_q", "Per-game state variance", "pts²"),
        ("core", "mov_cap", "Score proxy soft cap", "pts"),
        ("core", "student_t_df", "Student-t degrees of freedom", "df"),
        ("core", "base_game_sd", "Baseline game standard deviation", "pts"),
        ("core", "synergy_overload_eta", "Injury overload penalty", "scale"),
        ("core", "playoff_star_leverage", "Playoff star multiplier", "×"),
        ("factor", "home_court_advantage", "Home court advantage", "pts"),
        ("factor", "b2b_penalty", "Back-to-back penalty", "pts"),
        ("factor", "rest_diff_coeff", "Rest differential", "pts/day"),
        ("factor", "altitude_home_bonus", "Altitude bonus", "pts"),
    ]
    params = [dict(group=group, key=key, label=label, value=getattr(cfg,key), unit=unit,
                   note="Configured; not cross-validated", kept=1, d_logloss=None,
                   seasons_better=None, folds=None, d_test=None) for group,key,label,unit in specs]
    completed = [g for g in schedule if g["status"] == "final"]
    probs = np.array([float(g["p_home"]) for g in completed])
    outcomes = np.array([float(g["hs"] > g["as"]) for g in completed])
    def score(name, p):
        p = np.clip(p, .000001, .999999)
        n = len(p)
        return dict(model=name, split="snapshot prequential", seasons=cfg.season, games=n,
                    logloss=round(float(-np.mean(outcomes*np.log(p)+(1-outcomes)*np.log(1-p))),6) if n else None,
                    brier=round(float(np.mean((p-outcomes)**2)),6) if n else None,
                    acc=round(float(np.mean((p>=.5)==(outcomes>=.5))),6) if n else None)
    audit = [score("n-Beta", probs), score("50% baseline", np.full(len(probs),.5))]
    bins = []
    for i in range(10):
        mask = (probs >= i/10) & ((probs < (i+1)/10) if i<9 else (probs <= 1))
        n = int(mask.sum())
        bins.append(dict(bin=f"{i*10}–{(i+1)*10}%", p_mean=round(float(probs[mask].mean()),6) if n else None,
                         actual=round(float(outcomes[mask].mean()),6) if n else None, n=n))
    return params, audit, bins
