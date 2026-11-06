"""
Daily build orchestrator for n-Beta (n-Bet-a).

Runs the full data -> Bayesian Kalman rating -> Two-Stage Monte Carlo -> Audit pipeline,
validates mathematical consistency invariants, and writes static CSV + JSON artifacts
to `data/` for GitHub Pages rendering.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .config import ModelConfig, canonical_team, TEAM_VOLATILITY_MULT
from .data_fetcher import load_dataset
from .model import (
    compute_audit_and_calibration,
    enrich_players_and_injuries,
    run_kalman_state_space_model,
)
from .simulator import run_two_stage_monte_carlo


def write_csv_and_json(out_dir: Path, name: str, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    """Write dataset to both `<name>.csv` and `<name>.json` in `out_dir`."""
    csv_path = out_dir / f"{name}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    json_path = out_dir / f"{name}.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2, allow_nan=False)


def build_all(root_dir: Path, use_live_injuries: bool = False, n_sims: int = 100_000) -> Dict[str, Any]:
    """Execute the full n-Beta statistical pipeline and export static artifacts."""
    if n_sims <= 0:
        raise ValueError("n_sims must be positive")
    cfg = ModelConfig(n_sims=n_sims)
    seed_dir = root_dir / "data" / "seed"
    out_dir = root_dir / "data"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load schedule, teams, rosters, and injury data
    ds = load_dataset(seed_dir, cfg, use_live_injuries=use_live_injuries)
    teams_meta = ds["teams_meta"]
    schedule = ds["schedule"]

    # 2. Enrich players (O-Value / D-Value split + nonlinear injury synergy discount)
    as_of_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    players_enriched, team_injury_summary = enrich_players_and_injuries(
        ds["players"], as_of_iso[:10], cfg
    )

    # 3. Run Bayesian Kalman State-Space model across all completed games & predict upcoming slate
    kalman = run_kalman_state_space_model(
        teams_meta, schedule, team_injury_summary, ds["seed_history"], cfg
    )

    # Preseason reference distribution over the same listed schedule, without current injuries.
    prior_schedule = [{**g, "status": "upcoming", "hs": None, "as": None} for g in schedule]
    prior_state = run_kalman_state_space_model(teams_meta, prior_schedule, {}, ds["seed_history"], cfg)
    _, prior_dist = run_two_stage_monte_carlo(teams_meta, prior_state, {}, prior_schedule, cfg)
    prior_pmf = {(r["abbr"], r["wins"]): r["p"] for r in prior_dist}

    # 4. Run 100,000 Two-Stage Monte Carlo season + Play-In + Playoff simulations
    sim_summary, win_dist_rows = run_two_stage_monte_carlo(
        teams_meta, kalman, team_injury_summary, schedule, cfg
    )

    for r in win_dist_rows:
        r["p_prior"] = prior_pmf[(r["abbr"], r["wins"])]

    # 5. Compute Model & Audit parameters, backtest scorecard, and calibration bins
    params_rows, backtest_rows, calibration_rows = compute_audit_and_calibration(schedule, cfg)

    # 6. Assemble master `teams` table (sorted by current rank 1..30)
    abbrs_sorted = sorted(teams_meta.keys(), key=lambda ab: kalman["ranks_now"][ab])
    teams_rows: List[Dict[str, Any]] = []

    latest_d = kalman["latest_date"]
    prev1_d = kalman["prev_1d_date"]
    prev7_d = kalman["prev_7d_date"]

    for ab in abbrs_sorted:
        meta = teams_meta[ab]
        sim = sim_summary[ab]
        inj = team_injury_summary.get(ab, {})

        r_now = kalman["mu"][ab]
        r_sd = kalman["sd"][ab]
        r_ci90 = round(1.645 * r_sd, 2)
        r_1d = kalman["team_date_ratings"].get((ab, prev1_d), (r_now, r_sd))[0]
        r_7d = kalman["team_date_ratings"].get((ab, prev7_d), (r_now, r_sd))[0]

        rk_now = kalman["ranks_now"][ab]
        rk_1d = kalman["ranks_1d"][ab]
        rk_7d = kalman["ranks_7d"][ab]

        vegas_tot = meta["vegas_total"]
        vegas_diff = round(sim["proj_w"] - vegas_tot, 1)

        row: Dict[str, Any] = {
            "abbr": ab,
            "name": meta["name"],
            "tricode": meta["tricode"],
            "city": meta["city"],
            "conf": meta["conf"],
            "div": meta["div"],
            "color": meta["color"],
            "alt_color": meta["alt_color"],
            "rank": rk_now,
            "rank_d1": rk_1d - rk_now,
            "rank_d7": rk_7d - rk_now,
            "volatility_mult": TEAM_VOLATILITY_MULT.get(ab, 1.0),
            "scheduled_games": sum(ab in (g["home"],g["away"]) for g in schedule),
            "rating": f"{r_now:.2f}",
            "rating_sd": f"{r_sd:.2f}",
            "rating_ci90": f"{r_ci90:.2f}",
            "rating_d1": f"{r_now - r_1d:.2f}",
            "rating_d7": f"{r_now - r_7d:.2f}",
            "rating_prior": f"{kalman['prior_mu'][ab]:.2f}",
            "rating_today": f"{kalman['active_rating'][ab]:.2f}",
            "synergy_penalty": f"{inj.get('synergy_penalty', 0.0):.2f}",
            "vegas_total": f"{vegas_tot:.1f}",
            "vegas_diff": f"{vegas_diff:+.1f}",
            "w": kalman["wins"][ab],
            "l": kalman["losses"][ab],
            "last_game": kalman["last_game_str"][ab],
            "sos": f"{kalman['sos'][ab]:.2f}",
            "sos_rank": kalman["sos_rank"][ab],
            "sor": f"{kalman['sor'][ab]:.2f}",
            "sor_rank": kalman["sor_rank"][ab],
            "proj_w": f"{sim['proj_w']:.1f}",
            "proj_l": f"{sim['proj_l']:.1f}",
            "w_p10": sim["w_p10"],
            "w_p50": sim["w_p50"],
            "w_p90": sim["w_p90"],
            "p_top6": f"{sim['p_top6']:.4f}",
            "p_playin": f"{sim['p_playin']:.4f}",
            "p_playoffs": f"{sim['p_playoffs']:.4f}",
            "p_r2": f"{sim['p_r2']:.4f}",
            "p_cf": f"{sim['p_cf']:.4f}",
            "p_finals": f"{sim['p_finals']:.4f}",
            "p_title": f"{sim['p_title']:.4f}",
            "p_best": f"{sim['p_best']:.4f}",
        }
        for s_idx in range(1, 16):
            row[f"seed_{s_idx}"] = f"{sim[f'seed_{s_idx}']:.4f}"
        row["rating_end"] = f"{sim['rating_end']:.2f}"
        teams_rows.append(row)

    from .validation import validate_artifacts
    validate_artifacts(teams_rows, schedule, win_dist_rows)
    logos = json.loads((seed_dir / "logos.json").read_text())
    if isinstance(logos, dict):
        logos = {canonical_team(k): v for k, v in logos.items()}
    else:
        logos = [{**r, "abbr": canonical_team(r["abbr"])} for r in logos]
    (out_dir / "logos.json").write_text(json.dumps(logos, ensure_ascii=False, indent=2))

    # 7. Export `run`, `teams`, `schedule`, `win_dist`, `history`, `players`, `params`, `backtest`, `calibration`
    games_played = sum(1 for g in schedule if g["status"] == "final")
    games_left = len(schedule) - games_played

    run_rows = [{
        "as_of": as_of_iso,
        "season": cfg.season,
        "n_sims": cfg.n_sims,
        "games_played": games_played,
        "games_left": games_left,
        "elo_per_point": 26.14,
        "model_name": "n-Beta (Bayesian State-Space + Student-t)",
        "student_t_df": cfg.student_t_df,
        "data_source": "local seed snapshot (unverified provenance)",
        "injury_source": ds["injury_source"],
        "data_through": kalman["latest_date"],
        "schedule_games": len(schedule),
        "expected_schedule_games": 1230,
        "missing_games": max(0, 1230 - len(schedule)),
        "audit_scope": "snapshot prequential; priors not independently validated",
        "margin_method": "score proxy; no raw stints",
        "player_split_method": "position prior; not measured O/D impact",
        "market_source": "observed column only; missing values stay null",
        "random_seed": cfg.random_seed,
    }]

    write_csv_and_json(
        out_dir, "run", run_rows,
        list(run_rows[0]),
    )

    teams_fields = [
        "abbr", "name", "tricode", "city", "conf", "div", "color", "alt_color",
        "rank", "rank_d1", "rank_d7", "scheduled_games", "volatility_mult", "rating", "rating_sd", "rating_ci90",
        "rating_d1", "rating_d7", "rating_prior", "rating_today", "synergy_penalty",
        "vegas_total", "vegas_diff", "w", "l", "last_game", "sos", "sos_rank",
        "sor", "sor_rank", "proj_w", "proj_l", "w_p10", "w_p50", "w_p90",
        "p_top6", "p_playin", "p_playoffs", "p_r2", "p_cf", "p_finals", "p_title", "p_best",
        *[f"seed_{i}" for i in range(1, 16)], "rating_end",
    ]
    write_csv_and_json(out_dir, "teams", teams_rows, teams_fields)

    sched_fields = [
        "id", "date", "tip", "home", "away", "status", "hs", "as",
        "p_home", "spread", "market_spread", "edge_pts", "clean_margin", "home_delta", "away_delta", "neutral", "note",
    ]
    sched_export = []
    for g in schedule:
        sched_export.append({
            "id": g["id"],
            "date": g["date"],
            "tip": g["tip"],
            "home": g["home"],
            "away": g["away"],
            "status": g["status"],
            "hs": "" if g["hs"] is None else g["hs"],
            "as": "" if g["as"] is None else g["as"],
            "p_home": g["p_home"],
            "spread": g["spread"],
            "market_spread": g["market_spread"],
            "edge_pts": g["edge_pts"],
            "clean_margin": g["clean_margin"],
            "home_delta": g["home_delta"],
            "away_delta": g["away_delta"],
            "neutral": g["neutral"],
            "note": g["note"],
        })
    write_csv_and_json(out_dir, "schedule", sched_export, sched_fields)
    (out_dir / "prediction_traces.json").write_text(json.dumps(
        [g["prediction_trace"] for g in schedule if g["status"] != "final"],
        ensure_ascii=False, allow_nan=False, indent=2))
    write_csv_and_json(out_dir, "win_dist", win_dist_rows, ["abbr", "wins", "p", "p_prior"])
    write_csv_and_json(
        out_dir, "history", kalman["daily_history"],
        ["abbr", "date", "rating", "rating_sd", "rating_lo", "rating_hi"],
    )
    write_csv_and_json(
        out_dir, "players", players_enriched,
        ["abbr", "athlete_id", "name", "pos", "gp", "mpg", "o_value", "d_value", "value", "status", "p_out", "return_date", "comment"],
    )
    write_csv_and_json(
        out_dir, "params", params_rows,
        ["group", "key", "label", "value", "unit", "note", "kept", "d_logloss", "seasons_better", "folds", "d_test"],
    )
    write_csv_and_json(
        out_dir, "backtest", backtest_rows,
        ["model", "split", "seasons", "games", "logloss", "brier", "acc"],
    )
    write_csv_and_json(
        out_dir, "calibration", calibration_rows,
        ["bin", "p_mean", "actual", "n"],
    )

    return {
        "games_played": games_played,
        "games_left": games_left,
        "top5": [(r["rank"], r["abbr"], r["rating"], r["rating_ci90"], r["proj_w"], r["vegas_total"], r["p_title"]) for r in teams_rows[:5]],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the n-Beta daily statistical & simulation pipeline.")
    parser.add_argument("--live", action="store_true", help="Attempt live injury overlay from ESPN API")
    parser.add_argument("--sims", type=int, default=100_000, help="Number of Monte Carlo season simulations")
    args = parser.parse_args()

    root_dir = Path(__file__).resolve().parent.parent
    summary = build_all(root_dir, use_live_injuries=args.live, n_sims=args.sims)
    print(f"[n-Beta] Build complete: {summary['games_played']} final games, {summary['games_left']} upcoming games.")
    print("[n-Beta] Top 5 Teams (Rank | Abbr | Rating ±90%CI | Proj.W vs Vegas | Title%):")
    for rk, ab, rtg, ci, pw, vg, pt in summary["top5"]:
        print(f"  #{rk:<2d} {ab:<4s} Rating: {rtg:>5s} (±{ci}) | Proj.W: {pw:>4s} (Vegas {vg}) | Title: {float(pt)*100:5.1f}%")


if __name__ == "__main__":
    main()
