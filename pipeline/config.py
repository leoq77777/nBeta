"""
Configuration & Statistical Hyperparameters for n-Beta (n-Bet-a).

All parameters are expressed in points per 100 possessions / points per game
against an average NBA team (0.0 = League Average).
"""

from dataclasses import dataclass, field
from typing import Dict, Set


@dataclass(frozen=True)
class ModelConfig:
    """Core hyperparameters for the n-Beta statistical engine."""

    # Season metadata
    season: str = "2026–27"
    n_sims: int = 100_000
    random_seed: int = 20261104

    # 1. Preseason Prior & Kalman State-Space Parameters
    # Weight on Vegas preseason win total vs roster RAPM baseline
    vegas_prior_slope: float = 0.345          # Points of rating per win above/below 41.0
    prior_base_sd: float = 1.85               # Base prior standard deviation (points)
    roster_turnover_sd_bonus: float = 0.65    # Extra prior SD for high-turnover teams
    process_drift_q: float = 0.048            # Per-game state evolution variance (q)
    mean_reversion_rho: float = 0.9975        # Mild per-game shrinkage toward 0
    obs_noise_sigma: float = 11.60            # Effective single-game observation noise SD (points)

    # 2. Stint & Garbage-Time Filtering Parameters
    mov_cap: float = 22.0                     # Soft tanh margin-of-victory cap (points)
    garbage_time_margin_threshold: float = 18.0
    autocorr_favorite_dampener: float = 0.022 # Dampens blowout inflation when heavy favorites win big

    # 3. Lineup & Injury Nonlinear Synergy Parameters
    synergy_overload_threshold: float = 1.50  # Missing value threshold (pts) where overload kicks in
    synergy_overload_eta: float = 0.085       # Nonlinear penalty factor for multiple missing stars
    dtd_miss_prob_default: float = 0.50       # Default miss probability for Questionable / Day-To-Day
    injury_recovery_weibull_k: float = 2.2    # Shape parameter for stochastic return-date sampling
    return_ramp_games: int = 3                # Games required to ramp minutes from 70% to 100% after long absence

    # 4. Game-Level Context & Heavy-Tailed Student-t Matchup Engine
    home_court_advantage: float = 2.15        # Baseline NBA home court advantage (points)
    b2b_penalty: float = 1.45                 # Penalty for playing second night of a back-to-back (points)
    rest_diff_coeff: float = 0.38             # Bonus per extra day of rest (clipped to [-3, +3])
    altitude_home_bonus: float = 0.75         # Extra HCA for high-altitude arenas (DEN, UTA)
    student_t_df: float = 7.5                 # Degrees of freedom for heavy-tailed game margin distribution
    base_game_sd: float = 12.35               # Base single-game margin standard deviation

    # 5. Playoff Regime Switching & Market Calibration
    playoff_star_leverage: float = 1.12       # Multiplier on top-2 player impact in 7-game playoff series
    playoff_hca_boost: float = 0.25           # Extra home court edge in playoff games
    sim_epistemic_scale: float = 0.85         # Scale of posterior SD sampled across Monte Carlo universes
    sim_in_season_k: float = 0.32             # In-simulation game-by-game rating update sensitivity
    market_edge_threshold_pts: float = 1.50   # Minimum spread divergence (pts) to flag a +EV Edge

    altitude_teams: Set[str] = field(default_factory=lambda: {"DEN", "UTA"})


# Roster continuity estimates (0.0 to 1.0) affecting initial prior variance sigma_0^2
TEAM_CONTINUITY: Dict[str, float] = {
    "OKC": 0.92, "BOS": 0.90, "NY": 0.84, "DEN": 0.86, "MIN": 0.80,
    "DAL": 0.82, "MIL": 0.83, "PHI": 0.72, "CLE": 0.88, "IND": 0.87,
    "ORL": 0.89, "PHX": 0.78, "SAC": 0.81, "NOP": 0.76, "MEM": 0.80,
    "MIA": 0.85, "GS": 0.79, "LAL": 0.83, "HOU": 0.86, "SA": 0.82,
    "ATL": 0.75, "CHI": 0.70, "TOR": 0.77, "CHA": 0.74, "POR": 0.76,
    "UTA": 0.75, "DET": 0.78, "BKN": 0.68, "WSH": 0.71, "LAC": 0.73,
}

# Preseason 3-point attempt rate & pace volatility multipliers (affects game-specific SD)
TEAM_VOLATILITY_MULT: Dict[str, float] = {
    "BOS": 1.06, "GS": 1.05, "IND": 1.05, "ATL": 1.04, "DAL": 1.03,
    "SAC": 1.03, "OKC": 1.01, "HOU": 1.01, "MEM": 1.02, "MIL": 1.02,
    "NY": 0.97, "CLE": 0.98, "ORL": 0.96, "MIA": 0.97, "MIN": 0.97,
    "DEN": 0.98, "LAL": 0.99, "PHX": 1.00, "SA": 1.01, "PHI": 0.99,
    "NOP": 1.00, "CHI": 1.00, "TOR": 1.01, "CHA": 1.03, "POR": 1.02,
    "UTA": 1.03, "DET": 0.99, "BKN": 1.02, "WSH": 1.04, "LAC": 0.98,
}


TEAM_ALIASES = {"UTAH": "UTA", "NO": "NOP", "NYK": "NY", "GSW": "GS", "SAS": "SA"}

def canonical_team(abbr: str) -> str:
    return TEAM_ALIASES.get(abbr, abbr)
