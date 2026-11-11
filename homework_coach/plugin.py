"""Registration: public PluginContext surfaces only (SPEC §8)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import daily, schemas, writer
from .delivery import schedule_text
from .tools import Runtime, make_handlers

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

TOOLSET = "homework_coach"
PLUGIN_DIR = Path(__file__).resolve().parent.parent
AUX_TASK = "homework_vision"

BLUEPRINT_PROMPT = (
    "Call homework_coach_generate_packet once with child_ids=[\"{children}\"] and no date. "
    "Your final reply must be exactly the tool result's `message` "
    "field, verbatim: it already lists each child's focus and the MEDIA: lines that attach the "
    "PDFs. If the tool returns ok=false, reply with its `message` field verbatim (it starts with "
    "[CRON_FAILURE] and carries a text version of the packet). Never write your own packet, paths "
    "or answers."
)


USAGE = ("Usage: /homework status [child] | packet [YYYY-MM-DD] [child...] | "
         "feedback <child> [YYYY-MM-DD] 1=I 2=S S1=N | progress [child] [days] | schedule | "
         "daily [on|off] [builtin|model]")


def _message_or_json(raw: str) -> str:
    """Slash replies are read by people: prefer the handler's ready-made ``message``."""
    try:
        data = json.loads(raw)
    except ValueError:
        return raw
    if data.get("message"):
        return data["message"] if data.get("ok") else f"Not done: {data.get('error')}\n{data['message']}"
    return raw if data.get("ok") else f"Not done: {data.get('error')}"


def _slash(handlers: dict[str, Any], rt: Runtime):
    def handle(raw_args: str = "", **_: Any) -> str:
        parts = (raw_args or "").split()
        sub = parts[0].lower() if parts else "status"
        if sub == "status":
            return handlers["homework_coach_status"]({"child_id": parts[1]} if len(parts) > 1 else {})
        if sub == "feedback" and len(parts) >= 3:
            return _message_or_json(handlers["homework_coach_record_feedback"]({"reply": " ".join(parts[1:])}))
        if sub == "packet":
            args: dict[str, Any] = {}
            rest = parts[1:]
            if rest and _DATE_RE.match(rest[0]):
                args["date"] = rest.pop(0)
            if rest:
                args["child_ids"] = rest
            return _message_or_json(handlers["homework_coach_generate_packet"](args))
        if sub == "progress":
            pargs: dict[str, Any] = {}
            for tok in parts[1:]:
                if tok.isdigit():
                    pargs["days"] = int(tok)
                else:
                    pargs["child_id"] = tok
            return _message_or_json(handlers["homework_coach_progress"](pargs))
        if sub == "daily":
            try:
                change: dict[str, Any] = {}
                for tok in (p.lower() for p in parts[1:]):
                    if tok in ("on", "off"):
                        change["enabled"] = tok == "on"
                    elif tok in daily.WRITERS:
                        change["writer"] = tok
                    else:
                        return USAGE
                if change:
                    daily.save_settings(rt.store, change)
                return daily.describe(rt)
            except Exception as e:  # never raise from a slash handler
                return f"Not done: {type(e).__name__}: {e}"
        if sub == "schedule":
            try:
                return schedule_text(rt.family())
            except Exception as e:  # never raise from a slash handler
                return f"Not done: {type(e).__name__}: {e}"
        return USAGE
    return handle


def register(ctx: Any) -> None:
    cron = getattr(ctx, "current_cron_execution", None)
    rt = Runtime(get_setting=lambda k, d=None: ctx.get_config(k, default=d), llm=getattr(ctx, "llm", None),
                 cron_run=cron if callable(cron) else None)
    handlers = make_handlers(rt)
    for schema in schemas.ALL:
        ctx.register_tool(name=schema["name"], toolset=TOOLSET, schema=schema, handler=handlers[schema["name"]])

    ctx.register_command("homework", _slash(handlers, rt),
                         description="Homework Coach: status, packet, feedback, progress, schedule, daily",
                         args_hint="status|packet|feedback|progress|schedule|daily")

    ctx.register_auxiliary_task(AUX_TASK, display_name="Homework Coach vision",
                                description="Reads homework photos for Homework Coach.", inherit_from="vision")
    ctx.register_auxiliary_task(writer.AUX_TASK, display_name="Homework Coach sheet writer",
                                description=("Writes and double-checks the problems for practice sheets when "
                                             "'Who writes the sheet' is set to your model. Uses your main "
                                             "model unless you pick another here."))

    # Daily sheets: an in-process check (no Hermes cron job). It does nothing until a parent turns
    # Daily sheets on in the plugin's settings; unloading the plugin stops it.
    stop = daily.start_timer(lambda: rt)
    on_unload = getattr(ctx, "on_unload", None)
    if stop is not None and callable(on_unload):
        on_unload(stop)

    skills_dir = PLUGIN_DIR / "skills"
    if skills_dir.is_dir():
        for child in sorted(skills_dir.iterdir()):
            if (child / "SKILL.md").is_file():
                ctx.register_skill(child.name, child / "SKILL.md")

    ctx.register_automation_blueprint(
        "daily-packet",
        title="Daily homework practice packet",
        description=("Optional: also send each day's practice PDFs to a chat. Daily sheets in the "
                     "plugin's settings already make the sheet in the workspace without this job. "
                     "Make one job per schedule; /homework schedule prints the exact commands."),
        category="family",
        # Built-in weekday presets have no Mon-Sat option, so days is a cron day-of-week text slot.
        schedule_template="{minute} {hour} * * {days}",
        prompt_template=BLUEPRINT_PROMPT,
        slots=[
            {"name": "time", "type": "time", "label": "What time?", "default": "09:00"},
            {"name": "days", "type": "text", "label": "Which days? (cron day-of-week, 1-6 = Mon-Sat)",
             "default": "1-6"},
            {"name": "children", "type": "text", "label": "Which children? (ids, comma-separated, or all)",
             "default": "all"},
            {"name": "deliver", "type": "enum", "label": "Where to deliver?", "default": "origin",
             "options": ["origin", "local"], "strict": False},
        ],
        skills=["homework-coach:workflow"],
        tags=["family", "daily"],
    )
