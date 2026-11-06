"""Difficulty engine (SPEC §7): I/S/N feedback moves at most one dimension per skill.

Pure functions over SkillState so the policy is testable without storage.
"""
from __future__ import annotations

import re
from typing import Iterable

from .models import DIMENSIONS, RATING_SCORE, Feedback, SkillState

MAX_LEVEL = 5
MIN_LEVEL = 1
WINDOW = 2
MAX_SKILLS_MOVED_PER_PACKET = 2

_TOKEN_RE = re.compile(r"^([A-Za-z]*\d+)[:=]?([ISN])$", re.I)


def parse_ratings(raw: str) -> dict[str, str]:
    """Parse ``"1I 2S 3N"``, ``"1:I, 2:S"`` or ``"q1=I q2=N"`` into ``{item_id: rating}``."""
    out: dict[str, str] = {}
    for tok in re.split(r"[,;\s]+", raw.strip()):
        if not tok:
            continue
        m = _TOKEN_RE.match(tok)
        if not m:
            raise ValueError(f"cannot parse rating {tok!r}; use e.g. '1I 2S 3N'")
        out[m.group(1)] = m.group(2).upper()
    if not out:
        raise ValueError("no ratings given")
    return out


def _skill_windows(feedback: Iterable[Feedback], skill: str) -> list[list[str]]:
    """Ratings for ``skill`` per submission, oldest first, last WINDOW submissions only."""
    subs = []
    for fb in feedback:
        r = [rating for item, rating in fb.item_ratings.items() if fb.item_skills.get(item) == skill]
        if r:
            subs.append(r)
    return subs[-WINDOW:]


def decide(state: SkillState, feedback: Iterable[Feedback]) -> str:
    """Return ``"up"``, ``"down"`` or ``"hold"`` for one skill."""
    windows = _skill_windows(list(feedback), state.skill)
    if not windows:
        return "hold"
    if any(r == "N" for r in windows[-1]):
        return "down"
    flat = [r for w in windows for r in w]
    if len(flat) >= 2 and len(windows) >= 1 and all(r == "I" for r in flat):
        return "up"
    return "hold"


def apply(state: SkillState, decision: str, *, date: str = "") -> SkillState:
    """Mutate and return ``state`` according to ``decision`` (one dimension at most)."""
    if decision == "up":
        candidates = [d for d in _rotation_from(state) if state.dims[d] < MAX_LEVEL]
        if candidates:
            dim = candidates[0]
            state.dims[dim] += 1
            state.raised.append(dim)
            state.history.append({"date": date, "change": "up", "dim": dim})
    elif decision == "down":
        dim = state.raised.pop() if state.raised else "scaffold"
        if state.dims[dim] > MIN_LEVEL:
            state.dims[dim] -= 1
            state.history.append({"date": date, "change": "down", "dim": dim})
        else:
            state.history.append({"date": date, "change": "hold-floor", "dim": dim})
    state.level = max(MIN_LEVEL, min(MAX_LEVEL, round(sum(state.dims.values()) / len(state.dims))))
    return state


def _rotation_from(state: SkillState) -> list[str]:
    """Rotate scaffold -> steps -> representation -> number_range starting after the last raise."""
    order = list(DIMENSIONS)
    if state.raised:
        i = order.index(state.raised[-1]) + 1
        order = order[i:] + order[:i]
    return order


def update_child(states: dict[str, SkillState], feedback: list[Feedback], *, date: str = "",
                 touched: set[str] | None = None) -> dict[str, str]:
    """Apply the policy across a child's skills; at most MAX_SKILLS_MOVED_PER_PACKET move.

    Downs take priority over ups (safety first), then alphabetical for determinism. When
    ``touched`` is given, only those skills (the ones rated in the newest submission) may move,
    so an unrated skill is not raised again on every later submission.
    """
    decisions = {s: (decide(st, feedback) if touched is None or s in touched else "hold")
                 for s, st in states.items()}
    moving = sorted((s for s, d in decisions.items() if d != "hold"),
                    key=lambda s: (decisions[s] != "down", s))
    allowed = set(moving[:MAX_SKILLS_MOVED_PER_PACKET])
    result = {}
    for s, d in decisions.items():
        final = d if s in allowed else "hold"
        apply(states[s], final, date=date)
        result[s] = final
    return result


def effective_feedback(feedback: Iterable[Feedback]) -> list[Feedback]:
    """One merged record per packet date, oldest packet first.

    Several submissions for the same packet (a correction, or items rated in two sittings) are
    merged with later ratings winning, so re-sending the same reply never counts twice.
    """
    merged: dict[str, Feedback] = {}
    for fb in feedback:
        cur = merged.get(fb.packet_date)
        if cur is None:
            merged[fb.packet_date] = Feedback(date=fb.date, child_id=fb.child_id, packet_date=fb.packet_date,
                                              item_ratings=dict(fb.item_ratings), item_skills=dict(fb.item_skills),
                                              note=fb.note)
            continue
        cur.item_ratings.update(fb.item_ratings)
        cur.item_skills.update(fb.item_skills)
        cur.date = fb.date
        if fb.note and fb.note not in cur.note:
            cur.note = f"{cur.note}\n{fb.note}".strip()
    return [merged[k] for k in sorted(merged)]


def replay(feedback: Iterable[Feedback]) -> tuple[dict[str, SkillState], dict[str, dict[str, str]]]:
    """Rebuild skill state from the whole feedback log (deterministic, idempotent).

    Returns ``(states, moves_by_packet_date)``; history entries are dated with the packet date
    whose ratings caused them.
    """
    eff = effective_feedback(feedback)
    states: dict[str, SkillState] = {}
    moves: dict[str, dict[str, str]] = {}
    for i, fb in enumerate(eff):
        touched = {fb.item_skills[k] for k in fb.item_ratings if k in fb.item_skills}
        for s in touched:
            states.setdefault(s, SkillState(skill=s))
        res = update_child(states, eff[: i + 1], date=fb.packet_date, touched=touched)
        moves[fb.packet_date] = {s: d for s, d in res.items() if d != "hold"}
    return states, moves


__all__ = ["parse_ratings", "decide", "apply", "update_child", "effective_feedback", "replay", "RATING_SCORE"]
