# Data catalog

Canonical repository-relative paths and old-to-new aliases are in `catalog.json`; Python consumers use `backend.core.data_paths`. Frontend imports use an explicit public-data allowlist against the same catalog. External Python tools can call `resolve_dataset_path` for legacy filenames.

- `raw/nmc/`: unchanged official zone, historical vendor, crosswalk and source-evidence CSVs. Vendor names, phones and addresses are private; never serve this directory publicly. Original OSM GeoJSON/GPKG pairs remain in `raw/osm/` because formats have different consumers.
- `processed/`: cleaned vendor registry, candidate snapshot, historical compatibility/pairs and development splits; existing MCDA eligibility and feature values are preserved.
- `gis/manual/`: preferred 142 user-plotted display points, source pin export, GeoJSON equivalent, full 146-zone status checklist and both conflicting pin-106 candidates. Pins 1, 3, 85 and 106 remain unresolved; points are not surveyed boundaries.
- `gis/display/`: prior display candidates retained as fallback for zones outside the manual checklist.
- `gis/analytical/`: unchanged original analytical zone geometry. Original analytical geometry is preserved. Active versioned features use 142 manual points and labelled original-point fallbacks for the four unresolved FREE locations.
- `gis/illustrative/`: six display-only division polygons; spatial inclusion is not official administrative membership.
- `model/features/`, `model/kmeans/`, `model/recommendations/`: existing GIS features, clustering/comparison outputs and recommendation exports. Baseline artifacts remain in `data/models/kmeans/`. The active `manual-142-v1` features, scaler/K-Means, inputs and compact metadata are in `model/versions/manual-142-v1/`; catalog baseline paths support rollback.
- `pilot/`: original Lekha Nagar boundaries and consolidated three-zone source layout. SQLite remains the source of truth for the four saved layouts, 85 slots and assignments.
- `operational/`: local SQLite database, unchanged and ignored by Git.
- `archive/coordinate_handoff/`: original handoff instructions, numbered CSV/XLSX checklist and differing historical vendor source for rollback. Private vendor archives are ignored by Git. Existing upstream tracking/history of private source files is not rewritten by this cleanup.

Seven handoff copies were removed only after byte-for-byte SHA-256 comparison with their canonical files. Identical K=2 profile outputs are retained because baseline/comparison tools give them distinct roles. The cleanup retained baseline assets. The separately versioned GIS/K-Means refresh changes no raw geometry, SQLite records or MCDA formulas.

Reproduce the active refresh in dependency order: `python extra/research_tools/scripts/02_build_zone_features.py --version manual-142-v1 --compact-metadata`, `python extra/research_tools/scripts/04_train_kmeans.py --version manual-142-v1`, then `python extra/research_tools/scripts/03_build_training_data.py --version manual-142-v1`. Review `metadata/comparison_summary.json` for coordinate/slot conflicts.
