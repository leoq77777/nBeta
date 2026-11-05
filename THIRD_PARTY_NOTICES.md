# Third-party sources

- `assets/d3.v7.min.js`: D3 v7.9.0, Copyright 2010–2023 Mike Bostock; ISC license retained in `assets/D3-LICENSE.txt`. Source: https://github.com/d3/d3/tree/v7.9.0 .
- Six seed CSV files match the public export at https://github.com/chronicaria/chronicaria.github.io/tree/dc200d996eb9f7daa7790bad91c088d50821b65b/data . Upstream calculations, priors and player values have not been independently verified. `data/seed/logos.json` also originates from that public repository. Detailed provenance, hashes and discrepancies appear in `docs/SEED_VERIFICATION.md` and `data/verification/seed_audit.json`.
- External verification uses public ESPN schedule, roster and box-score endpoints. Generated `data/` files derive from the supplied snapshot and this project's offline pipeline.

Attribution does not change the rights in upstream data, team marks or third-party software. No project-wide license is assigned by this release.
