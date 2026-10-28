"""Optional, evidence-grounded Gemini prose for MCDA factor explanations.

This module never calculates scores or eligibility.  It accepts the six
deterministic factor records produced by the active recommendation engine and
may only restate their supplied evidence in the vendor's saved language.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from collections import OrderedDict, defaultdict, deque
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Literal, Mapping

from pydantic import BaseModel, Field, ValidationError

from backend.core.config import GeminiSettings, get_gemini_settings
from backend.core.data_paths import CATALOG
from backend.decision_policy import FACTOR_ORDER


LANGUAGE_NAMES = {"en": "English", "mr": "Marathi", "hi": "Hindi"}
MAX_PROMPT_BYTES = 20_000
MAX_EXPLANATION_CHARS = 650


class GeneratedFactor(BaseModel):
    factor: Literal["business", "commercial", "access", "facilities", "preference", "historical"]
    explanation: str = Field(min_length=1, max_length=MAX_EXPLANATION_CHARS)
    evidence_refs: list[str] = Field(min_length=1, max_length=8)


class GeneratedEnvelope(BaseModel):
    factors: list[GeneratedFactor] = Field(min_length=6, max_length=6)


class ExplanationValidationError(ValueError):
    """Raised when model output is not grounded in supplied evidence."""


class _BoundedCache:
    def __init__(self, max_size: int):
        self.max_size = max_size
        self.data: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self.lock = threading.Lock()

    def get(self, key: str) -> dict[str, Any] | None:
        with self.lock:
            value = self.data.get(key)
            if value is not None:
                self.data.move_to_end(key)
            return value

    def put(self, key: str, value: dict[str, Any]) -> None:
        with self.lock:
            self.data[key] = value
            self.data.move_to_end(key)
            while len(self.data) > self.max_size:
                self.data.popitem(last=False)


class _MinuteLimiter:
    def __init__(self):
        self.events: dict[str, deque[float]] = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, scope: str, limit: int) -> bool:
        now = time.monotonic()
        with self.lock:
            events = self.events[scope]
            while events and events[0] <= now - 60:
                events.popleft()
            if len(events) >= limit:
                return False
            events.append(now)
            return True


_cache_by_size: dict[int, _BoundedCache] = {}
_cache_lock = threading.Lock()
_limiter = _MinuteLimiter()


def _cache(size: int) -> _BoundedCache:
    with _cache_lock:
        return _cache_by_size.setdefault(size, _BoundedCache(size))


def _safe_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return round(value, 6) if value == value else None
    return str(value)[:300]


def build_evidence(
    *, zone_id: str, language: str, factors: list[Mapping[str, Any]],
    division: str | None, business_category: str | None,
    preference_profile: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a small PII-free allow-list of claims for the model."""
    factor_evidence: dict[str, Any] = {}
    for factor in factors:
        key = str(factor.get("key", ""))
        if key not in FACTOR_ORDER:
            continue
        references = {
            f"factor.{key}.score": _safe_scalar(factor.get("score")),
            f"factor.{key}.weight_percent": _safe_scalar(factor.get("weight")),
            f"factor.{key}.contribution": _safe_scalar(factor.get("contribution")),
        }
        for index, item in enumerate(factor.get("evidence") or []):
            references[f"factor.{key}.evidence.{index}"] = {
                "label": _safe_scalar(item.get("label")),
                "value": _safe_scalar(item.get("value")),
            }
        factor_evidence[key] = {
            "deterministic_summary": _safe_scalar(factor.get("summary")),
            "deterministic_details": _safe_scalar(factor.get("details")),
            "references": references,
        }
    return {
        "zone_id": zone_id,
        "division": division,
        "business_category": business_category,
        "language": language,
        "model_version": CATALOG.get("active_model_version"),
        "preferences": dict(preference_profile or {}),
        "factors": factor_evidence,
    }


def _flatten_references(evidence: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for factor in evidence["factors"].values():
        result.update(factor["references"])
    return result


def _numbers(value: Any) -> set[Decimal]:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    found: set[Decimal] = set()
    for token in re.findall(r"(?<![\w])[-+]?\d+(?:[.,]\d+)?", text):
        try:
            found.add(Decimal(token.replace(",", "")))
        except InvalidOperation:
            pass
    return found


_UNSUPPORTED_CLAIMS = re.compile(
    r"\b(guarantee[ds]?|verified footfall|measured footfall|proven demand|"
    r"guaranteed sales|expected income|profit(?:ability)?|legal approval|"
    r"approved boundary|safe traffic)\b", re.IGNORECASE,
)


def validate_generated(payload: Any, evidence: Mapping[str, Any]) -> GeneratedEnvelope:
    try:
        parsed = payload if isinstance(payload, GeneratedEnvelope) else GeneratedEnvelope.model_validate(payload)
    except ValidationError as exc:
        raise ExplanationValidationError("Gemini returned invalid structured output") from exc
    keys = [item.factor for item in parsed.factors]
    if len(set(keys)) != 6 or set(keys) != set(FACTOR_ORDER):
        raise ExplanationValidationError("Gemini output must contain each factor exactly once")
    allowed = _flatten_references(evidence)
    zone_id = str(evidence["zone_id"])
    allowed_zone_tokens = {zone_id.upper()}
    for item in parsed.factors:
        factor_prefix = f"factor.{item.factor}."
        if any(ref not in allowed or not ref.startswith(factor_prefix) for ref in item.evidence_refs):
            raise ExplanationValidationError("Gemini cited evidence outside the requested factor")
        if _UNSUPPORTED_CLAIMS.search(item.explanation):
            raise ExplanationValidationError("Gemini made an unsupported operational claim")
        cited_numbers: set[Decimal] = set()
        for ref in item.evidence_refs:
            cited_numbers.update(_numbers(allowed[ref]))
        prose_without_reference_ids = item.explanation
        for ref in item.evidence_refs:
            prose_without_reference_ids = prose_without_reference_ids.replace(ref, "")
        if not _numbers(prose_without_reference_ids).issubset(cited_numbers):
            raise ExplanationValidationError("Gemini used an unsupported numeric claim")
        mentioned_zone_ids = {match.upper() for match in re.findall(r"\b[A-Z]{2,4}_[A-Z]_\d{3}\b", item.explanation)}
        if not mentioned_zone_ids.issubset(allowed_zone_tokens):
            raise ExplanationValidationError("Gemini named an unsupported zone")
    return parsed


def _prompt(evidence: Mapping[str, Any]) -> str:
    language = LANGUAGE_NAMES[evidence["language"]]
    return (
        "You explain an existing municipal decision-support recommendation. "
        "You do not calculate, change, or reinterpret any score. Return exactly six factors "
        f"in {language}. Use only the JSON evidence below. Every factual or numeric statement "
        "must cite one or more reference IDs from that same factor. Do not infer footfall, demand, "
        "sales, income, profitability, legal status, safety, boundaries, or unavailable location facts. "
        "Do not write digits, numeric values, or reference IDs in the prose because the interface already displays them. "
        "Explain what the cited evidence means, and describe absent evidence as unavailable. "
        "Keep each explanation under 55 words. "
        "Return JSON matching the supplied schema.\nEVIDENCE:\n"
        + json.dumps(evidence, ensure_ascii=False, separators=(",", ":"))
    )


def _default_generate(settings: GeminiSettings, prompt: str) -> Any:
    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=settings.api_key,
        http_options=types.HttpOptions(timeout=int(settings.timeout_seconds * 1000)),
    )
    response = client.models.generate_content(
        model=settings.model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=GeneratedEnvelope,
            temperature=0.0,
            max_output_tokens=4096,
        ),
    )
    if getattr(response, "parsed", None) is not None:
        return response.parsed
    return json.loads(response.text)


def _fallback(factors: list[Mapping[str, Any]], reason: str, language: str) -> dict[str, Any]:
    return {
        "source": "deterministic_fallback",
        "language": language,
        "message": reason,
        "factors": [
            {
                "factor": factor["key"],
                "explanation": factor.get("details") or factor.get("summary") or "Evidence explanation unavailable.",
                "evidence_refs": [],
            }
            for factor in factors if factor.get("key") in FACTOR_ORDER
        ],
    }


def generate_explanations(
    *, zone_id: str, factors: list[Mapping[str, Any]], profile: Mapping[str, Any],
    requester_scope: str, settings: GeminiSettings | None = None,
    generator: Callable[[GeminiSettings, str], Any] | None = None,
) -> dict[str, Any]:
    """Generate validated prose or return the existing deterministic explanation."""
    settings = settings or get_gemini_settings()
    language = str(profile.get("preferred_language") or "en").lower()
    language = language if language in LANGUAGE_NAMES else "en"
    fallback = lambda reason: _fallback(factors, reason, language)
    if not settings.enabled:
        return fallback("AI explanations are disabled; showing the verified rule-based explanation.")
    if not settings.api_key:
        return fallback("AI explanation service is not configured; showing the verified rule-based explanation.")
    evidence = build_evidence(
        zone_id=zone_id,
        language=language,
        factors=factors,
        division=profile.get("preferred_division"),
        business_category=profile.get("business_category"),
        preference_profile={
            "priority_profile": profile.get("priority_profile"),
            "parking": bool(profile.get("parking_preference")),
            "transport": bool(profile.get("transport_preference")),
            "market": bool(profile.get("market_preference")),
        },
    )
    prompt = _prompt(evidence)
    if len(prompt.encode("utf-8")) > MAX_PROMPT_BYTES:
        return fallback("The evidence payload is too large; showing the verified rule-based explanation.")
    fingerprint_data = {"settings": {"model": settings.model}, "evidence": evidence}
    fingerprint = hashlib.sha256(json.dumps(fingerprint_data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    cached = _cache(settings.cache_size).get(fingerprint)
    if cached is not None:
        return cached
    if not _limiter.allow(requester_scope, settings.requests_per_minute):
        return fallback("AI explanation request limit reached; showing the verified rule-based explanation.")
    try:
        raw = (generator or _default_generate)(settings, prompt)
        parsed = validate_generated(raw, evidence)
    except Exception:
        # SDK, model, timeout, quota and validation details stay server-side and
        # must never leak credentials or provider internals to the client.
        return fallback("AI explanation is temporarily unavailable; showing the verified rule-based explanation.")
    result = {
        "source": "gemini",
        "language": language,
        "model": settings.model,
        "message": "AI-generated wording grounded in the displayed recommendation evidence.",
        "factors": [item.model_dump() for item in parsed.factors],
    }
    _cache(settings.cache_size).put(fingerprint, result)
    return result

