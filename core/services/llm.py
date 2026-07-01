"""Large Language Model integration for the Remote Patrol System.

Primary use case (per product decision): AI analysis & classification of
incident reports submitted by security guards — both the free-text narrative
and any attached photos (vision model) — to detect anomalies, assign a
severity, and recommend an action for the command centre.

Design principles:
  * Provider-agnostic via an OpenAI-compatible client (`LLM_BASE_URL`).
  * Fully degradable: with no `LLM_API_KEY`, a deterministic keyword-based mock
    is returned so the system stays demoable and testable offline.
  * All model output is coerced into a stable, validated schema.
"""

from __future__ import annotations

import base64
import json
import logging
import mimetypes
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

VALID_CATEGORIES = [
    "intrusion",
    "fire_hazard",
    "vehicle_issue",
    "medical",
    "vandalism",
    "suspicious_activity",
    "environmental",
    "other",
]
VALID_SEVERITIES = ["low", "medium", "high", "critical"]

_INCIDENT_SYSTEM_PROMPT = (
    "You are the AI analyst for a security patrol command centre. Given an "
    "incident report (text and optional photos) from a patrol officer, classify "
    "it and assess risk. Respond ONLY with a compact JSON object with keys: "
    "category (one of {categories}), severity (one of {severities}), summary "
    "(<=280 chars), recommended_action (<=280 chars), anomaly_detected (bool), "
    "tags (array of short strings)."
).format(categories=VALID_CATEGORIES, severities=VALID_SEVERITIES)


def is_enabled() -> bool:
    return bool(settings.LLM_API_KEY)


def _client():
    from openai import OpenAI

    return OpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)


def _encode_image(path: str) -> str | None:
    """Return a data URL for a local image, suitable for the vision API."""
    try:
        mime, _ = mimetypes.guess_type(path)
        mime = mime or "image/jpeg"
        with open(path, "rb") as fh:
            data = base64.b64encode(fh.read()).decode("ascii")
        return f"data:{mime};base64,{data}"
    except OSError as exc:
        logger.warning("Could not read incident image %s: %s", path, exc)
        return None


def _coerce_analysis(raw: dict[str, Any], source: str) -> dict[str, Any]:
    category = str(raw.get("category", "other")).lower()
    severity = str(raw.get("severity", "medium")).lower()
    tags = raw.get("tags") or []
    if not isinstance(tags, list):
        tags = [str(tags)]
    return {
        "category": category if category in VALID_CATEGORIES else "other",
        "severity": severity if severity in VALID_SEVERITIES else "medium",
        "summary": str(raw.get("summary", "")).strip()[:280],
        "recommended_action": str(raw.get("recommended_action", "")).strip()[:280],
        "anomaly_detected": bool(raw.get("anomaly_detected", False)),
        "tags": [str(t)[:40] for t in tags][:8],
        "source": source,
    }


# ---------------------------------------------------------------------------
# Deterministic offline mock
# ---------------------------------------------------------------------------
_KEYWORD_RULES = [
    (("fire", "smoke", "flame", "burning"), "fire_hazard", "critical"),
    (("intruder", "break-in", "trespass", "forced", "broke in"), "intrusion", "high"),
    (("blood", "injured", "unconscious", "collapse", "medical"), "medical", "critical"),
    (("broken", "vandal", "graffiti", "smashed"), "vandalism", "medium"),
    (("suspicious", "loiter", "prowler", "unknown person"), "suspicious_activity", "medium"),
    (("engine", "tire", "flat", "breakdown", "overheat"), "vehicle_issue", "medium"),
    (("flood", "leak", "spill", "chemical"), "environmental", "high"),
]


def _mock_analysis(text: str, has_images: bool) -> dict[str, Any]:
    lowered = (text or "").lower()
    category, severity = "other", "low"
    for keywords, cat, sev in _KEYWORD_RULES:
        if any(k in lowered for k in keywords):
            category, severity = cat, sev
            break
    anomaly = severity in ("high", "critical")
    summary = (text or "No description provided.").strip()
    summary = (summary[:200] + "…") if len(summary) > 200 else summary
    action = {
        "critical": "Dispatch nearest unit immediately and alert emergency services.",
        "high": "Escalate to a supervisor and send backup to verify.",
        "medium": "Log the report and schedule a follow-up inspection.",
        "low": "Record for the shift report; no immediate action required.",
    }[severity]
    tags = [category]
    if has_images:
        tags.append("photo_attached")
    return _coerce_analysis(
        {
            "category": category,
            "severity": severity,
            "summary": summary,
            "recommended_action": action,
            "anomaly_detected": anomaly,
            "tags": tags,
        },
        source="mock",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def analyze_incident(text: str, image_paths: list[str] | None = None) -> dict[str, Any]:
    """Classify an incident report and assess risk.

    Returns a validated dict: category, severity, summary, recommended_action,
    anomaly_detected, tags, source.
    """
    image_paths = image_paths or []
    if not is_enabled():
        return _mock_analysis(text, has_images=bool(image_paths))

    try:
        content: list[dict[str, Any]] = [
            {"type": "text", "text": f"Incident report:\n{text or '(no text)'}"}
        ]
        for path in image_paths:
            data_url = _encode_image(path)
            if data_url:
                content.append(
                    {"type": "image_url", "image_url": {"url": data_url}}
                )

        response = _client().chat.completions.create(
            model=settings.LLM_VISION_MODEL if image_paths else settings.LLM_TEXT_MODEL,
            messages=[
                {"role": "system", "content": _INCIDENT_SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        raw = json.loads(response.choices[0].message.content)
        return _coerce_analysis(raw, source="llm")
    except Exception as exc:  # noqa: BLE001 - never let AI break intake
        logger.warning("LLM incident analysis failed, falling back to mock: %s", exc)
        return _mock_analysis(text, has_images=bool(image_paths))


def generate_report_narrative(context: dict[str, Any]) -> dict[str, Any]:
    """Produce a natural-language narrative summary for a daily/monthly report."""
    if not is_enabled():
        return {"narrative": _mock_report(context), "source": "mock"}

    try:
        prompt = (
            "You are writing the executive summary of a security patrol report. "
            "Given these aggregated statistics as JSON, write a concise, "
            "professional narrative (3-5 sentences) highlighting coverage, "
            "notable incidents, carbon efficiency, and any recommendations.\n\n"
            f"{json.dumps(context, default=str)}"
        )
        response = _client().chat.completions.create(
            model=settings.LLM_TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )
        return {
            "narrative": response.choices[0].message.content.strip(),
            "source": "llm",
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM report generation failed, falling back to mock: %s", exc)
        return {"narrative": _mock_report(context), "source": "mock"}


def _mock_report(context: dict[str, Any]) -> str:
    period = context.get("period", "the reporting period")
    patrols = context.get("total_patrols", 0)
    incidents = context.get("total_incidents", 0)
    critical = context.get("critical_incidents", 0)
    distance = context.get("total_distance_km", 0)
    emissions = context.get("total_emission_kg", 0)
    return (
        f"During {period}, the fleet completed {patrols} patrol(s) covering "
        f"{distance} km and logged {incidents} incident(s), of which {critical} "
        f"were critical. Estimated carbon emissions totalled {emissions} kg CO2e. "
        "Coverage remained within operational targets; command recommends "
        "continued monitoring of high-priority locations and review of any "
        "critical incidents flagged by the AI analyst."
    )
