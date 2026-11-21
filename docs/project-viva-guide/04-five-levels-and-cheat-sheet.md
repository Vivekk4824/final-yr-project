# 14. Teach me the complete project at five levels

## Level 1 — 60-second overview

“VendorMap is an explainable geospatial decision-support system for Nashik street-vendor zoning and allocation. We combine official municipal zone and vendor records with precomputed OpenStreetMap road, transport, commercial and facility context. The system first applies hard eligibility rules such as FREE zone type, usable reference, live OPEN status and capacity. It then ranks eligible zones with a transparent six-factor weighted MCDA. K-Means separately profiles environmental zone types; it does not make the recommendation. For selected pilot zones we validate physical slot footprints in a metric coordinate system, maintain spacing and pedestrian clearance, and track slot status. Vendors submit requests, officers approve them transactionally, and an optional two-stage MILP can prepare a capacity-aware batch plan. The system is decision support—not a permit, profit predictor or legal guarantee.”

## Level 2 — five-minute overview

Start with the fragmented-data problem: 308 official zones, 7,259 historical vendor rows, text-to-zone associations, incomplete map references and live capacity. Explain the offline pipeline: validate → resolve references → project to UTM → build 250/500 m features → K-Means profile → versioned candidate snapshot. Then explain runtime: vendor OTP/profile → FREE/reference/live/division filters → six normalized factors → weighted score/Top-N → optional slot request → officer approval → active allocation. Finish by separating K-Means, MCDA, geometry and MILP, and state the evidence limits.

## Level 3 — 15-minute technical explanation

1. Show `data/catalog.json` and active `manual-142-v2` version.
2. Explain fixed point buffers, nearest geometry, POI counts, road-density intersection and UTM 43N.
3. Explain K-Means preprocessing and K=2 selection metrics; state it is descriptive.
4. Derive the six MCDA factors, scales, weights and missing-data formula.
5. Work through `NW_F_025` to 69.8551 and explain why this is not probability.
6. Explain hard operational filters and seven-day verification.
7. Explain generated/imported/drawn slot paths and 2×2/0.5/1.2/0.25/0.002 constants.
8. Trace PENDING→RESERVED and APPROVED→ACTIVE/OCCUPIED transactions.
9. Define MILP variables/constraints and two-stage objective.
10. Present measured validation and the absence of labels/legal guarantee.

## Level 4 — deep technical understanding

Use the full derivations and code references in the first two documents. Be ready to distinguish:

- source feature versus factor score versus weighted contribution;
- proximity transform versus Haversine distance;
- environmental cluster versus suitability rank;
- analytical zone reference versus surveyed legal polygon;
- candidate footprint versus valid/reserved/allocated slot;
- independent ranking versus capacity-coupled optimization;
- artifact metric versus real-world validation.

The key invariant is “constraints first, score second, approval last.” Missing or restricted evidence cannot be rescued by a high score. Every stage exposes provenance/limitations rather than silently inventing certainty.

## Level 5 — external examiner challenge

- **“Your model has no accuracy. Why call it intelligent?”** Call it an explainable decision-support model, not predictive AI. Its value is reproducible spatial evidence, transparent policy aggregation and constraint-safe workflow.
- **“Historical vendors create circular reasoning.”** Correct risk. The code uses historical evidence only as contextual factors, applies shrinkage and leave-group-out removal, and never labels historical presence as success. Further expert/outcome validation is required.
- **“K-Means K=2 is weak with silhouette 0.34.”** It indicates modest separation, not failure or suitability accuracy. K=2 was selected for stability, size and interpretability; clusters are descriptive and non-authoritative.
- **“Your slots may block real pedestrians.”** Computational clearance is only a provisional assumption. The report explicitly says unknown obstructions and site verification are incomplete; field survey is mandatory.
- **“Why does the optimizer not allocate automatically?”** Administrative allocation has legal and operational consequences. The planner is deliberately read-only; an authenticated officer reviews and commits through an audited transaction.
- **“Can a high score place a vendor in a no-vending zone?”** No. Zone type/live restrictions are hard filters before scoring.
- **“Is OSM reliable enough?”** It is useful open context, but incomplete. The system exposes coverage/missingness and requires municipal/site verification.
- **“Is fairness solved?”** Only maximum assignment count precedes score in the MILP. Protected-group, waiting-time and livelihood fairness need policy variables, data and audit; claiming them now would be false.

# 15. One-page revision cheat sheet

## One-line definition

Explainable GIS + MCDA recommendation, provisional slot mapping, audited allocation workflow, and advisory capacity optimizer for Nashik street-vendor management.

## Numbers to remember

- 308 official zones; 7,259 historical vendor records.
- 258 usable GIS references; 50 missing.
- 250 m and 500 m buffers; EPSG:32643 metric CRS.
- 12 K-Means features; 258 training rows; K=2; sizes 83/175.
- K-Means: silhouette .3406, ARI stability 1.0, `n_init=20`, seeds 42-46.
- Six MCDA weights: 25%, 20%, 20%, 15%, 10%, 10%.
- Historical shrinkage 20; history saturation scale 50.
- Commercial scales 12/4/8; access scales 400 m/1000 m/5000; facility scales 15/6/3/4.
- Live verification maximum age: seven days.
- Generated slots: 2×2 m; 0.5 m spacing; 1.2 m corridor; 0.25 m search; 0.002 m tolerance; maximum ten.
- MILP: max 500 vendors; 30 s; stage-2 weights 1.0/0.10/0.05.

## Six MCDA factors

`Business .25 + Commercial .20 + Access .20 + Facilities .15 + Preference .10 + Historical density .10`.

Score formula: `100 × weighted available factor sum / available weight sum`.

Hard filters: FREE + usable reference + not excluded + optional OPEN/positive capacity + optional recent verified officer snapshot + strict selected division.

## Never confuse these

- MCDA ranks; K-Means profiles; geometry forms/validates slots; MILP resolves capacity conflicts; officer approval allocates.
- A score is not probability.
- A reference point is not a legal boundary.
- FREE is not a permit.
- Mapped POIs are not footfall.
- Historical presence is not business success.
- Internal cluster metrics are not recommendation accuracy.
- Computational slot validity is not a field survey.

## Best worked examples

- `NW_F_025`: actual stored balanced factor scores produce 69.8551.
- MILP conflict: flexible A uses Y so constrained B can use X; two assigned instead of greedy one.
- Slot `NN_F_013`: five rectangles per boundary with continuous corridor and validated spacing.

## Strong closing statement

“The strength of VendorMap is not pretending uncertain data is ground truth. It separates evidence, policy, geometry, optimization and administrative authority, records provenance and limitations, and produces explainable recommendations that an officer can verify rather than blindly accept.”
