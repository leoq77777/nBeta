# Additive v1 production single-game model

The accepted Additive research candidate now has a frozen NumPy-only serving implementation. Scheduled game probabilities, spreads and expected scores use this model when the server has an active verified bundle. Season simulations, team rating tables and the explicitly labelled legacy sandbox retain the previous engine; no season-simulation acceptance is inferred from single-game benchmark results.

## Artifact and training

`models/additive-v1.json` stores coefficients, training-only feature means/scales, dynamic-filter configuration, joint-score residual parameters and provenance hashes. It is refitted on all 13,209 historical completed regular-season games, through 2025–26. Hyperparameters are frozen to those selected for the final historical fold; there is no new tuning against 2026–27 labels. Daily updates change features and dynamic state, not trained weights.

The feature implementation in `pipeline/additive_features.py` is promoted from the accepted experiment. Conformance checks reproduce all 13,209 historical feature rows and dynamic predictions, and the final fold's 1,230 out-of-sample probabilities and total means. Serving uses the same 66 margin and 74 total features, with no new regression family or lineup interactions.

The private `history.json.gz` contains historical source inputs required to replay the lagged state. It is deployed outside the public web root; its SHA256 is pinned in the public model artifact. Historical source publication times remain uncertified, as documented in the research report.

## Live inference and quality

After daily score and player-box collection, `pipeline.additive.activate` validates the model, feature-code and history hashes, conservatively normalizes current-season boxes, rebuilds lagged features and runs inference. Outcomes enter at assumed tip+6h, predictions use min(T−24h, build time) as their modeled information cutoff. Actual forecast capture time is independently preserved by the forward ledger; late captures never become T−24h forecasts.

Unknown non-DNP statistics, ambiguous identities and nonconserved team scores/minutes quarantine a team box instead of zero filling. Final/OT and numbered OT labels are parsed when period counts are absent. At least 90% of live finalized team boxes must validate; held boxes and source hashes are exposed in `data/additive_model.json`. All game labels remain included. A held box leaves earlier player state in place, so data gaps can produce stale roster features.

Full feature vectors, additive group contributions and the frozen artifact hash accompany each forecast. The total/margin joint-normal approximation yields both expected team scores. It does not explicitly simulate overtime or model true possession counts, live injury announcements, five-player stints or pairwise defensive matchups. Distant schedule projections use current available state and are refreshed daily; they are not claims of knowing future lineups.

## Switching, trace and rollback

- Runtime bundle: `/home/ubuntu/projects/nbeta/models/additive-v1/{model.json,history.json.gz}`.
- Active selection: `/home/ubuntu/projects/nbeta/models/active` symlink.
- Each build saves `legacy_prediction_traces.json` and the previous single-game values as shadow comparators, then publishes Additive scheduled-game forecasts.
- `run.json` explicitly names the single-game and season models. Model & audit distinguishes live Additive from the legacy historical scorecard and season-model description.
- The append-only forward ledger evaluates Additive and legacy separately by model/artifact version and records joint-score errors for Additive.
- Corrupt configured bundles or insufficient live inputs fail publication and retain the previous current snapshot. There is no silent fallback while a bundle is configured.
- Intentional rollback: disable the active bundle symlink and run the snapshot service. The resulting snapshot explicitly identifies Legacy Student-t. Existing forecast evidence must never be deleted or overwritten.

## Verification

Local and server conformance receipts are retained under `benchmark/results/additive_release_v1/`. Integration tests cover active/shadow settlement, no-past-data backfill, frozen-artifact failure, unknown-stat quarantine, overtime minutes, expected-score identities and source/version separation. Historical benchmark scores are development evidence; live forward evaluation is ongoing.
