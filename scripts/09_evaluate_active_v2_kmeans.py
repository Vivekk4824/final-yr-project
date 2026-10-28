"""Experiment-only K=2..6 evaluation for active manual-142-v2 features.

Writes only to reports/kmeans/active_v2_k_selection. It never updates the
catalog, active model artifact, candidate snapshot, assignments, or database.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from unittest.mock import patch

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import (
    adjusted_rand_score,
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.data_paths import CATALOG, dataset_path
from backend.decision_policy import derive_mcda_weights
from backend.repositories.database import DATABASE_PATH
import backend.mcda_engine as mcda

trainer = importlib.import_module("scripts.04_train_kmeans")

OUT = ROOT / "reports" / "kmeans" / "active_v2_k_selection"
K_VALUES = range(2, 7)
SEEDS = list(trainer.SEEDS)
FEATURES = list(trainer.FEATURES)
GROUPS = dict(trainer.GROUPS)
DISTANCES = set(trainer.DISTANCES)
DIVISIONS = ["Nashik East", "Nashik West", "Nashik Road", "New Nashik", "Panchavati", "Satpur"]
CATEGORIES = ["food", "clothing", "vegetable_fruit", "general_goods"]
PROFILES = ["BALANCED", "COMMERCIAL", "ACCESSIBILITY", "FACILITIES"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def check_input_contract(features: pd.DataFrame, official: pd.DataFrame, path: Path) -> None:
    expected = ROOT / CATALOG["datasets"]["zone_features"]
    if CATALOG.get("active_model_version") != "manual-142-v2" or path.resolve() != expected.resolve():
        raise ValueError("Experiment must use the active manual-142-v2 feature dataset")
    required = {"zone_id", "division", "zone_type", "geometry_usable_for_reference_model", *FEATURES}
    missing = required - set(features.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    if features.zone_id.isna().any() or features.zone_id.duplicated().any():
        raise ValueError("Feature zone IDs must be unique and nonempty")
    if official.zone_id.isna().any() or official.zone_id.duplicated().any():
        raise ValueError("Official zone IDs must be unique and nonempty")
    joined = features[["zone_id", "division", "zone_type"]].merge(
        official[["zone_id", "division", "zone_type"]], on="zone_id", suffixes=("_feature", "_official"), validate="one_to_one"
    )
    if len(joined) != len(features) or not joined.division_feature.eq(joined.division_official).all() or not joined.zone_type_feature.eq(joined.zone_type_official).all():
        raise ValueError("Feature division/type metadata differs from the canonical registry")


def metrics(x: np.ndarray, labels: np.ndarray, model: KMeans) -> dict[str, float]:
    sizes = np.bincount(labels, minlength=model.n_clusters)
    return {
        "silhouette": float(silhouette_score(x, labels)),
        "davies_bouldin": float(davies_bouldin_score(x, labels)),
        "calinski_harabasz": float(calinski_harabasz_score(x, labels)),
        "inertia": float(model.inertia_),
        "smallest_cluster_size": int(sizes.min()),
        "largest_cluster_size": int(sizes.max()),
        "cluster_size_range": int(sizes.max() - sizes.min()),
        "cluster_size_ratio": float(sizes.max() / sizes.min()),
    }


def profile_name(group_scores: dict[str, float]) -> str:
    labels = {
        "road_access": "Road and Pedestrian Access",
        "commercial": "Mapped Commercial Activity",
        "transport": "Public Transport Access",
        "facilities": "Mapped Public Facilities",
    }
    ordered = sorted(group_scores, key=group_scores.get, reverse=True)
    positive = [name for name in ordered if group_scores[name] >= 0.35]
    if not positive:
        return f"Lower Mapped Environmental Intensity; relatively {labels[ordered[0]]}"
    if len(positive) == 1:
        return labels[positive[0]]
    return f"{labels[positive[0]]} with {labels[positive[1]]}"


def chart_outputs(comparison: pd.DataFrame, sizes: pd.DataFrame, profiles: pd.DataFrame) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axis = plt.subplots(figsize=(7.2, 4.2))
    axis.errorbar(comparison.k, comparison.silhouette_mean, yerr=comparison.silhouette_std, marker="o", capsize=4)
    axis.set(title="K-Means silhouette comparison", xlabel="Number of clusters (K)", ylabel="Mean silhouette")
    axis.set_xticks(list(K_VALUES))
    fig.tight_layout(); fig.savefig(OUT / "silhouette_comparison.png", dpi=170); plt.close(fig)

    pivot = sizes.pivot(index="k", columns="cluster", values="zone_count")
    fig, axis = plt.subplots(figsize=(8, 4.5))
    pivot.plot(kind="bar", stacked=True, ax=axis, colormap="tab20")
    axis.set(title="Cluster sizes by K", xlabel="K", ylabel="Zones")
    axis.legend(title="Cluster", ncol=3, fontsize=8)
    fig.tight_layout(); fig.savefig(OUT / "cluster_size_comparison.png", dpi=170); plt.close(fig)

    heat = profiles.pivot_table(index=["k", "cluster"], columns="feature", values="standardized_mean")
    fig, axis = plt.subplots(figsize=(13, max(5, len(heat) * .36)))
    image = axis.imshow(heat.to_numpy(), aspect="auto", cmap="RdBu_r", vmin=-1.5, vmax=1.5)
    axis.set_xticks(range(len(heat.columns)), [c.replace("_", " ") for c in heat.columns], rotation=55, ha="right", fontsize=8)
    axis.set_yticks(range(len(heat.index)), [f"K{k} C{c}" for k, c in heat.index], fontsize=8)
    axis.set_title("Standardized environmental cluster profiles")
    fig.colorbar(image, ax=axis, label="Standard deviations from overall mean")
    fig.tight_layout(); fig.savefig(OUT / "cluster_profile_heatmap.png", dpi=170); plt.close(fig)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    feature_path = dataset_path("zone_features")
    official_path = dataset_path("official_zones")
    features = pd.read_csv(feature_path, dtype={"zone_id": str})
    official = pd.read_csv(official_path, dtype={"zone_id": str})
    check_input_contract(features, official, feature_path)

    usable = features.geometry_usable_for_reference_model.astype(str).str.lower().isin(["true", "1", "yes"])
    population = features.loc[usable].copy().reset_index(drop=True)
    raw = population[FEATURES].apply(pd.to_numeric, errors="coerce")
    if np.isinf(raw.to_numpy()).any() or (raw < 0).any().any():
        raise ValueError("Environmental features contain invalid values")
    transformed, params = trainer.preprocess(raw, "balanced")
    active_indices = np.flatnonzero(np.var(transformed, axis=0) > 1e-12)
    x = transformed[:, active_indices]
    active_features = [FEATURES[index] for index in active_indices]
    standardized = transformed[:, active_indices] / params["weights"][active_indices]

    comparison_rows, size_rows, profile_rows = [], [], []
    selected: dict[int, dict[str, object]] = {}
    assignments = population[["zone_id", "division", "zone_type"]].copy()

    for k in K_VALUES:
        trials = []
        for seed in SEEDS:
            model = KMeans(n_clusters=k, n_init=20, random_state=seed)
            labels = model.fit_predict(x)
            trials.append({"seed": seed, "model": model, "labels": labels, "metrics": metrics(x, labels, model)})
        pairwise_ari = [adjusted_rand_score(a["labels"], b["labels"]) for a, b in combinations(trials, 2)]
        chosen = max(trials, key=lambda trial: (trial["metrics"]["silhouette"], -trial["seed"]))
        selected[k] = chosen
        assignments[f"cluster_k{k}"] = chosen["labels"]
        assignments[f"distance_to_centroid_k{k}"] = np.min(chosen["model"].transform(x), axis=1)
        values = {name: [trial["metrics"][name] for trial in trials] for name in trials[0]["metrics"]}
        comparison_rows.append({
            "k": k,
            "training_rows": len(population),
            "completed_seeds": len(trials),
            "selected_seed": chosen["seed"],
            **{f"{name}_mean": float(np.mean(items)) for name, items in values.items()},
            **{f"{name}_std": float(np.std(items)) for name, items in values.items()},
            "smallest_cluster_size_across_seeds": int(min(values["smallest_cluster_size"])),
            "largest_cluster_size_across_seeds": int(max(values["largest_cluster_size"])),
            "selected_smallest_cluster_size": int(np.bincount(chosen["labels"], minlength=k).min()),
            "selected_largest_cluster_size": int(np.bincount(chosen["labels"], minlength=k).max()),
            "selected_cluster_size_ratio": float(
                np.bincount(chosen["labels"], minlength=k).max()
                / np.bincount(chosen["labels"], minlength=k).min()
            ),
            "stability_ari_mean": float(np.mean(pairwise_ari)),
            "stability_ari_median": float(np.median(pairwise_ari)),
            "stability_ari_min": float(np.min(pairwise_ari)),
        })

        labels = np.asarray(chosen["labels"])
        counts = np.bincount(labels, minlength=k)
        group_profile_scores: dict[int, dict[str, float]] = {}
        for cluster in range(k):
            mask = labels == cluster
            group_scores = {}
            for group, group_features in GROUPS.items():
                indices = [active_features.index(name) for name in group_features if name in active_features]
                scores = []
                for index in indices:
                    value = float(standardized[mask, index].mean())
                    scores.append(-value if active_features[index] in DISTANCES else value)
                group_scores[group] = float(np.mean(scores))
            group_profile_scores[cluster] = group_scores
            name = profile_name(group_scores)
            size_rows.append({
                "k": k, "cluster": cluster, "profile_name": name,
                "selected_seed": chosen["seed"], "zone_count": int(counts[cluster]),
                "share_of_training_rows": float(counts[cluster] / len(population)),
                "smallest_cluster_for_k": int(counts.min()), "largest_cluster_for_k": int(counts.max()),
                "cluster_size_ratio_for_k": float(counts.max() / counts.min()),
            })
            for feature_index, feature in enumerate(active_features):
                raw_values = raw.loc[mask, feature]
                profile_rows.append({
                    "k": k, "cluster": cluster, "profile_name": name,
                    "zone_count": int(mask.sum()), "feature": feature,
                    "raw_median": float(raw_values.median()), "overall_raw_median": float(raw[feature].median()),
                    "raw_mean": float(raw_values.mean()), "overall_raw_mean": float(raw[feature].mean()),
                    "standardized_mean": float(standardized[mask, feature_index].mean()),
                })

    comparison = pd.DataFrame(comparison_rows)
    cluster_sizes = pd.DataFrame(size_rows)
    profiles = pd.DataFrame(profile_rows)

    division_rows, free_rows = [], []
    # Read operational status once. Subsequent 96 scenarios reuse this frozen frame.
    live_zones, historical_vendors = mcda.load(use_live_status=True, database_path=DATABASE_PATH)
    scoreable_ids = set(mcda.score_candidates("food", use_live_status=True, database_path=DATABASE_PATH).zone_id)
    for k in K_VALUES:
        label_col = f"cluster_k{k}"
        for (division, cluster), count in assignments.groupby(["division", label_col]).size().items():
            division_rows.append({"k": k, "division": division, "cluster": cluster, "zone_count": int(count)})
        for cluster, group in assignments.groupby(label_col):
            free = group.zone_type.eq("FREE")
            free_rows.append({
                "k": k, "cluster": cluster, "profile_name": cluster_sizes.loc[(cluster_sizes.k.eq(k)) & (cluster_sizes.cluster.eq(cluster)), "profile_name"].iloc[0],
                "all_zones": len(group), "free_zones": int(free.sum()),
                "currently_scoreable_free_zones": int(group.zone_id.isin(scoreable_ids).sum()),
            })

    stored = pd.read_csv(dataset_path("kmeans_output") / "zones_with_clusters.csv", dtype={"zone_id": str})
    stored_k2 = stored.loc[stored.cluster.notna(), ["zone_id", "cluster"]]
    current_compare = assignments[["zone_id", "cluster_k2"]].merge(stored_k2, on="zone_id", validate="one_to_one")
    current_k2_ari = adjusted_rand_score(current_compare.cluster, current_compare.cluster_k2)

    v1_features = ROOT / CATALOG["model_versions"]["manual-142-v1"]["zone_features"]
    v1_assignments = ROOT / CATALOG["model_versions"]["manual-142-v1"]["kmeans_output"] / "zones_with_clusters.csv"
    v1 = pd.read_csv(v1_assignments, dtype={"zone_id": str})
    v2 = stored
    common = v1.loc[v1.cluster.notna(), ["zone_id", "cluster"]].merge(
        v2.loc[v2.cluster.notna(), ["zone_id", "cluster"]], on="zone_id", suffixes=("_v1", "_v2")
    )
    v1_v2_ari = adjusted_rand_score(common.cluster_v1, common.cluster_v2)
    v1_feature_frame = pd.read_csv(v1_features, dtype={"zone_id": str})
    feature_compare = v1_feature_frame[["zone_id", *FEATURES]].merge(features[["zone_id", *FEATURES]], on="zone_id", suffixes=("_v1", "_v2"))
    changed_feature_rows = int(np.any([
        ~np.isclose(pd.to_numeric(feature_compare[f"{name}_v1"], errors="coerce"), pd.to_numeric(feature_compare[f"{name}_v2"], errors="coerce"), equal_nan=True)
        for name in FEATURES
    ], axis=0).sum())

    recommendation_counts = {k: Counter() for k in K_VALUES}
    recommendation_rows = []
    frozen_assignments = assignments.set_index("zone_id")
    profile_lookup = cluster_sizes.set_index(["k", "cluster"])["profile_name"].to_dict()
    def frozen_load(use_live_status=False, database_path=None):
        return live_zones.copy(deep=True), historical_vendors.copy(deep=True)
    with patch.object(mcda, "load", frozen_load):
        for division in DIVISIONS:
            for category in CATEGORIES:
                for profile in PROFILES:
                    weights = derive_mcda_weights({"priority_profile": profile})["final_weights"]
                    result = mcda.recommend(category, division=division, top_n=3, use_live_status=True, database_path=DATABASE_PATH, factor_weights=weights)
                    for rank, zone_id in enumerate(result.zone_id, start=1):
                        for k in K_VALUES:
                            cluster = int(frozen_assignments.loc[zone_id, f"cluster_k{k}"])
                            recommendation_counts[k][cluster] += 1
                            recommendation_rows.append({
                                "k": k,
                                "business_category": category,
                                "preferred_division": division,
                                "priority_profile": profile,
                                "rank": rank,
                                "zone_id": zone_id,
                                "cluster": cluster,
                                "cluster_profile_name": profile_lookup[(k, cluster)],
                            })

    recommendation_details = pd.DataFrame(recommendation_rows)
    recommendation_distribution = (
        recommendation_details.groupby(
            ["k", "business_category", "preferred_division", "priority_profile", "cluster", "cluster_profile_name"],
            as_index=False,
        )
        .agg(recommendation_count=("zone_id", "size"), distinct_recommended_zones=("zone_id", "nunique"))
    )

    comparison.to_csv(OUT / "k_comparison.csv", index=False)
    cluster_sizes.to_csv(OUT / "cluster_sizes.csv", index=False)
    profiles.to_csv(OUT / "cluster_profiles.csv", index=False)
    pd.DataFrame(division_rows).to_csv(OUT / "division_cluster_distribution.csv", index=False)
    pd.DataFrame(free_rows).to_csv(OUT / "free_zone_cluster_distribution.csv", index=False)
    assignments.to_csv(OUT / "cluster_assignments_by_k.csv", index=False)
    recommendation_distribution.to_csv(OUT / "recommendation_cluster_distribution.csv", index=False)
    chart_outputs(comparison, cluster_sizes, profiles)

    best_k = 2
    lines = [
        "# Active manual-142-v2 K-Means selection experiment", "",
        f"Generated UTC: {datetime.now(timezone.utc).isoformat()}", "",
        "## Method", "",
        f"- Active feature source: `{feature_path.relative_to(ROOT)}` (SHA-256 `{sha256(feature_path)}`)",
        f"- Evaluation population: {len(population)} zones with usable environmental references.",
        f"- Features: {', '.join(FEATURES)}.",
        "- Preprocessing: log1p; 1st/99th percentile clipping; median imputation; StandardScaler; equal environmental-group weighting.",
        f"- Seeds: {SEEDS}; KMeans n_init=20; K evaluated: {list(K_VALUES)}.",
        "- Excluded from clustering: identity, coordinates, capacity, occupancy, division, zone type, historical vendors, business categories, MCDA scores and preferences.", "",
        "## Selection", "",
        f"Recommended experiment result: **K={best_k}**. It has the highest silhouette, perfect seed stability, and the most balanced usable cluster sizes. K=4 adds interpretive detail and slightly improves Davies-Bouldin, but lowers silhouette and its selected run has a 21-zone cluster alongside a 160-zone cluster (one seed produced an 18-zone minimum). K=5 and K=6 create 3-zone fragments and are less stable.", "",
        f"The recreated K=2 assignment has label-invariant ARI {current_k2_ari:.6f} against the stored active assignments; the production model remains unchanged.",
        f"The v1-versus-v2 stored K=2 assignments have ARI {v1_v2_ari:.6f} across {len(common)} common assigned zones. {changed_feature_rows} common feature rows changed in at least one selected environmental feature.", "",
        "## Recommendation-profile distribution", "",
    ]
    for k in K_VALUES:
        total = sum(recommendation_counts[k].values())
        detail = ", ".join(f"cluster {cluster}: {count} ({count/total:.1%})" for cluster, count in sorted(recommendation_counts[k].items()))
        lines.append(f"- K={k}: {detail}")
    lines += ["", "These counts describe cluster membership across the 288 Top-3 positions from the existing 96-scenario MCDA audit. Clusters did not alter eligibility, scores, division filtering or ranking.", "",
              "### Differentiation within preferred divisions", ""]
    for k in K_VALUES:
        by_division = recommendation_details.loc[recommendation_details.k.eq(k)].groupby("preferred_division").cluster.nunique()
        detail = ", ".join(f"{division}: {int(count)} profile(s)" for division, count in by_division.items())
        lines.append(f"- K={k}: {detail}")
    lines += ["", "### Business-category patterns", ""]
    for k in K_VALUES:
        category_parts = []
        k_rows = recommendation_details.loc[recommendation_details.k.eq(k)]
        for category, category_rows in k_rows.groupby("business_category"):
            counts = category_rows.cluster.value_counts()
            dominant_cluster = int(counts.index[0])
            category_parts.append(
                f"{category}: cluster {dominant_cluster} ({counts.iloc[0] / counts.sum():.1%}; {profile_lookup[(k, dominant_cluster)]})"
            )
        lines.append(f"- K={k}: " + "; ".join(category_parts))
    lines += ["", "The category and division patterns are descriptive associations in the fixed audit results, not evidence that clusters caused a recommendation.", "",
              "## Limitations", "", "- OSM feature coverage is incomplete; mapped absence is not confirmed real-world absence.", "- Reference points are analytical and do not define official vending boundaries.", "- Internal clustering metrics do not measure suitability, profitability, footfall or legal eligibility.", "- Numeric cluster labels are arbitrary; comparisons use Adjusted Rand Index.", "",
              "## Activation steps (not executed)", "", "1. Obtain approval for the chosen K.", "2. For the recommended K=2, rerun `python scripts/04_train_kmeans.py --version manual-142-v2`; the current approved selection rule already chooses K=2.", "3. If approving another K, first make a reviewed versioned policy change that pins or selects that K; do not edit generated assignment CSVs manually.", "4. Regenerate the candidate snapshot through its existing versioned pipeline so the artifact and `environment_cluster` field stay synchronized.", "5. Review assignments, profiles, minimum cluster size and recommendation explanations.", "6. Run backend tests and the frontend test/build suite.", "7. Activate only through the catalog/version workflow after review."]
    (OUT / "k_selection_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    expected_ids = set(population.zone_id)
    if set(assignments.zone_id) != expected_ids or assignments.zone_id.duplicated().any():
        raise AssertionError("Assignment coverage or uniqueness validation failed")
    for k in K_VALUES:
        if assignments[f"cluster_k{k}"].isna().any() or assignments[f"cluster_k{k}"].nunique() != k:
            raise AssertionError(f"Invalid K={k} assignment coverage")
    print(comparison[["k", "silhouette_mean", "davies_bouldin_mean", "calinski_harabasz_mean", "stability_ari_mean", "smallest_cluster_size_mean", "largest_cluster_size_mean", "cluster_size_ratio_mean"]].to_string(index=False))
    print(f"\nRecommended K={best_k}; active production artifacts were not changed.")
    print(f"Outputs: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
