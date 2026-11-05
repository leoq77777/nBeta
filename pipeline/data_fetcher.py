"""
Data acquisition, live API adapters, and Stint-level Garbage-Time filtering for n-Beta.

Supports:
1. Local seed data loading from `data/seed/` (for zero-config reproducible runs).
2. Optional ESPN injury overlay; schedule and priors remain local snapshots.
3. Stint-level garbage-time filtering and rest/back-to-back context enrichment.
"""

from __future__ import annotations

import csv
import json
import math
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .config import ModelConfig, canonical_team


def read_csv_dicts(path: Path) -> List[Dict[str, str]]:
    """Read a CSV file into a list of string dictionaries."""
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def fetch_espn_injuries(timeout: int = 8) -> Optional[List[Dict[str, Any]]]:
    """
    Fetch real-time NBA injury reports from ESPN's public API.
    Returns None if offline or unreachable so pipeline can fall back gracefully.
    """
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "nBeta-Analytics/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        out: List[Dict[str, Any]] = []
        for team_entry in payload.get("injuries", []):
            team_abbr = team_entry.get("team", {}).get("abbreviation", "")
            for item in team_entry.get("injuries", []):
                athlete = item.get("athlete", {})
                details = item.get("details", {})
                out.append({
                    "abbr": team_abbr,
                    "athlete_id": str(athlete.get("id", "")),
                    "name": athlete.get("displayName", ""),
                    "status": item.get("status", "Active"),
                    "return_date": details.get("returnDate", ""),
                    "comment": item.get("shortComment", "") or item.get("longComment", ""),
                })
        return out
    except Exception:
        return None


def compute_stint_garbage_time_weight(
    margin: float,
    seconds_remaining: float,
    active_core_players: int = 6,
    lambda_gt: float = 14.0,
) -> float:
    """
    Compute the non-garbage-time weight w_k in [0, 1] for a game stint.

    Follows the ARCHITECTURE.md specification:
    - Full weight (1.0) during competitive play.
    - Smooth exponential decay when in-game win probability exceeds 95%
      in the 4th quarter or when core rotation players have been pulled.
    """
    if seconds_remaining <= 0:
        seconds_remaining = 1.0
    # Diffusion win probability approximation given margin and remaining seconds
    time_frac = max(seconds_remaining / 2880.0, 0.005)
    z_in_game = margin / (12.4 * math.sqrt(time_frac))
    p_in_game = 0.5 * (1.0 + math.erf(z_in_game / math.sqrt(2.0)))

    excess_cert = max(0.0, abs(p_in_game - 0.5) - 0.45)
    prob_decay = math.exp(-lambda_gt * (excess_cert ** 2))
    lineup_factor = min(1.0, max(0.25, active_core_players / 8.0))

    if seconds_remaining <= 540 and abs(margin) > 18:
        prob_decay *= 0.35
    if seconds_remaining <= 360 and abs(margin) > 22:
        prob_decay *= 0.15

    return float(prob_decay * lineup_factor)


def estimate_clean_game_margin(
    home_score: int,
    away_score: int,
    pregame_expected_margin: float,
    game_id: str,
    cfg: ModelConfig,
) -> Tuple[float, float]:
    """
    Estimate the garbage-time-filtered net margin (clean_margin) and effective
    diminishing-returns margin (capped_margin) for a completed game.

    When full play-by-play stints are unavailable offline, reconstructs the expected
    4th-quarter garbage-time bench drift: blowouts where the leading team leads by >16
    typically experience bench convergence (or blowout padding), which we filter before
    applying the soft hyperbolic tangent cap C * tanh(M_clean / C) and favorite
    autocorrelation dampener.
    """
    raw_margin = float(home_score - away_score)
    abs_m = abs(raw_margin)

    if abs_m > cfg.garbage_time_margin_threshold:
        # In blowouts, late 4th-quarter stints have low weight w_k;
        # competitive-window margin compresses extreme late-game noise
        excess = abs_m - cfg.garbage_time_margin_threshold
        clean_abs = cfg.garbage_time_margin_threshold + 0.58 * excess
        clean_margin = math.copysign(clean_abs, raw_margin)
    else:
        clean_margin = raw_margin

    # Soft hyperbolic tangent cap: C * tanh(M_clean / C)
    capped_margin = cfg.mov_cap * math.tanh(clean_margin / cfg.mov_cap)

    # Autocorrelation dampener: prevents heavy favorites from inflating ratings on routine blowouts
    if raw_margin * pregame_expected_margin > 0 and abs_m > 12.0:
        fav_align = min(abs(pregame_expected_margin), 12.0)
        dampener = 1.0 / (1.0 + cfg.autocorr_favorite_dampener * fav_align)
        capped_margin *= dampener

    return round(clean_margin, 2), round(capped_margin, 2)


def enrich_schedule_context(
    schedule_rows: List[Dict[str, str]],
    teams_meta: Dict[str, Dict[str, Any]],
    cfg: ModelConfig,
) -> List[Dict[str, Any]]:
    """
    Sort schedule chronologically and compute rest days, back-to-back (B2B) flags,
    3-in-4 fatigue flags, and altitude indicators for every game.
    """
    sorted_games = sorted(schedule_rows, key=lambda r: (r["date"], r.get("tip", ""), r["id"]))
    last_played_date: Dict[str, datetime] = {}
    recent_dates: Dict[str, List[datetime]] = {abbr: [] for abbr in teams_meta}

    enriched: List[Dict[str, Any]] = []
    for row in sorted_games:
        g_date = datetime.strptime(row["date"][:10], "%Y-%m-%d")
        home = row["home"]
        away = row["away"]

        def get_rest_and_b2b(team: str) -> Tuple[int, int, int]:
            prev = last_played_date.get(team)
            if prev is None:
                rest_days = 3
                is_b2b = 0
            else:
                delta_days = (g_date - prev).days - 1
                rest_days = max(0, min(delta_days, 4))
                is_b2b = 1 if delta_days == 0 else 0
            # Check 3 games in 4 nights
            hist = [d for d in recent_dates.get(team, []) if 0 < (g_date - d).days <= 3]
            is_3in4 = 1 if len(hist) >= 2 else 0
            return rest_days, is_b2b, is_3in4

        h_rest, h_b2b, h_3in4 = get_rest_and_b2b(home)
        a_rest, a_b2b, a_3in4 = get_rest_and_b2b(away)

        last_played_date[home] = g_date
        last_played_date[away] = g_date
        recent_dates.setdefault(home, []).append(g_date)
        recent_dates.setdefault(away, []).append(g_date)

        is_final = row.get("status") == "final" and row.get("hs", "") != "" and row.get("as", "") != ""
        hs = int(float(row["hs"])) if is_final else None
        as_ = int(float(row["as"])) if is_final else None
        neutral = int(float(row.get("neutral", "0") or 0))

        enriched.append({
            "id": str(row["id"]),
            "date": row["date"][:10],
            "tip": row.get("tip", ""),
            "home": home,
            "away": away,
            "status": "final" if is_final else "upcoming",
            "hs": hs,
            "as": as_,
            "neutral": neutral,
            "note": row.get("note", ""),
            "home_rest": h_rest,
            "away_rest": a_rest,
            "home_b2b": h_b2b,
            "away_b2b": a_b2b,
            "home_3in4": h_3in4,
            "away_3in4": a_3in4,
            "is_altitude": 1 if (not neutral and home in cfg.altitude_teams) else 0,
            "seed_spread": float(row["spread"]) if row.get("spread", "") != "" else 0.0,
            "observed_market_spread": float(row["market_spread"]) if row.get("market_spread", "") != "" else None,
            "seed_p_home": float(row["p_home"]) if row.get("p_home", "") != "" else 0.5,
        })

    return enriched


def load_dataset(seed_dir: Path, cfg: ModelConfig, use_live_injuries: bool = False) -> Dict[str, Any]:
    """Load and enrich teams, players, schedule, and run metadata."""
    run_rows = read_csv_dicts(seed_dir / "run.csv")
    team_rows = read_csv_dicts(seed_dir / "teams.csv")
    sched_rows = read_csv_dicts(seed_dir / "schedule.csv")
    player_rows = read_csv_dicts(seed_dir / "players.csv")
    history_rows = read_csv_dicts(seed_dir / "history.csv")

    teams_meta: Dict[str, Dict[str, Any]] = {}
    for r in team_rows:
        abbr = r["abbr"]
        teams_meta[abbr] = {
            "abbr": abbr,
            "name": r["name"],
            "tricode": r.get("tricode", abbr),
            "city": r["city"],
            "conf": r["conf"],
            "div": r["div"],
            "color": r["color"],
            "alt_color": r["alt_color"],
            "vegas_total": float(r["vegas_total"]),
            "seed_prior": float(r["rating_prior"]),
        }

    for rows in (team_rows, player_rows, history_rows):
        for row in rows:
            row["abbr"] = canonical_team(row["abbr"])
    teams_meta = {canonical_team(ab): {**meta, "abbr": canonical_team(ab)} for ab, meta in teams_meta.items()}
    for row in sched_rows:
        if row["status"] == "scheduled":
            row["status"] = "upcoming"
        row["home"] = canonical_team(row["home"])
        row["away"] = canonical_team(row["away"])
    if len(teams_meta) != 30 or len({g["id"] for g in sched_rows}) != len(sched_rows):
        raise ValueError("Expected 30 unique teams and unique game IDs")
    for row in sched_rows:
        if row["home"] not in teams_meta or row["away"] not in teams_meta or row["home"] == row["away"]:
            raise ValueError(f"Invalid matchup: {row['id']}")
        if row.get("status") not in {"final", "upcoming"}:
            raise ValueError(f"Invalid status: {row['id']}")
        if row["status"] == "final" and (not row.get("hs") or not row.get("as") or row["hs"] == row["as"]):
            raise ValueError(f"Invalid final score: {row['id']}")
    if any(p["abbr"] not in teams_meta for p in player_rows):
        raise ValueError("Unknown roster team")

    # Optional live injury overlay from ESPN API
    if use_live_injuries:
        live_inj = fetch_espn_injuries()
        if live_inj:
            inj_by_name = {item["name"].lower(): item for item in live_inj}
            for p in player_rows:
                match = inj_by_name.get(p["name"].lower())
                if match:
                    p["status"] = match["status"]
                    status = match["status"].lower()
                    p["p_out"] = str({"out": 1.0, "doubtful": .75, "probable": .25, "active": 0.0}.get(status, .5))
                    if match["return_date"]:
                        p["return_date"] = match["return_date"]
                    if match["comment"]:
                        p["comment"] = match["comment"]

    enriched_sched = enrich_schedule_context(sched_rows, teams_meta, cfg)

    return {
        "run_meta": run_rows[0] if run_rows else {},
        "injury_source": "espn" if use_live_injuries and live_inj else "seed",
        "teams_meta": teams_meta,
        "schedule": enriched_sched,
        "players": player_rows,
        "seed_history": history_rows,
        "seed_teams": team_rows,
    }
