"""Contract and scientific guardrails for the structural refactor."""
from backend.core.data_paths import resolve_dataset_path
import hashlib
import ast
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

import backend.api as api
from backend.core.config import ConfigurationError, get_cors_origins
from backend.repositories import database
from backend.allocation.allocation_optimizer import AllocationDemand, optimize_precomputed
from backend.recommendation.decision_policy import calculate_ahp_weights

ROOT = Path(__file__).resolve().parents[1]
BASELINES = Path(__file__).resolve().parent / "fixtures/baselines"
IMPLEMENTATION_PATHS = {
    "backend/mcda_engine.py": "backend/recommendation/mcda_engine.py",
    "backend/decision_policy.py": "backend/recommendation/decision_policy.py",
    "backend/allocation_optimizer.py": "backend/allocation/allocation_optimizer.py",
    "backend/allocation_planning_service.py": "backend/allocation/allocation_planning_service.py",
    "backend/recommendation_evaluation.py": "backend/recommendation/recommendation_evaluation.py",
    "backend/ahp_calibration.py": "extra/research_tools/ahp_calibration.py",
    "backend/expert_label_aggregation.py": "extra/research_tools/expert_label_aggregation.py",
    "backend/suitability_model_training.py": "extra/research_tools/suitability_model_training.py",
    "scripts/01_validate_data.py": "extra/research_tools/scripts/01_validate_data.py",
    "scripts/02_build_zone_features.py": "extra/research_tools/scripts/02_build_zone_features.py",
    "scripts/03_build_training_data.py": "extra/research_tools/scripts/03_build_training_data.py",
    "scripts/04_compare_kmeans.py": "extra/research_tools/scripts/04_compare_kmeans.py",
    "scripts/04_train_kmeans.py": "extra/research_tools/scripts/04_train_kmeans.py",
    "research/mcda_baseline.py": "extra/research_tools/mcda_baseline.py",
}


def test_openapi_contract_matches_pre_refactor_baseline():
    expected = json.loads((BASELINES / "api-contract-baseline.json").read_text(encoding="utf-8"))
    assert api.app.openapi() == expected


def test_database_and_boundary_paths_remain_stable():
    assert database.DATABASE_PATH == ROOT / "data/operational/vendor_management.db"
    assert api.pilot_slots.gis.BOUNDARY_PATH == ROOT / "data/pilot/lekha_nagar_boundaries.geojson"
    assert not api.AUTH_TEST_BYPASS


def test_original_runtime_and_research_assets_are_unchanged():
    baseline = json.loads((BASELINES / "refactor-baseline.json").read_text(encoding="utf-8"))
    for name, digest in baseline.get("tracked_assets_sha256", baseline["assets_sha256"]).items():
        path = resolve_dataset_path(name)
        assert path.is_file(), name
        raw = path.read_bytes()
        if path.suffix.lower() in {".csv", ".json", ".geojson", ".md", ".txt"}:
            raw = raw.replace(b"\r\n", b"\n")
        assert hashlib.sha256(raw).hexdigest() == digest, name


def test_scientific_implementations_match_original_function_bodies():
    baseline = json.loads((BASELINES / "algorithm-baseline.json").read_text(encoding="utf-8"))
    for filename, expected in baseline.items():
        tree = ast.parse((ROOT / IMPLEMENTATION_PATHS.get(filename, filename)).read_text(encoding="utf-8"))
        actual = {n.name: hashlib.sha256(ast.dump(n, include_attributes=False).encode()).hexdigest()
                  for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
        assert actual == expected, filename


def test_goal_programming_respects_final_capacity_and_prefers_better_suitability():
    demands = [AllocationDemand("V1", "food"), AllocationDemand("V2", "food")]
    rows = [dict(vendor_id=vendor, zone_id="Z1", score=score,
                 score_coverage=1.0, zone_division="New Nashik")
            for vendor, score in [("V1", 90.0), ("V2", 60.0)]]
    plan = optimize_precomputed(demands, rows, {"Z1": 1})
    assert plan.assignment_count == 1
    assert plan.unassigned_count == 1
    assert plan.assignments[0].vendor_id == "V1"
    assert plan.capacity_snapshot == {"Z1": 1}
    assert "advisory" in plan.notice.lower()


def test_goal_programming_maximizes_assignments_before_score():
    demands = [AllocationDemand("V1", "food"), AllocationDemand("V2", "food")]
    rows = [dict(vendor_id=vendor, zone_id=zone, score=score,
                 score_coverage=1.0, zone_division="New Nashik")
            for vendor, zone, score in [("V1", "Z1", 99.0), ("V1", "Z2", 20.0), ("V2", "Z1", 60.0)]]
    plan = optimize_precomputed(demands, rows, {"Z1": 1, "Z2": 1})
    assert plan.assignment_count == 2
    assert {(a.vendor_id, a.zone_id) for a in plan.assignments} == {("V1", "Z2"), ("V2", "Z1")}


def test_equal_ahp_judgments_produce_equal_consistent_weights():
    result = calculate_ahp_weights(np.ones((6, 6)))
    assert result.is_consistent
    assert result.consistency_ratio == pytest.approx(0, abs=1e-12)
    assert list(result.weights.values()) == pytest.approx([1 / 6] * 6)


def test_cors_local_defaults_and_explicit_deployment_origin():
    with patch.dict("os.environ", {"CORS_ORIGINS": "https://vendors.example.test/"}):
        assert get_cors_origins() == ["https://vendors.example.test"]
    with patch.dict("os.environ", {"CORS_ORIGINS": "*"}):
        with pytest.raises(ConfigurationError):
            get_cors_origins()
