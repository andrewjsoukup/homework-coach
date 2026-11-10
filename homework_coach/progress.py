"""Parent progress report: is practice tracking class, and is the child getting more independent?

Built only from what the plugin already stores (homework-photo observations, packets, parent
ratings, skill state). No model call, no network: the same numbers the panel shows, summarized
in a form a parent can read in ten seconds.
"""
from __future__ import annotations

from datetime import date as Date, timedelta
from typing import Any

from . import config as cfg
from .models import Feedback


def _share_independent(ratings: list[str]) -> float | None:
    scored = [r for r in ratings if r in ("I", "S", "N")]
    return round(scored.count("I") / len(scored), 2) if scored else None


def _ratings_for(feedback: list[Feedback], skill: str | None, start: str, end: str) -> list[str]:
    out: list[str] = []
    for f in feedback:
        if not (start <= f.packet_date <= end):
            continue
        out += [r for item, r in f.item_ratings.items() if skill is None or f.item_skills.get(item) == skill]
    return out


def child_progress(store: Any, child: cfg.Child, today: str, days: int = 14) -> dict[str, Any]:
    end = Date.fromisoformat(today)
    cur_start = (end - timedelta(days=days - 1)).isoformat()
    prev_start = (end - timedelta(days=2 * days - 1)).isoformat()
    prev_end = (end - timedelta(days=days)).isoformat()
    obs = store.observations(child.id)
    fb = store.feedback(child.id)
    skills = store.load_skills(child.id)

    anchors = [{"date": o.date, "lesson": o.lesson, "skills": list(o.skills)} for o in obs[-5:]]
    latest = obs[-1] if obs else None
    stale_days = (end - Date.fromisoformat(latest.date)).days if latest else None

    per_skill = []
    for name, st in sorted(skills.items()):
        now = _share_independent(_ratings_for(fb, name, cur_start, today))
        before = _share_independent(_ratings_for(fb, name, prev_start, prev_end))
        per_skill.append({
            "skill": name, "level": st.level, "independent_now": now, "independent_before": before,
            "trend": (None if now is None or before is None else
                      "up" if now > before + 0.05 else "down" if now < before - 0.05 else "steady"),
            "changes": [h for h in st.history if cur_start <= h.get("date", "") <= today],
        })

    from . import curriculum as cur

    steer = cur.steer(store, child, today)
    practiced = sorted({f.packet_date for f in fb if cur_start <= f.packet_date <= today})
    return {
        "id": child.id, "name": child.name, "window_days": days,
        "class_focus": ({"date": latest.date, "lesson": latest.lesson, "skills": list(latest.skills)}
                        if latest else None),
        "homework_photos": len(obs), "recent_anchors": anchors, "days_since_last_photo": stale_days,
        "rated_practice_days": len(practiced),
        "independent_now": _share_independent(_ratings_for(fb, None, cur_start, today)),
        "independent_before": _share_independent(_ratings_for(fb, None, prev_start, prev_end)),
        "skills": per_skill,
        "steered_by": steer["source"],
        "class_unit": steer["unit"], "next_unit": steer["next_unit"], "unit_goals": steer["goals"],
        "teacher_materials": len(cur.materials(store, child.id)),
    }


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{round(x * 100)}%"


def message(report: dict[str, Any]) -> str:
    lines = [f"Homework Coach progress — last {report['window_days']} days"]
    for c in report["children"]:
        lines.append(f"\n{c['name']}")
        focus = c["class_focus"]
        if focus:
            what = focus["lesson"] or ", ".join(focus["skills"]) or "unlabelled"
            lines.append(f"- In class: {what} (from homework photo {focus['date']})")
        else:
            lines.append("- In class: no homework photo yet. Send a photo so practice follows class.")
        if c.get("class_unit"):
            u = c["class_unit"]
            lines.append(f"- Curriculum unit: {u['title']} ({u['start']} to {u['end']})")
            if c.get("unit_goals"):
                lines.append(f"  Goals: {'; '.join(c['unit_goals'][:3])}")
        if c.get("next_unit"):
            lines.append(f"- Coming up: {c['next_unit']['title']} from {c['next_unit']['start']}")
        lines.append(f"- Practice is steered by: {c.get('steered_by', 'grade default')}")
        if c["days_since_last_photo"] is not None and c["days_since_last_photo"] > 7:
            lines.append(f"- Last homework photo was {c['days_since_last_photo']} days ago; send a new one "
                         "so practice keeps up with class.")
        lines.append(f"- Practice: {c['rated_practice_days']} rated day(s); on their own "
                     f"{_pct(c['independent_now'])} (prior {c['window_days']} days {_pct(c['independent_before'])})")
        for s in c["skills"]:
            trend = {"up": "↑", "down": "↓", "steady": "→"}.get(s["trend"] or "", "")
            moved = len(s["changes"])
            lines.append(f"  · {s['skill']}: level {s['level']}, on their own {_pct(s['independent_now'])} {trend}"
                         + (f", adjusted {moved}×" if moved else ""))
    return "\n".join(lines)


def build(rt: Any, child_id: str | None = None, days: int = 14) -> dict[str, Any]:
    fam = rt.family()
    today = rt.today(fam)
    kids = [c for c in fam.children if not child_id or c.id == child_id]
    if child_id and not kids:
        raise KeyError(f"unknown child {child_id!r}")
    report = {"as_of": today, "window_days": days,
              "children": [child_progress(rt.store, c, today, days) for c in kids]}
    report["message"] = message(report)
    return report
