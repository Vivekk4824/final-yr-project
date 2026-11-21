# 13. Seventy-two project-specific viva questions and answers

Each entry is structured as **simple answer — technical explanation — code evidence**.

## Problem and objectives

1. **What exact problem does VendorMap solve?** It supports municipal zone recommendation and controlled allocation. — It joins official eligibility/capacity, GIS context, vendor preferences, physical pilot slots and approvals; it does not predict profit. — `backend/recommendation/mcda_engine.py`; `backend/repositories/database.py`.
2. **Why is a normal map insufficient?** A map displays geometry but does not rank evidence or enforce capacity/workflow. — VendorMap adds MCDA, live filters, slot validation, transactions and an advisory MILP. — `backend/application.py`.
3. **Who are the main users?** Vendors and NMC officers. — Sessions enforce VENDOR, ADMIN and onboarding roles. — `backend/services/authentication.py:465-633`.
4. **What is the primary project objective?** Explainable decision support, not autonomous permitting. — Outputs explicitly say score is not success probability and plan is advisory. — `mcda_engine.py:1805-1823`; `allocation_optimizer.py:207-211`.
5. **What is the strongest novelty?** Connecting zone-level evidence, live municipal state, site-level slots and audited allocation. — Most GIS viewers stop at visualization. — `backend/routers/` and `frontend/src/features/`.

## Architecture and stack

6. **Why React and FastAPI?** React supports role-based interactive maps; FastAPI supports typed modular APIs. — Vite builds the UI and Pydantic validates request bodies. — `frontend/package.json`; `backend/application.py`.
7. **Why SQLAlchemy Core?** It provides portable transactional SQL without requiring a heavy ORM domain model. — The same metadata targets SQLite and PostgreSQL. — `backend/repositories/database.py:1-40`.
8. **What happens at startup?** Configuration and database are validated, schema/zone rows are initialized, and identities are seeded. — The lifespan calls ordered idempotent bootstrap. — `backend/bootstrap.py`.
9. **How do modules communicate?** The UI calls REST endpoints; routers call services/algorithms/repository; the DB stores operational state. — Offline artifacts are read from the versioned catalog. — `frontend/src/services/api.js`; `data/catalog.json`.
10. **What is precomputed versus real time?** GIS features/K-Means/snapshots are precomputed; profile weights, live filtering, MCDA ranking and transactions run at request time. — This avoids expensive GIS processing per click. — `scripts/02...04`; `mcda_engine.score_candidates`.
11. **Can the backend use PostgreSQL?** Yes. — `DATABASE_URL` accepts PostgreSQL and migrations/portable schema exist; SQLite is default. — `backend/core/config.py`; `scripts/migrate_sqlite_to_postgres.py`.

## Geographic datasets and preprocessing

12. **What are the core data sources?** NMC-derived zone/vendor tables and cleaned OSM layers. — The active catalog pins exact versioned paths. — `data/catalog.json`.
13. **How many official zones and vendors are present?** 308 zones and 7,259 historical vendor rows. — These are checked-in artifact counts, not live city totals. — `official_zones.csv`; `training_data_metrics.json`.
14. **Why use EPSG:32643?** It is a metric UTM CRS suitable for Nashik. — Metres are needed for 250/500 m buffers, spacing and area. — `scripts/02_build_zone_features.py:32`; `pilot_geometry.py:23-24`.
15. **Why not calculate metre buffers in latitude/longitude?** Degrees have nonuniform physical length. — The code projects before buffer/distance operations and converts back for maps. — `pilot_geometry.metric/geographic`.
16. **How are nearby POIs counted?** A fixed point buffer is queried through a spatial index and exact intersection. — Cleaned distinct records, not raw tag occurrences, are counted. — `02_build_zone_features.py:171-199,426-437`.
17. **How is road density calculated?** Intersected road length divided by circular buffer area in km². — Raw length is retained for audit. — `02_build_zone_features.py:438-445`.
18. **How are overlapping land-use polygons handled?** Their union area is used. — This avoids double-counting overlap; mapped shares require at least 10% classified coverage. — `02_build_zone_features.py:446-469`.
19. **Does zero OSM POIs mean none exist?** No. — It means none are mapped in that cleaned layer; reports explicitly warn about incomplete coverage. — `feature_build_metrics.json`.
20. **Are zone geometries legal boundaries?** No. — Most are analytical/provisional references; `official_boundary_verified` is false in this pipeline. — `02_build_zone_features.py:386-397`.
21. **What happens to missing geometry?** Geometry-derived factors remain NaN and baseline eligibility excludes the zone. — Missing is never fabricated as zero. — `02_build_zone_features.py:400-402,473-494`; `mcda_engine.py:696-722`.

## MCDA and suitability

22. **Which MCDA method is used?** Missing-aware weighted summation. — It is neither TOPSIS nor active AHP. — `mcda_engine._calculate_mcda`.
23. **What are the six factors?** Business, commercial, access, facilities, preference and historical evidence. — Factor order and weights are explicit. — `decision_policy.py:37-67`.
24. **What are the baseline weights?** 0.25, 0.20, 0.20, 0.15, 0.10 and 0.10 respectively. — They are research/policy assumptions, not learned coefficients. — `decision_policy.py:47-67`.
25. **How are counts normalized?** Logarithmic saturation with a documented scale and clipping. — This models diminishing returns. — `mcda_engine.py:149-165`.
26. **How are distances normalized?** Exponential decay `exp(-d/scale)`. — Major-road scale is 400 m and bus-access scale is 1000 m. — `mcda_engine.py:109-120,168-184`.
27. **How is missing factor data handled?** Its weight is omitted and the available weights are renormalized. — Coverage exposes how much evidence remained. — `mcda_engine.py:1385-1453`.
28. **Is there a suitability cutoff?** No. — Hard rules decide eligibility; score ranks survivors. — `mcda_engine.py:1581-1678,1889-1998`.
29. **How are ties resolved?** Score descending, original score descending, zone ID ascending. — This makes results deterministic. — `mcda_engine.py:1854-1873`.
30. **What is business compatibility?** Smoothed historical category concentration relative to citywide share. — It is not demand, profit or success. — `mcda_engine.py:1179-1288`.
31. **Why shrink historical evidence?** Small samples are unstable. — Strength 20 pulls weak zones toward the city prior/neutral score. — `mcda_engine.py:131-132,1179-1288`.
32. **How is vendor self-leakage controlled?** The historical vendor's whole location group is removed before scoring. — If unavailable, its vendor ID is removed. — `mcda_engine.py:1077-1106`.
33. **Is division a factor or constraint?** A selected division is a hard constraint. — Its preference weight becomes zero and is redistributed to prevent double reward. — `decision_policy.neutralize_constrained_division_weight`.
34. **Is AHP used?** AHP calculation utilities are implemented, but active weights are not expert-validated AHP output. — No reviewed policy replaces the versioned baseline. — `decision_policy.py:456-714`.
35. **Why MCDA instead of machine learning?** There are zero independent suitability labels. — Historical presence is contextual and cannot safely be treated as success or negatives. — `training_data_metrics.json`.
36. **What does score 70 mean?** A weighted evidence score of about 70/100 under the current policy. — It is not 70% probability, accuracy or legal confidence. — `mcda_engine.py:1805-1823`.
37. **What if weights change?** Contributions and ranking can change, but constraints remain. — The sensitivity module measures Top-K/rank robustness. — `recommendation_evaluation.py`.

## K-Means and clustering

38. **Why is clustering used?** To describe environmental zone profiles. — It is not the suitability decision or slot generator. — `scripts/04_train_kmeans.py`.
39. **What is clustered?** 258 zone reference points represented by 12 environmental variables. — Coordinates and vendor outcomes are excluded. — `kmeans_run.json`.
40. **What preprocessing is used?** log1p, 1/99 percentile clipping, median imputation, standardization and group balancing. — Fitting uses only the training population. — `04_train_kmeans.py:55-76`.
41. **What distance does K-Means use?** Euclidean distance in transformed 12-D feature space. — It does not use Haversine/geographic distance. — scikit-learn `KMeans` at `04_train_kmeans.py:170`.
42. **What is active K?** K=2. — The saved clusters contain 83 and 175 rows. — `kmeans_run.json`.
43. **How was K chosen?** Stability/size eligibility, then highest mean silhouette with smaller K within 0.01. — Evaluations use five seeds and `n_init=20`. — `04_train_kmeans.py:149-170`.
44. **What does inertia mean?** Sum of squared distances to assigned centroids. — Active inertia is 736.1383 in transformed space; lower alone cannot select K because it always falls with K. — `kmeans_run.json`.
45. **Were DBSCAN or OPTICS used?** No. — No active source or artifact implements them. — repository search plus `scripts/04_train_kmeans.py`.
46. **Are clusters spatial zones?** Not necessarily. — Points with similar environment can be far apart, because coordinates are excluded. — `04_train_kmeans.py:33-43`.
47. **Does cluster ID affect MCDA?** No. — Saved audits explicitly state clusters did not alter eligibility or scores. — `reports/kmeans/.../k_selection_summary.md`.

## Slot generation

48. **What exactly is a vending slot?** A rectangular, status-bearing GeoJSON footprint in a pilot zone. — It is stored with dimensions, center, geometry, links and audit events. — `database.py:270-307`.
49. **Where are slots automatically generated?** Only the `NN_F_013` two-boundary pilot. — Three other layouts are imported and `PAN_F_031` is manually drawn. — `services/pilot_slots.py:22-24,568-586`.
50. **What are default slot dimensions?** 2 m × 2 m for the generated pilot. — Imported/drawn layouts preserve their supplied/measured dimensions. — `pilot_geometry.py:83-89,173-178`.
51. **How is spacing enforced?** Polygon-to-polygon metric distance must be at least 0.5 m by default. — A 0.002 m tolerance handles floating point. — `pilot_geometry.py:25,110,188-190`.
52. **How is pedestrian clearance handled?** A continuous adjoining corridor defaults to 1.2 m and must not overlap slots/obstructions. — For imported layouts it is explicitly unverified. — `pilot_geometry.py:151-195,233-237`.
53. **How are slot coordinates produced?** A deterministic 0.25 m grid search in a rotated UTM frame. — It keeps the longest feasible run up to five per boundary. — `pilot_geometry.py:294-370`.
54. **How are overlaps prevented?** Exact polygon intersection area checks and DB conflict checks. — IDs are unique and persisted with a compound key. — `pilot_geometry.validate_layout`; `database.py:276-297`.
55. **How is capacity respected?** Generation caps the pilot count, imports verify expected counts, and manual drawing cannot exceed official capacity. — `pilot_geometry.py:143-144,221-222`; `pilot_slots.py:467-492`.
56. **Are slot locations legally verified?** No. — Their validation state is `ILLUSTRATIVE_UNVERIFIED` and field survey remains required. — `database.py:290`; `geographic_validation.json`.

## Allocation and optimization

57. **How does a vendor get a slot?** The vendor requests an available slot and an officer approves it. — PENDING reserves; approval creates ACTIVE/OCCUPIED state. — `database.py:1264-1384,1646-1846`.
58. **What prevents two vendors taking one slot?** Unique partial indexes plus locked transactional checks. — Separate constraints cover pending requests and active allocations. — `database.py:140-167`.
59. **Is allocation automatic?** No. — The optimizer is advisory; the approval workflow commits. — `allocation_optimizer.py:1-16`.
60. **Which optimization method is implemented?** Two-stage pre-emptive goal-programming MILP. — Stage 1 maximizes assignment count; Stage 2 minimizes quality penalties. — `allocation_optimizer._solve_model`.
61. **What are the decision variables?** Binary vendor-zone edges and binary unassigned variables. — Each vendor must choose exactly one edge or unassigned. — `allocation_optimizer.py:1037-1194`.
62. **What are the hard constraints?** One outcome per vendor and zone capacity not exceeded. — Unknown/nonpositive capacity creates no feasible edge. — `allocation_optimizer.py:983-988`; `_known_positive_capacity`.
63. **How is fairness represented?** Maximum number assigned is lexicographically prior to score. — Demographic, waiting-time and income fairness are not implemented. — `allocation_optimizer.py:1245-1419`.
64. **What happens when no slot/capacity exists?** The vendor remains explicitly unassigned or the request is rejected with a conflict. — The MILP stays feasible through `u_v`. — `allocation_optimizer.py:1166-1194`.
65. **How are relocations handled?** The current zone is excluded and active allocation state is replaced only through approval. — The planner labels demand RELOCATION. — `allocation_planning_service.py:355-390`.
66. **Why can the MILP beat greedy first-come-first-served?** It considers conflicts jointly. — It may assign a flexible vendor to a second-best zone so a constrained vendor can use the only feasible zone, maximizing total assignments. — `allocation_optimizer.py:958-1461`.

## Testing, limitations and future scope

67. **How was MCDA validated?** By deterministic tests and weight-sensitivity/ranking-stability analysis, not predictive accuracy. — One saved study has 224 scenarios. — `reports/recommendation_evaluation/`.
68. **How was clustering validated?** Silhouette, Davies-Bouldin, Calinski-Harabasz, inertia, cluster size and seed ARI. — These only measure internal structure. — `04_train_kmeans.py:78-108`.
69. **How was slot geometry validated?** Exact dimension, validity, containment, spacing, corridor and obstruction rules. — The saved pilot passes computational rules but lacks field verification. — `pilot_geometry.validate_layout`; report JSON.
70. **What is the largest scientific limitation?** No independent suitability/outcome labels. — Therefore historical associations and MCDA cannot be called predictive accuracy. — `training_data_metrics.json`.
71. **Can the system prove legality?** No. — It can exclude recorded NO_VENDING/restricted states, but site/legal verification is external. — `mcda_engine._apply_live_filter`.
72. **How would you improve it?** Add authoritative surveyed boundaries/live capacity, field-observed access/safety/footfall, expert labels, fairness review and longitudinal pilot outcomes. — Version and revalidate rather than silently replacing artifacts. — `data/catalog.json` version workflow.

