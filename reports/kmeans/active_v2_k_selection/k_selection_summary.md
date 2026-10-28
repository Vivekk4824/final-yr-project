# Active manual-142-v2 K-Means selection experiment

Generated UTC: 2026-10-15T18:11:29.877932+00:00

## Method

- Active feature source: `data\model\versions\manual-142-v2\features\zone_features.csv` (SHA-256 `253ecc5cd1bb980377b0e1588c3cc6f9207a62aaf87e731dd13e92d538150cc3`)
- Evaluation population: 258 zones with usable environmental references.
- Features: distance_to_major_road_m, road_density_250m_per_km2, pedestrian_road_density_250m_per_km2, commercial_poi_count_250m, market_poi_count_500m, food_poi_count_250m, bus_count_500m, distance_to_bus_access_m, healthcare_count_500m, education_count_500m, toilet_count_500m, parking_count_500m.
- Preprocessing: log1p; 1st/99th percentile clipping; median imputation; StandardScaler; equal environmental-group weighting.
- Seeds: [42, 43, 44, 45, 46]; KMeans n_init=20; K evaluated: [2, 3, 4, 5, 6].
- Excluded from clustering: identity, coordinates, capacity, occupancy, division, zone type, historical vendors, business categories, MCDA scores and preferences.

## Selection

Recommended experiment result: **K=2**. It has the highest silhouette, perfect seed stability, and the most balanced usable cluster sizes. K=4 adds interpretive detail and slightly improves Davies-Bouldin, but lowers silhouette and its selected run has a 21-zone cluster alongside a 160-zone cluster (one seed produced an 18-zone minimum). K=5 and K=6 create 3-zone fragments and are less stable.

The recreated K=2 assignment has label-invariant ARI 1.000000 against the stored active assignments; the production model remains unchanged.
The v1-versus-v2 stored K=2 assignments have ARI 0.984266 across 258 common assigned zones. 4 common feature rows changed in at least one selected environmental feature.

## Recommendation-profile distribution

- K=2: cluster 0: 245 (85.1%), cluster 1: 43 (14.9%)
- K=3: cluster 0: 123 (42.7%), cluster 1: 38 (13.2%), cluster 2: 127 (44.1%)
- K=4: cluster 0: 139 (48.3%), cluster 1: 31 (10.8%), cluster 2: 96 (33.3%), cluster 3: 22 (7.6%)
- K=5: cluster 0: 22 (7.6%), cluster 1: 123 (42.7%), cluster 2: 127 (44.1%), cluster 3: 16 (5.6%)
- K=6: cluster 1: 139 (48.3%), cluster 2: 96 (33.3%), cluster 3: 18 (6.2%), cluster 4: 4 (1.4%), cluster 5: 31 (10.8%)

These counts describe cluster membership across the 288 Top-3 positions from the existing 96-scenario MCDA audit. Clusters did not alter eligibility, scores, division filtering or ranking.

### Differentiation within preferred divisions

- K=2: Nashik East: 2 profile(s), Nashik Road: 1 profile(s), Nashik West: 2 profile(s), New Nashik: 1 profile(s), Panchavati: 1 profile(s), Satpur: 2 profile(s)
- K=3: Nashik East: 2 profile(s), Nashik Road: 2 profile(s), Nashik West: 2 profile(s), New Nashik: 1 profile(s), Panchavati: 1 profile(s), Satpur: 2 profile(s)
- K=4: Nashik East: 2 profile(s), Nashik Road: 2 profile(s), Nashik West: 4 profile(s), New Nashik: 1 profile(s), Panchavati: 1 profile(s), Satpur: 2 profile(s)
- K=5: Nashik East: 2 profile(s), Nashik Road: 2 profile(s), Nashik West: 2 profile(s), New Nashik: 1 profile(s), Panchavati: 1 profile(s), Satpur: 2 profile(s)
- K=6: Nashik East: 3 profile(s), Nashik Road: 2 profile(s), Nashik West: 4 profile(s), New Nashik: 1 profile(s), Panchavati: 1 profile(s), Satpur: 2 profile(s)

### Business-category patterns

- K=2: clothing: cluster 0 (83.3%; Public Transport Access with Mapped Commercial Activity); food: cluster 0 (84.7%; Public Transport Access with Mapped Commercial Activity); general_goods: cluster 0 (84.7%; Public Transport Access with Mapped Commercial Activity); vegetable_fruit: cluster 0 (87.5%; Public Transport Access with Mapped Commercial Activity)
- K=3: clothing: cluster 2 (44.4%; Public Transport Access); food: cluster 2 (44.4%; Public Transport Access); general_goods: cluster 2 (44.4%; Public Transport Access); vegetable_fruit: cluster 0 (44.4%; Mapped Commercial Activity with Mapped Public Facilities)
- K=4: clothing: cluster 0 (50.0%; Public Transport Access); food: cluster 0 (48.6%; Public Transport Access); general_goods: cluster 0 (48.6%; Public Transport Access); vegetable_fruit: cluster 0 (45.8%; Public Transport Access)
- K=5: clothing: cluster 2 (44.4%; Public Transport Access); food: cluster 2 (44.4%; Public Transport Access); general_goods: cluster 2 (44.4%; Public Transport Access); vegetable_fruit: cluster 1 (44.4%; Mapped Public Facilities with Mapped Commercial Activity)
- K=6: clothing: cluster 1 (50.0%; Public Transport Access); food: cluster 1 (48.6%; Public Transport Access); general_goods: cluster 1 (48.6%; Public Transport Access); vegetable_fruit: cluster 1 (45.8%; Public Transport Access)

The category and division patterns are descriptive associations in the fixed audit results, not evidence that clusters caused a recommendation.

## Limitations

- OSM feature coverage is incomplete; mapped absence is not confirmed real-world absence.
- Reference points are analytical and do not define official vending boundaries.
- Internal clustering metrics do not measure suitability, profitability, footfall or legal eligibility.
- Numeric cluster labels are arbitrary; comparisons use Adjusted Rand Index.

## Activation steps (not executed)

1. Obtain approval for the chosen K.
2. For the recommended K=2, rerun `python scripts/04_train_kmeans.py --version manual-142-v2`; the current approved selection rule already chooses K=2.
3. If approving another K, first make a reviewed versioned policy change that pins or selects that K; do not edit generated assignment CSVs manually.
4. Regenerate the candidate snapshot through its existing versioned pipeline so the artifact and `environment_cluster` field stay synchronized.
5. Review assignments, profiles, minimum cluster size and recommendation explanations.
6. Run backend tests and the frontend test/build suite.
7. Activate only through the catalog/version workflow after review.
