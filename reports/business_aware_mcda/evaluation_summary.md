# Business-aware GIS MCDA experiment

Generated UTC: 2026-10-15T18:51:13.453781+00:00
Active dataset: `manual-142-v2`
Experimental policy: `business-aware-gis-v1`
Production feature flag default: `false`

## Formula

The experiment keeps the six existing MCDA factors and all effective weights. It replaces only the Commercial factor with a category-specific weighted mean of available mapped commercial-context features. Missing components are omitted with weight renormalization. Rows with no mapped category components fall back to the unchanged baseline Commercial score.

Historical Business Compatibility remains an independent smoothed historical concentration score. Accessibility, pedestrian/transport context and Facilities remain separate factors and are not copied into category GIS compatibility. This is the main double-counting control.

The category mapping uses commercial subtype counts rather than combining them with the aggregate commercial POI count. The aggregate contains those subtypes and would otherwise reward some mapped POIs twice.

## 96-scenario comparison

- Changed first-ranked zone: 13 of 96 scenarios.
- Changed Top-3 membership: 24 of 96 scenarios.
- Mean Top-3 overlap: 91.3%.
- Mean change in selected category-GIS compatibility: +0.0042 on the 0-1 component scale.
- Mean absolute candidate score change: 1.084 points on the 0-100 scale.
- Mean cross-category Top-3 overlap changed from 80.6% to 76.9%.
- Category differentiation increased in 7 of 24 division/profile groups.

## Evidence quality and limitations

- Sparse category features with nonzero coverage below 25% of candidate rows: food_poi_count_250m, market_poi_count_500m, retail_poi_count_250m, service_poi_count_250m.
- Mapped POIs indicate environmental context only. They do not demonstrate demand, customer footfall, sales, profitability or legal suitability.
- Historical association evidence is contextual and is not a success label.
- The feature mapping is a transparent hypothesis and has not been calibrated with outcome or expert-judgement data.
- Flower, other and unknown categories retain the baseline Commercial factor because no sufficiently specific active GIS field exists.
- Operational capacity was read as a frozen snapshot. No PostgreSQL write path was called.

## Activation recommendation

**DO_NOT_ACTIVATE_WITHOUT_EXPERT REVIEW.**

Keep `BUSINESS_AWARE_MCDA_EXPERIMENT=false` in normal environments. Review the mapping with municipal/GIS domain experts, inspect sparse-feature zones, and repeat the isolated test and 96-scenario audit before any versioned catalog or production-policy change.
