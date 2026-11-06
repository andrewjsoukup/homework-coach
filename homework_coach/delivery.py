"""Delivery text, per-child schedules and chat-reply parsing (SPEC §9.4).

The plugin never sends messages itself. A scheduled run is an ordinary Hermes cron job made
from the ``homework-coach:daily-packet`` blueprint; the job's final reply is delivered by
Hermes to the job's ``deliver`` target, and ``MEDIA:<absolute path>`` lines in that reply are
uploaded as native attachments by the gateway. This module only builds that reply text.
"""
from __future__ import annotations

import re
from datetime import date as Date
from datetime import timedelta
from typing import Any

from .config import Child, FamilyConfig

BLUEPRINT_KEY = "homework-coach:daily-packet"
DOW = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

_REPLY_LINE = re.compile(r"^\s*(?P<child>[a-z0-9][a-z0-9-]*)\s*[:,-]?\s+(?P<ratings>.+?)\s*$", re.I)
_RATING_TOK = re.compile(r"^[A-Za-z]*\d+[:=]?[ISN]$", re.I)
_DATE_TOK = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _human_date(date: str) -> str:
    d = Date.fromisoformat(date)
    return f"{d.strftime('%a')} {d.strftime('%b')} {d.day}"


def packet_message(result: dict[str, Any], family: FamilyConfig) -> str:
    """Chat-ready delivery text for a ``build_packet`` result (``ok`` or ``reused``).

    One line per child, a ``MEDIA:`` line per PDF (child sheets first, then the key), and the
    one-line feedback syntax. Paths are absolute so the gateway can attach them.
    """
    date = result["date"]
    names = {c.id: c.name for c in family.children}
    items = result.get("items", {})
    files = result.get("files", {})
    lines = [f"Homework Coach practice — {_human_date(date)}"]
    if result.get("reused") and not result.get("added"):
        lines[0] += " (already generated today; same packet re-sent)"
    for cid, focus in result.get("children", {}).items():
        core = [i for i in items.get(cid, []) if not i.get("optional")]
        stretch = len(items.get(cid, [])) - len(core)
        extra = f" + {stretch} optional stretch" if stretch else ""
        lines.append(f"- {names.get(cid, cid)}: {focus} ({len(core)} items{extra})")
    lines.append("")
    for cid in result.get("children", {}):
        if cid in files:
            lines.append(f"MEDIA:{files[cid]}")
    for label, path in files.items():
        if label.startswith("parent_key"):
            lines.append(f"MEDIA:{path}")
    first = next(iter(result.get("children", {})), "child")
    ids = [i["id"] for i in items.get(first, [])][:3] or ["1", "2"]
    example = " ".join(f"{i}={r}" for i, r in zip(ids, "ISN"))
    lines += ["", "Parent key is a separate file — keep it away from the practice sheet.",
              f"After practice, reply with one line per child, e.g. `{first} {example}` "
              "(I = on their own, S = with support, N = not yet). Unrated items are fine."]
    return "\n".join(lines)


def failure_message(result: dict[str, Any], *, in_cron: bool) -> str:
    """Honest failure text: what failed, plus the full text packet + separated key if available.

    Inside a cron run the first line is Hermes's ``[CRON_FAILURE]`` marker so the run is recorded
    as failed while the evidence (including the text fallback) is still delivered verbatim.
    """
    head = f"Homework Coach: no PDF packet for {result.get('date', 'today')} — {result.get('error', 'failed')}."
    parts = (["[CRON_FAILURE]"] if in_cron else []) + [head]
    if result.get("fallback_text"):
        parts += ["Text version below (problems first, parent key after the divider):", "",
                  result["fallback_text"]]
    else:
        parts.append("Nothing was generated; no packet is attached.")
    return "\n".join(parts)


def next_packet_date(child: Child, after: str) -> str | None:
    """First date after ``after`` on the child's schedule (None if the schedule is empty)."""
    d = Date.fromisoformat(after)
    for n in range(1, 8):
        cand = d + timedelta(days=n)
        if DOW[cand.weekday()] in child.schedule.days:
            return cand.isoformat()
    return None


def schedule_groups(family: FamilyConfig) -> list[dict[str, Any]]:
    """Children grouped by identical schedule → one cron job (blueprint fill) per group."""
    groups: dict[tuple, list[Child]] = {}
    for c in family.children:
        groups.setdefault((c.schedule.time, c.schedule.days), []).append(c)
    out = []
    for (time_, days), kids in groups.items():
        cron = kids[0].schedule.to_cron()
        dow = cron.split()[-1]
        ids = ",".join(k.id for k in kids)
        out.append({
            "children": [k.id for k in kids], "time": time_, "days": list(days), "cron": cron,
            "blueprint_command": f"/blueprint {BLUEPRINT_KEY} time={time_} days={dow} children={ids} deliver=origin",
        })
    return out


def schedule_text(family: FamilyConfig) -> str:
    groups = schedule_groups(family)
    lines = ["Homework Coach does not create cron jobs itself. To schedule daily packets, run the "
             "command(s) below in the chat where packets should arrive (deliver=origin), or pick "
             "'Daily homework practice packet' on the Cron/Blueprints page:", ""]
    for g in groups:
        who = ", ".join(g["children"])
        lines.append(f"- {who} — {', '.join(g['days'])} at {g['time']}:")
        lines.append(f"  {g['blueprint_command']}")
    lines += ["", "Cron times follow the Hermes timezone setting; packet dates use the family timezone "
              f"({family.timezone}) — keep them the same. Re-running a job on the same day re-sends "
              "the same packet."]
    return "\n".join(lines)


def parse_reply(text: str, child_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Parse a parent's chat reply into ``{child_id: {"ratings": str, "date": str|None}}``.

    Accepts one line (or ``;``-separated segment) per child: ``nova 1=I 2=S S1=I``, optionally
    with a packet date (``nova 2026-11-04 1I 2S``). With a single configured child the name may
    be omitted. Raises ``ValueError`` naming the bad part.
    """
    known = {c.lower(): c for c in child_ids}
    out: dict[str, dict[str, Any]] = {}
    segments = [s for s in re.split(r"[\n;]+", text or "") if s.strip()]
    if not segments:
        raise ValueError("empty feedback")
    for seg in segments:
        toks = seg.replace(",", " ").split()
        child = None
        if toks and toks[0].lower().rstrip(":") in known:
            child = known[toks.pop(0).lower().rstrip(":")]
        elif len(known) == 1:
            child = next(iter(known.values()))
        else:
            raise ValueError(f"start each line with a child id ({', '.join(child_ids)}): {seg.strip()!r}")
        date = None
        if toks and _DATE_TOK.match(toks[0]):
            date = toks.pop(0)
        bad = [t for t in toks if not _RATING_TOK.match(t)]
        if bad or not toks:
            raise ValueError(f"cannot read ratings for {child}: {' '.join(bad) or '(none)'}; use e.g. '1=I 2=S S1=N'")
        prev = out.get(child)
        if prev and prev["date"] != date:
            raise ValueError(f"two different packet dates for {child}")
        out[child] = {"ratings": " ".join(([prev["ratings"]] if prev else []) + toks), "date": date}
    return out
