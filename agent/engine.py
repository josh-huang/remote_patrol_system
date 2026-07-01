"""The agent decision loop — the "brain" that drives the system.

Given an operator message, the agent iteratively calls tools (reading state,
proposing actions) until it can answer. Write tools are never executed inline;
they are returned as `write_calls` and queued as pending AgentActions by `run`.

With an LLM API key it uses real tool-calling. Without one it falls back to a
deterministic keyword router so the whole experience remains demoable offline.
"""

from __future__ import annotations

import json
import logging

from django.conf import settings
from django.utils import timezone

from core.services import llm

from . import tools
from .models import AgentAction, AgentMessage
from .prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

MAX_STEPS = 6


def _client():
    from openai import OpenAI

    return OpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)


# ---------------------------------------------------------------------------
# LLM tool-calling loop
# ---------------------------------------------------------------------------
def _run_llm(history: list[dict]) -> tuple[str, list, list]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
    steps: list = []
    write_calls: list = []
    client = _client()
    schema = tools.openai_schema()

    for _ in range(MAX_STEPS):
        response = client.chat.completions.create(
            model=settings.LLM_TEXT_MODEL,
            messages=messages,
            tools=schema,
            tool_choice="auto",
            temperature=0.2,
        )
        msg = response.choices[0].message

        if not msg.tool_calls:
            return msg.content or "", steps, write_calls

        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            }
        )

        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            if tools.is_write(name):
                summary = tools.summarize(name, args)
                write_calls.append({"tool_name": name, "arguments": args, "summary": summary})
                steps.append(
                    {"tool": name, "kind": "write", "arguments": args, "status": "queued"}
                )
                result = {"status": "queued_for_confirmation", "summary": summary}
            else:
                result = tools.execute(name, args)
                steps.append(
                    {"tool": name, "kind": "read", "arguments": args, "result": result}
                )

            messages.append(
                {"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result, default=str)}
            )

    # Ran out of steps — ask the model for a final synthesis without tools.
    response = client.chat.completions.create(
        model=settings.LLM_TEXT_MODEL, messages=messages, temperature=0.2
    )
    return response.choices[0].message.content or "", steps, write_calls


# ---------------------------------------------------------------------------
# Deterministic offline fallback
# ---------------------------------------------------------------------------
def _run_mock(user_text: str) -> tuple[str, list, list]:
    text = (user_text or "").lower()
    steps: list = []
    write_calls: list = []

    def use(name, args=None):
        result = tools.execute(name, args or {})
        steps.append({"tool": name, "kind": "read", "arguments": args or {}, "result": result})
        return result

    def has(*kw):
        return any(k in text for k in kw)

    # Route / plan → propose a write action (queued for confirmation).
    if has("规划", "路线", "route", "plan", "派车", "dispatch", "调度"):
        vehicles = use("list_vehicles", {"available_only": True}).get("vehicles", [])
        vids = [v["id"] for v in vehicles]
        if vids:
            args = {"name": "AI-planned patrol", "vehicle_ids": vids}
            summary = tools.summarize("create_patrol_plan", args)
            write_calls.append({"tool_name": "create_patrol_plan", "arguments": args, "summary": summary})
            steps.append({"tool": "create_patrol_plan", "kind": "write", "arguments": args, "status": "queued"})
            answer = (
                f"I found {len(vids)} available vehicle(s). I've prepared a plan that "
                f"auto-routes them across all active locations (priority-first). "
                f"Confirm the action below to create and dispatch it."
            )
        else:
            answer = "No available vehicles right now, so I can't propose a route."
        return answer, steps, write_calls

    # Incidents / anomalies
    if has("事件", "incident", "异常", "anomaly", "critical", "严重", "危"):
        sev = "critical" if has("critical", "严重", "危") else None
        data = use("list_incidents", {"severity": sev, "limit": 5}).get("incidents", [])
        if not data:
            return "No matching incidents found.", steps, write_calls
        lines = [
            f"- #{i['id']} [{i['ai_severity']}] {i['ai_category']} at "
            f"{i['location_name'] or 'unknown'}: {i['ai_recommended_action']}"
            for i in data
        ]
        return "Here are the relevant incidents:\n" + "\n".join(lines), steps, write_calls

    # Live positions / where are the vehicles
    if has("位置", "哪", "where", "live", "map", "地图", "gps"):
        pos = use("get_live_positions").get("positions", [])
        lines = [f"- {p['plate_number']}: ({p['latitude']:.4f}, {p['longitude']:.4f})" for p in pos]
        return "Current vehicle positions:\n" + "\n".join(lines), steps, write_calls

    # Report
    if has("报告", "report", "日报", "月报", "summary", "总结"):
        period = "monthly" if has("月", "month") else "daily"
        rep = use("generate_report", {"period": period})
        narr = llm.generate_report_narrative(rep)
        return narr["narrative"], steps, write_calls

    # Emissions / carbon
    if has("碳", "排放", "emission", "carbon", "co2"):
        s = use("get_dashboard_summary")
        return (
            f"Total estimated emissions so far: {s['total_emission_kg']} kg CO2e "
            f"across the fleet ({s['vehicles_total']} vehicles).",
            steps,
            write_calls,
        )

    # Default → dashboard overview
    s = use("get_dashboard_summary")
    return (
        f"Command overview: {s['vehicles_available']}/{s['vehicles_total']} vehicles "
        f"available, {s['active_locations']} active locations, {s['open_incidents']} "
        f"open incident(s) ({s['critical_incidents']} critical), "
        f"{s['total_emission_kg']} kg CO2e total. Ask me to plan a route, review "
        f"incidents, or generate a report.",
        steps,
        write_calls,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def _history(conversation) -> list[dict]:
    msgs = []
    for m in conversation.messages.filter(role__in=["user", "assistant"]):
        msgs.append({"role": m.role, "content": m.content})
    return msgs


def run(conversation, user_text: str, user, origin=AgentAction.Origin.CHAT):
    """Process one operator turn. Returns the persisted assistant AgentMessage."""
    AgentMessage.objects.create(
        conversation=conversation, role=AgentMessage.Role.USER, content=user_text
    )

    try:
        if llm.is_enabled():
            content, steps, write_calls = _run_llm(_history(conversation))
        else:
            content, steps, write_calls = _run_mock(user_text)
    except Exception as exc:  # noqa: BLE001 - never crash the endpoint
        logger.warning("Agent LLM loop failed, using mock: %s", exc)
        content, steps, write_calls = _run_mock(user_text)

    assistant = AgentMessage.objects.create(
        conversation=conversation,
        role=AgentMessage.Role.ASSISTANT,
        content=content,
        steps=steps,
    )

    for call in write_calls:
        AgentAction.objects.create(
            conversation=conversation,
            message=assistant,
            origin=origin,
            tool_name=call["tool_name"],
            arguments=call["arguments"],
            summary=call["summary"],
        )

    return assistant


def confirm_action(action: AgentAction, user) -> AgentAction:
    """Execute a previously proposed write action after operator confirmation."""
    if action.status != AgentAction.Status.PENDING:
        return action
    result = tools.execute(action.tool_name, action.arguments)
    action.result = result
    action.status = (
        AgentAction.Status.FAILED
        if isinstance(result, dict) and result.get("error")
        else AgentAction.Status.CONFIRMED
    )
    action.resolved_by = user
    action.resolved_at = timezone.now()
    action.save()
    return action


def reject_action(action: AgentAction, user) -> AgentAction:
    if action.status == AgentAction.Status.PENDING:
        action.status = AgentAction.Status.REJECTED
        action.resolved_by = user
        action.resolved_at = timezone.now()
        action.save()
    return action
