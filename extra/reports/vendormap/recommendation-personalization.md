# VendorMap recommendation validation

This report records the earlier 25% experiment. The [final six-input audit](final-recommendation-input-validation.md) covers the approved 15% default.

The audit ran 144 vendor scenarios against the active manual-142-v2 GIS and a read-only copy of the bundled operational SQLite snapshot. It crossed all six supported categories and six divisions with two saved pin positions per division and two priority and facility settings per division. Positions came from the westernmost and easternmost eligible mapped references. The comparison below uses Anywhere to isolate ranking from the radius constraint.

The audited 25% experiment blends 75% of the active six-factor MCDA with 25% of the proximity score, `100 × exp(-distance_km / 3)`. The business GIS flag replaces only the Commercial component using available category evidence. The API retains the original baseline MCDA score alongside the active and personalized scores. Distances use the active model's stored manual and saved pilot references. Zones without those references can still appear in the explorer.

## Results

| Policy | Top-1 changed | Top-3 membership changed | Mean Top-3 overlap with baseline | Mean original MCDA loss per Top 3 |
| --- | ---: | ---: | ---: | ---: |
| Business GIS only | 14/144 | 24/144 | 94.0% | 0.28 points |
| Location only at 25% | 69/144 | 122/144 | 62.5% | — |
| Both at 25% proximity | 70/144 | 124/144 | 60.4% | 4.84 points |
| Both at 20% proximity | 58/144 | 107/144 | 69.9% | 2.85 points |
| Both at 15% proximity | 44/144 | 95/144 | 76.6% | 1.61 points |
| Both at 10% proximity | 27/144 | 69/144 | 82.9% | 0.98 points |

- **Location sensitivity.** Holding division, business and priority fixed, changing the pin changed the #1 zone in 45 of 72 matched pairs at 25% proximity. Mean Top-3 overlap fell from 100% to 46.3%. The selected zones were 1.35 km closer on average.
- **Business evidence.** The GIS-only experiment reduced same-location, cross-category Top-3 overlap from 82.4% to 76.1%. Mean selected category GIS compatibility rose by 1.85 points on a 0–100 scale. At 25% proximity, the business flag lowered this proxy by 0.22 points relative to location-only ranking. The OSM layers contain contextual observations with sparse coverage. Sales and footfall are unobserved. Flower and other retain the original Commercial factor.
- **Priority and facility sensitivity.** Holding division, category and pin fixed, changing priority and its matched facility setting reduced average Top-3 overlap from 96.3% to 90.7% under the combined experiment. Top-1 changes in those pairs fell from 12 to 5 of 72.
- **Suitability.** At 25% proximity, the 90th-percentile average Top-3 loss was 8.93 points, and the largest individual Top-1 loss was 21.79 points. At 15% proximity, the comparable 90th percentile was 3.70 points, with a mean distance improvement of 0.59 km. The 25% experiment did not clear the suitability gate for rollout. The 15% result is a candidate for staging validation.
- **Eligibility and coverage.** The explorer kept all 165 eligible FREE zones, including 20 with null suitability. Another 3 scoreable zones lacked a reviewed distance reference. All recommendations satisfied the selected division, FREE status, operational status and positive available capacity. The 1 km shortlist returned fewer than three zones in 84 scenarios. The 3 km shortlist did so in 12 scenarios. The 5 km and 10 km shortlists had three results in all audited scenarios.
- **K-Means.** The location and business experiments showed enough ranking differentiation to keep K=2. The existing K=4 study measured environment clusters and showed lower silhouette and smaller clusters. It provided no demonstrated ranking advantage. [Active K-Means evaluation](../kmeans/active_v2_k_selection/k_selection_summary.md)

## Example Top 3

| Vendor scenario | Baseline | Combined at 25% proximity |
| --- | --- | --- |
| Food, Nashik West, Balanced, pin at NW_F_004 | NW_F_025, NW_F_007, NW_F_017 | NW_F_007, NW_F_025, NW_F_005 |
| Clothing, Nashik West, Balanced, same pin | NW_F_025, NW_F_007, NW_F_017 | NW_F_007, NW_F_005, NW_F_025 |
| Vegetables and fruit, Satpur, Facilities and parking, pin at SAT_F_020 | SAT_F_004, SAT_F_022, SAT_F_011 | SAT_F_013, SAT_F_020, SAT_F_004 |

## Rollout

1. Apply the additive migration in staging using the normal startup or run it separately against the intended database configuration with the command below. The repository adds `preferred_latitude`, `preferred_longitude` and `preferred_radius_km` as nullable columns.
2. Start with `BUSINESS_AWARE_MCDA_EXPERIMENT=false` and `LOCATION_RANKING_EXPERIMENT=false`. Confirm profile saves, the eligible explorer and ordinary ranking on the staging snapshot with saved pilot layouts.
3. Review category mappings and run a staged comparison with one flag at a time. The location policy is configured by `LOCATION_PROXIMITY_WEIGHT` (approved default `0.15`) and `LOCATION_PROXIMITY_DECAY_KM` (default `3`). Roll back ranking by setting both flags to `false`.

```sh
python -c "from backend.repositories.database import migrate_vendor_location_preferences; migrate_vendor_location_preferences()"
python extra/validation/11_evaluate_vendor_personalization.py
```

The evaluation script reads the bundled SQLite operational snapshot in read-only mode and emits JSON to stdout. The PostgreSQL integration test uses a disposable instance supplied via `VENDORMAP_TEST_POSTGRES_URL`.

## Files

- Backend ranking and API. `backend/recommendation/location_ranking.py`, `backend/recommendation/mcda_engine.py`, `backend/recommendation/business_aware_mcda.py`, `backend/routers/recommendations.py`, `backend/services/recommendation_context.py`.
- Preference persistence. `backend/schemas/api.py`, `backend/services/vendors.py`, `backend/repositories/database.py`, `.env.example`.
- Vendor workspace. `frontend/src/app/ImplementationApp.jsx`, `frontend/src/services/api.js`, and `WorkingLocationFields.jsx`, `PreferenceFields.jsx`, `RankingContext.jsx`, `RecommendationDetailPage.jsx`, `VendorPortal.jsx`, `VendorPortal.css`, `useVendorWorkspace.js` and `viewModel.js` under `frontend/src/features/vendor/`.
- Translations. `frontend/src/i18n/en.js`, `frontend/src/i18n/mr.js`, `frontend/src/i18n/hi.js`.
- Validation. `extra/validation/11_evaluate_vendor_personalization.py`, `tests/test_vendor_location_recommendations.py`, `frontend/tests/vendor-location-browser.mjs`, `frontend/src/i18n/i18n.test.js`, `frontend/src/features/vendor/recommendationExplorer.test.js`.
