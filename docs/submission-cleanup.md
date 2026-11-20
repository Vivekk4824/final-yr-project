# VendorMap submission cleanup

The working layout stays centered on `frontend/`, `backend/`, and `data/`. Frontend features, shared components and locale dictionaries already have separate directories. FastAPI routers, services, schemas, GIS and database access already have separate packages. Data and model versions remain under their cataloged paths. The demo entry points and the recommendation implementation stay in place.

## Moved to the archive

Each listed directory moved in full from `reports/` to `extra/reports/`. The archive preserves the previous directory structure. File contents were checked during the move, followed by repair of relative documentation links.

| Previous directory | Archive directory | Files |
| --- | --- | ---: |
| `reports/architecture-refactor/` | `extra/reports/architecture-refactor/` | 26 |
| `reports/business_aware_mcda/` | `extra/reports/business_aware_mcda/` | 9 |
| `reports/figures/` | `extra/reports/figures/` | 2 |
| `reports/kmeans/` | `extra/reports/kmeans/` | 11 |
| `reports/pilot_slots/` | `extra/reports/pilot_slots/` | 1 |
| `reports/production-readiness/` | `extra/reports/production-readiness/` | 1 |
| `reports/slot-workspace/` | `extra/reports/slot-workspace/` | 1 |
| `reports/synthetic_demo/` | `extra/reports/synthetic_demo/` | 19 |
| `reports/ui-refinement/` | `extra/reports/ui-refinement/` | 20 |
| `reports/vendormap/` | `extra/reports/vendormap/` | 23 |
| **Total** | | **113** |

The K-Means evaluation and plotting scripts, business-aware evaluation, synthetic experiment, final input audit, and browser report writers now point to the archive. Documentation links and historical checksum manifest paths were updated. The recorded checksum values were preserved.

## Deleted

- `.npm-cache/` and `.pytest_cache/`, containing 12 regenerable package-manager and test cache files.
- Ten project `__pycache__/` directories under `backend/`, `scripts/`, and `tests/`, containing 94 compiled Python files.

The 106 cache files occupied approximately 39.4 MiB.

## Retained

- `frontend/src/`, both test suites, `frontend/vercel.json`, `frontend/vite.config.js`, package and dependency manifests, frontend tools, and the verified production build in `frontend/dist/`.
- `backend/`, including the recommendation engine, 85/15 policy, K-Means K=2, feature flags, existing API behavior, and database initialization and migration entry points.
- `data/` and `models/`, including the active and rollback model versions, coordinates, GIS files, and the operational database file. Cleanup verification uses isolated databases.
- `reports/data_quality/`, `reports/expert_review/`, `reports/ahp_calibration/`, `reports/metrics/`, and `reports/recommendation_evaluation/`. These paths are referenced by API or GIS consumers, research tools, or rollback and CLI workflows.
- `research-paper/`, `docs/`, `README.md`, `app/`, `research/`, and `scripts/`. The installed environments `.venv/` and `frontend/node_modules/` were retained for the demo.
- `frontend/.tsupgrader/`. Windows denied the directory move, so its existing validation artifacts were retained in place.

The [recommendation validation](../extra/reports/vendormap/final-recommendation-input-validation.md) and [274-scenario CSV](../extra/reports/vendormap/final-recommendation-input-validation.csv) are in the archive. [Startup and hosting commands](deployment.md) remain in the deployment guide.

## Verification

- The development FastAPI entry point started with disposable SQLite. The Render Uvicorn command started locally with production settings and disposable PostgreSQL 17. Both served a healthy response and the same 258-feature GIS payload. For Food in Nashik West, both returned the same deterministic Top 3 of `NW_F_025`, `NW_F_007`, and `NW_F_017`.
- A Vercel-mode production build passed, along with 75 frontend checks covering the Vercel rewrites, LAN proxy, PWA and recommendation explorer. Headless Edge passed the six-input preference flow, mobile map picker, saved preferences, Expand Search, and English, Marathi and Hindi.
- The full backend run finished with 212 passing and 10 failing tests. The same ten tests failed before cleanup. Seven involve the incomplete local saved-pilot GIS fixture and three compare against legacy API, asset or implementation snapshots. The two PostgreSQL integration cases ran in the post-cleanup suite and accounted for the two baseline skips.
- Hosted Vercel and Render services are outside the scope of local verification. The existing deployment configuration remains in place.
