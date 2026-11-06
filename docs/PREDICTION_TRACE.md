# Live forecast trace and forward feed

The daily snapshot job now appends forecast evidence and joins later final results. The active Additive stages are dynamic baseline, team/history feature correction and player feature correction, sharing its normal margin variance. The legacy Student-t model is retained as a separately versioned shadow with strength, availability/recovery and context stages. These are ordered ablations, not causal contributions. True lineup interactions remain unavailable.

## Capture and settlement

- Every successful build exports `data/prediction_traces.json`, including unrounded stage margins/probabilities, the margin distribution, recovery weight, raw rating inputs and schedule context.
- Before switching `current`, the server retains the completed snapshot, validates traces against the published rounded schedule, and appends events to `/home/ubuntu/projects/nbeta/forward_ledger/events.jsonl` under an exclusive lock with fsync.
- Predictions are captured only for future games within seven days. Each record stores actual capture time, scheduled tip, snapshot, immutable code hash and input seed hashes. No pre-deployment predictions are backfilled.
- The primary evaluation selects the most recent forecast per model version recorded at or before T−24h. Earlier reschedules recheck eligibility against both forecast and result tip. Late forecasts remain evidence but never enter the primary cohort.
- Results are collected only for games scheduled after ledger activation. Games without an eligible prediction are excluded with an explicit reason. Later score corrections append new outcome events; earlier evidence remains intact. Each rebuild recomputes diagnostics from latest observed results without changing forecast records.
- Ledger hash chaining detects edited events, but is not an externally trusted timestamp or cryptographic proof against an operator who rewrites the entire chain. Source priors, roster/player values and injuries retain their existing verification limitations.
- Model versions are kept separate. The daily feed does not retrain, tune weights or infer improvement from individual misses.

## Reports

Every newly published immutable snapshot includes:

- `data/trace_report.json`: cohort counts, stage Log Loss/Brier/MAE, ordered loss changes, calibration bins, standardized residual moments, B2B groups, team residual histories and the twenty largest final-stage Log Loss errors.
- `data/trace_games.json`: all eligible settled forecasts, immutable forecast/outcome hashes and per-stage residuals.
- `data/prediction_traces.json`: current upcoming-stage forecasts.

The Model & audit page exposes diagnostics and downloads using its pinned backend snapshot. Additive joint-score diagnostics are calculated only for eligible actual Additive forecasts; legacy forecasts never receive fabricated score totals. Zero settled games initially means evidence is accumulating, not that performance is perfect.

Positive delta Log Loss or squared error means that stage worsened prediction versus the immediately preceding stage. One-game errors and subgroup calibration are descriptive, not causal findings or upgrade tests.

## Operations

Existing systemd schedule is retained: 23:00, 23:30 and 00:00 America/Los_Angeles. On November 6, 2026 these are 02:00, 02:30 and 03:00 America/New_York. The first eligible settlements require captured forecasts followed by completed games; the first scheduled feed may have no settlements.

```sh
systemctl list-timers nbeta-refresh.timer --all
journalctl -u nbeta-refresh.service -n 30 --no-pager
python -m unittest discover -s tests -p 'test_trace.py' -v
```

If trace validation or ledger integrity fails, publication does not switch the current pointer and systemd reports failure. A completed but unpublished snapshot may remain for investigation. Ledger entries refer to persisted computed forecasts; a failure switching the pointer does not imply every captured forecast appeared on the homepage.
