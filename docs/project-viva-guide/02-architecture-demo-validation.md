# 8. Architecture and code execution flow

## Module map

| Module | Important files/functions | Input → processing → output |
|---|---|---|
| App composition | `backend/application.py`, `core/lifecycle.py`, `bootstrap.initialize_application` | config → bootstrap/router registration → ASGI app |
| Auth | `services/authentication.py`, `routers/auth.py` | mobile/admin credentials → OTP/session validation → secure cookie/session |
| Vendors | `services/vendors.py`, `routers/vendors.py` | profile/registry → validation and merge → vendor DTOs |
| Recommendation | `recommendation/mcda_engine.py`, `decision_policy.py` | versioned snapshot + live state + profile → filter/score/rank → Top-N |
| Zone/capacity | `routers/zones.py`, `services/capacity_analysis.py` | official/live/association records → summaries → catalog/maps |
| Allocation workflow | `repositories/database.py`, `routers/allocations.py` | request/decision → locked transaction → request/allocation/audit updates |
| Batch planning | `allocation/allocation_planning_service.py`, `allocation_optimizer.py` | vendor IDs → demands/MCDA edges/MILP → advisory plan |
| Pilot slots | `geo/pilot_geometry.py`, `services/pilot_slots.py`, `routers/pilot_slots.py` | boundaries/drawings → validate/persist → layout and events |
| Navigation | `services/navigation.py` | origin + authorized target → routing service → walking route/fallback error |
| UI shell | `frontend/src/app/ImplementationApp.jsx` | session/URL → role navigation → admin/vendor workspace |
| Maps | `RecommendationMap.jsx`, `AdminZoneMap.jsx`, `PilotSlotMap.jsx` | API GeoJSON/state → Leaflet layers → interactive map |
| Offline GIS | `scripts/01...04...` | raw NMC/OSM → checked/versioned features/model/snapshot |
| Evaluation | `recommendation_evaluation.py`, `scripts/09...10...` | fixed artifacts/policy perturbations → metrics/reports |

## Startup and principal sequence

`backend.application:app` creates FastAPI, CORS and private/no-store middleware, then includes routers. The lifespan invokes ordered bootstrap: validate configuration/database, upgrade/seed the operational schema and seed historical identities. The frontend starts at `main.jsx`, loads `ImplementationApp`, calls `/api/auth/me`, and routes to login, onboarding, vendor, or admin UI.

```mermaid
sequenceDiagram
  actor V as Vendor
  participant UI as React UI
  participant API as FastAPI
  participant S as Recommendation service
  participant M as MCDA engine
  participant DB as Operational DB
  V->>UI: Open recommendations
  UI->>API: POST /api/recommendations
  API->>DB: Read vendor profile/live status
  API->>S: Resolve context and weights
  S->>M: score_candidates + rank_candidates
  M->>M: FREE/reference/live/division filters
  M->>M: six factors + weighted sum
  M-->>API: ranked Top-N with evidence
  API-->>UI: recommendation response
  UI-->>V: cards and Leaflet map
  V->>UI: Request zone/slot
  UI->>API: POST /api/allocation-requests
  API->>DB: transaction; reserve slot if selected
  DB-->>UI: PENDING request
  actor A as Officer
  A->>API: Approve request
  API->>DB: locked approval transaction
  DB-->>A: ACTIVE allocation / OCCUPIED slot
```

Precomputed operations: cleaning, GIS buffers/features, K-Means and candidate snapshots. Runtime operations: profile policy, live eligibility, MCDA factor calculation/ranking, requests, capacity checks and MILP when explicitly invoked. UI state changes after API responses or refetches; there is no WebSocket/event-stream layer.

# 9. Important formulas and parameters

| Formula/rule | Meaning and units | Example / edge case | Code |
|---|---|---|---|
| `log1p(max(x,0))/log1p(scale)` clipped [0,1] | diminishing return for count/density | at x=scale, score=1; larger stays 1 | `mcda_engine.py:149-165` |
| `exp(-d/scale)` | nearer is better | road d=400 m gives 0.3679 | `mcda_engine.py:168-184` |
| missing-aware weighted sum | comparable 0-100 score | missing factor weight leaves denominator rather than becoming zero | `mcda_engine.py:1369-1485` |
| smoothed share `(same + 20×prior)/(n+20)` | stabilize small historical samples | n=0 returns citywide prior | `mcda_engine.py:1179-1199` |
| lift `smoothed_share/prior` | category concentration relative to city | undefined if city prior is zero | `mcda_engine.py:1202-1214` |
| reliability `n/(n+20)` | shrink weak business evidence toward 0.5 | n=0 gives neutral 0.5 | `mcda_engine.py:1267-1288` |
| road density `clipped_length/buffer_area_km²` | mapped road intensity | 1000 m / 0.19635 km² ≈ 5093 m/km² for a 250 m circle | `02_build_zone_features.py:438-445` |
| Haversine `2R asin(sqrt(a))` | great-circle vendor-zone distance in km | experimental proximity only; absent coords stay missing | `location_ranking.py:100-108` |
| K-Means objective `Σ||x_i-μ_c||²` | inertia/WCSS in transformed feature space | active inertia 736.1383 | `04_train_kmeans.py:170-194` |
| group weight `1/sqrt(group size)` | equalizes total squared influence per environmental group | 3-feature group gives 0.577 per feature | `04_train_kmeans.py:66` |
| slot spacing `distance(poly_i,poly_j) ≥ spacing` | gap in metres | default 0.5 m, tolerance 0.002 m | `pilot_geometry.py:188-190` |
| capacity `current ≤ official`; available is difference | prevents over-allocation | unknown capacity cannot enter MILP | `database.py:96-117`; `allocation_optimizer.py:485-542` |
| MILP stage 2 cost | suitability loss + fallback + low coverage | score 80, no fallback, coverage .9 costs .2+.005=.205 | `allocation_optimizer.py:1330-1385` |

Library-handled operations include Shapely buffer/intersection/coverage/validity and scikit-learn centroid iteration. The project configures and validates them; it does not reimplement GEOS or Lloyd's algorithm.

# 10. Technical design decisions and alternatives

- **Why GIS?** Location suitability is spatial: proximity, neighbourhood counts, line density, containment and non-overlap cannot be represented truthfully as ordinary text fields.
- **Why OSM?** It supplies reproducible, open road/POI/land-use context. Its limitation is incomplete and uneven mapping, so absence is never claimed as real-world absence.
- **Why MCDA?** Evidence is heterogeneous, labels are absent, and officers need factor contributions. A supervised classifier would need validated outcomes.
- **Why clustering?** It summarizes environmental patterns and supports interpretation/quality checks. It is not required to score every zone and is deliberately excluded from the causal decision path.
- **Why K-Means?** With scaled numeric environmental variables it is simple, reproducible, fast and easy to profile. DBSCAN would identify noise and non-spherical density but requires an interpretable epsilon in the transformed 12-D space and would not guarantee profiles for all zones.
- **Why not cluster coordinates?** Geographic closeness is not the same as environmental similarity; coordinates would dominate city geography and obscure the intended profile.
- **Why slots?** A zone-level recommendation cannot guarantee a non-overlapping physical footprint or pedestrian corridor. Slot mapping makes site constraints explicit.
- **Why not use centroids as slots?** A cluster centroid is an abstract point in feature space, not a geographic/legal pavement location.
- **Why separate optimization?** MCDA evaluates each vendor-zone edge; the MILP resolves shared finite capacity across vendors. Ranking independently can produce conflicts.
- **What if weights change?** Scores/ranks may change; eligibility cannot. The saved sensitivity study found stable Top-1 for its one food/Nashik West case but only 56.7% identical ordered Top-3 across 224 scenarios. This is not universal stability.
- **What if a high score violates a restriction?** It is filtered before scoring/ranking. Scores never override NO_VENDING, RESTRICTED, closed/full status, missing capacity in production, or invalid geometry.
- **What if datasets are incomplete?** Missing factor weights are renormalized and coverage is exposed; missing reference geometry removes a zone; missing live state removes it in production mode.
- **Bias defence:** historical concentration may encode past policy/inequality. Shrinkage, leave-group-out evidence, explicit limitations and environmental factors reduce but do not eliminate bias. No demographic fairness audit exists.
- **Portability:** code and CRS/taxonomy are separable, but another city needs its own canonical zones, local UTM CRS, validated OSM extraction, live-status workflow, weights and site survey.
- **Scalability:** precomputation and spatial indexes make city-scale ranking cheap. MCDA is linear in candidate edges; MILP can grow with vendors×zones, hence max 500 and optional pool size.

# 11. Live demo presentation script

## Recommended 7-10 minute demo

1. **Problem and login (45 s).** Open `/login`; state that vendors use OTP and officers use admin login. Do not expose credentials or the console OTP. Explain two roles.
2. **Officer overview (60 s).** Open Overview. Show zone/request/allocation summaries and capacity warnings. Explain that operational state is separate from offline research evidence.
3. **Zones & maps (75 s).** Open “Zones & maps,” filter FREE/NO_VENDING or a division, and select a zone. Explain 308 official records, analytical references, and why map pins are not legal polygons.
4. **Vendor directory (45 s).** Open “Vendors,” search one record, and show category/history/current allocation. Explain the 7,259-record historical registry and audited associations.
5. **Vendor recommendations (2 min).** Log in as a prepared vendor or use a pre-authenticated vendor session; open Recommendations and a detail page. Show score, factor contributions, limitations and map. Explain hard filtering first, weighted MCDA second. Say K-Means describes the zone environment but does not set the score.
6. **Application (60 s).** Request an eligible zone/available pilot slot. Show PENDING status. Explain that requesting reserves a slot but does not allocate it.
7. **Officer approval (60 s).** Return to Applications, inspect and approve the prepared request. Show ACTIVE allocation and OCCUPIED slot. Explain transaction/uniqueness/capacity checks. Use a disposable demo record only; this changes DB state, so for a read-only viva use an already approved request instead.
8. **Vending slots (90 s).** Open “Vending slots,” select `NN_F_013` or an imported pilot. Show 2×2 footprints, boundary, spacing/corridor, status and warning. Emphasize provisional/not surveyed.
9. **Close (30 s).** State validation metrics and limitations: no success labels, no legal guarantee, OSM incompleteness, site survey required.

Likely examiner challenges: “Is the score accuracy?”—No, it is a transparent decision score. “Does K-Means recommend?”—No. “Are all 308 zones mapped?”—258 have usable environmental references; only eligible FREE references enter baseline ranking. “Does approval happen automatically?”—No, the MILP is advisory and officer approval commits.

Do not invent a “Generate citywide slots,” “Auto permit,” “Demand heatmap,” or “AI prediction accuracy” screen. They do not exist.

## Three-minute version

- 0:00-0:30: problem, roles and architecture.
- 0:30-1:15: officer zones map; explain official data + precomputed OSM context.
- 1:15-2:00: vendor recommendation detail; explain constraints then six-factor MCDA.
- 2:00-2:35: pilot slot map; explain UTM geometry, 2×2 m, spacing and provisional status.
- 2:35-3:00: request/approval/allocation and limitations.

# 12. Results, validation, and limitations

## What is actually measured

- GIS build: 308 total zones, 258 usable references, 50 missing; 250/500 m buffers and source counts are recorded in `feature_build_metrics.json`.
- Historical data: 7,259 vendors; 5,310 text associations; 1,777 review candidates; zero independent suitability labels (`training_data_metrics.json`).
- K-Means: K=2, silhouette 0.3406, DB 1.4645, CH 102.8891, inertia 736.1383, ARI stability 1.0, sizes 83/175 (`kmeans_run.json`). These are internal structure metrics, not suitability accuracy.
- MCDA sensitivity for one food/Nashik West request: 224 scenarios, Top-1 stability 100%, ordered Top-3 stability 56.7%, mean Top-3 retention 85.6%, minimum 66.7% (`mcda_sensitivity_summary.json`). It is one scenario, not a citywide accuracy result.
- Slot geometry: ten generated slots, containment/spacing/corridor PASS, 0.5 m minimum spacing, 1.2 m corridor, but unknown obstructions unassessed and site verification false (`geographic_validation.json`).
- Business-aware experiment: 96 scenarios, first-ranked zone changed in 13 and Top-3 membership in 24; result says do not activate without expert review (`reports/business_aware_mcda/evaluation_summary.md`).
- Test inventory: 226 Python + 76 JavaScript declared tests. No fresh pass rate was generated in this analysis.

## What the system cannot guarantee

It cannot guarantee legal permission, exact boundary, pedestrian footfall, sales/profit, safety, pavement width, accessibility compliance, current real-world vacancy without fresh officer verification, fair outcomes across protected groups, or ML predictive accuracy. The most serious limitations are provisional references, OSM incompleteness, historical bias, no outcome labels, pilot-only slot coverage, and no independent field validation.

Appropriate next validation is: survey a stratified sample with municipal/GIS experts; measure coordinate error and site constraints; collect blinded expert suitability ratings; test inter-rater agreement; compare MCDA ranking with expert judgments using Spearman/NDCG/Top-K; pilot allocations and observe lawful occupancy/retention without treating profit as the only outcome; perform subgroup/fairness and sensitivity audits; and version data/model policy when roads or POIs change.

