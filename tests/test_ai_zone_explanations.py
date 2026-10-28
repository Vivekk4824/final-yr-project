"""Unit tests for the read-only, optional Gemini explanation layer."""
from __future__ import annotations

import copy
import json

import pytest
import pandas as pd

from backend.core.config import GeminiSettings
from backend.decision_policy import FACTOR_ORDER
from backend.services.ai_zone_explanations import (
    ExplanationValidationError,
    build_evidence,
    generate_explanations,
    validate_generated,
)
from backend.routers import recommendations as recommendation_router


def factors():
    return [
        {
            "key": key,
            "score": 0.5,
            "weight": 20.0,
            "contribution": 10.0,
            "summary": f"Rule summary for {key}.",
            "details": f"Rule detail for {key}.",
            "evidence": [{"label": "Recorded value", "value": 5}],
        }
        for key in FACTOR_ORDER
    ]


def settings(*, enabled=True, key="test-key", model="gemini-test"):
    return GeminiSettings(enabled, key, model, 2.0, 32, 60)


def valid_payload(text="This explanation uses only the cited recorded evidence."):
    return {
        "factors": [
            {"factor": key, "explanation": text, "evidence_refs": [f"factor.{key}.evidence.0"]}
            for key in FACTOR_ORDER
        ]
    }


def profile(language="en"):
    return {
        "preferred_language": language,
        "preferred_division": "Nashik East",
        "business_category": "food",
        # These values must never enter the model prompt.
        "full_name": "Sensitive Person",
        "mobile": "9999999999",
    }


def test_disabled_and_missing_key_use_all_six_rule_based_factors():
    for configured in (settings(enabled=False), settings(key=None)):
        result = generate_explanations(
            zone_id="NE_F_010", factors=factors(), profile=profile(),
            requester_scope="disabled", settings=configured,
        )
        assert result["source"] == "deterministic_fallback"
        assert [item["factor"] for item in result["factors"]] == list(FACTOR_ORDER)


@pytest.mark.parametrize("language,name", [("en", "English"), ("mr", "Marathi"), ("hi", "Hindi")])
def test_saved_language_is_requested_and_prompt_contains_no_personal_data(language, name):
    captured = {}
    def generator(_settings, prompt):
        captured["prompt"] = prompt
        return valid_payload()
    result = generate_explanations(
        zone_id=f"NE_F_01{len(language)}", factors=factors(), profile=profile(language),
        requester_scope=f"lang-{language}", settings=settings(), generator=generator,
    )
    assert result["source"] == "gemini"
    assert result["language"] == language
    assert f"in {name}" in captured["prompt"]
    assert "Sensitive Person" not in captured["prompt"]
    assert "9999999999" not in captured["prompt"]


@pytest.mark.parametrize("failure", [TimeoutError("timeout"), RuntimeError("quota"), RuntimeError("invalid model")])
def test_provider_failures_use_deterministic_fallback(failure):
    def generator(_settings, _prompt):
        raise failure
    result = generate_explanations(
        zone_id="NE_F_010", factors=factors(), profile=profile(), requester_scope=str(failure),
        settings=settings(), generator=generator,
    )
    assert result["source"] == "deterministic_fallback"
    assert "temporarily unavailable" in result["message"]


def test_invalid_json_and_missing_factor_fall_back():
    for returned in ("not-json", {"factors": valid_payload()["factors"][:-1]}):
        result = generate_explanations(
            zone_id="NE_F_010", factors=factors(), profile=profile(), requester_scope=repr(returned),
            settings=settings(), generator=lambda _settings, _prompt, value=returned: value,
        )
        assert result["source"] == "deterministic_fallback"


def test_validator_rejects_unsupported_numbers_claims_and_cross_factor_references():
    evidence = build_evidence(
        zone_id="NE_F_010", language="en", factors=factors(),
        division="Nashik East", business_category="food",
    )
    numeric = valid_payload("There are 999 verified records.")
    with pytest.raises(ExplanationValidationError):
        validate_generated(numeric, evidence)
    claim = valid_payload("This guarantees sales and profitability.")
    with pytest.raises(ExplanationValidationError):
        validate_generated(claim, evidence)
    crossed = valid_payload()
    crossed["factors"][0]["evidence_refs"] = ["factor.commercial.evidence.0"]
    with pytest.raises(ExplanationValidationError):
        validate_generated(crossed, evidence)


def test_explanation_layer_does_not_mutate_scores_weights_or_contributions():
    original = factors()
    snapshot = copy.deepcopy(original)
    result = generate_explanations(
        zone_id="NE_F_010", factors=original, profile=profile(), requester_scope="unchanged",
        settings=settings(), generator=lambda _settings, _prompt: valid_payload(),
    )
    assert result["source"] == "gemini"
    assert original == snapshot
    assert "score" not in result["factors"][0]
    assert "weight" not in result["factors"][0]


def test_endpoint_recomputes_authenticated_strict_division_context(monkeypatch):
    calls = {}
    def session(_request, role):
        calls["role"] = role
        return {"vendor_id": "V1", "role": "VENDOR"}
    monkeypatch.setattr(recommendation_router, "request_session", session)
    monkeypatch.setattr(recommendation_router, "get_vendor_profile", lambda *args, **kwargs: profile("mr"))
    monkeypatch.setattr(recommendation_router, "get_active_allocation_for_vendor", lambda *args, **kwargs: None)
    monkeypatch.setattr(recommendation_router, "resolve_recommendation_context", lambda *args, **kwargs: {
        "business": "food", "division": "Nashik East", "engine_vendor_id": "V1",
        "weight_profile": {"final_weights": {key: 1 / 6 for key in FACTOR_ORDER}},
    })
    frame = pd.DataFrame([{"zone_id": "NE_F_010", "score": 51.25, "zone_division": "Nashik East"}])
    frame.attrs["all_candidates"] = frame.copy()
    frame.attrs["effective_factor_weights"] = {key: 1 / 6 for key in FACTOR_ORDER}
    def recommend(*args, **kwargs):
        calls["division"] = args[1]
        calls["live"] = kwargs["use_live_status"]
        return frame
    monkeypatch.setattr(recommendation_router, "recommend", recommend)
    monkeypatch.setattr(recommendation_router, "explain", lambda row, weights: factors())
    monkeypatch.setattr(recommendation_router, "active_vendor_category_counts", lambda *args, **kwargs: {})
    monkeypatch.setattr(recommendation_router, "generate_explanations", lambda **kwargs: {
        "source": "gemini", "language": "mr", "factors": valid_payload()["factors"],
    })
    response = recommendation_router.recommendation_ai_explanation("NE_F_010", object())
    assert calls == {"role": "VENDOR", "division": "Nashik East", "live": True}
    assert response["scores_unchanged"] is True
    assert response["factor_order"] == list(FACTOR_ORDER)

