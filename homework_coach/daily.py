"""Daily sheets: the opt-in switch, the "is a sheet due?" check and the in-process timer.

Nothing here talks to Hermes's scheduler. When a parent turns Daily sheets on, a small
background thread in each long-lived Hermes process that loaded the plugin checks once a
minute whether a scheduled child still has no sheet for today, and builds it through the
same tool handler chat uses. The desktop workspace runs the same check when it is opened,
so a computer that was off at the practice time catches up the moment someone looks.

Safe to run in several processes at once: ``build_packet`` holds a per-date lock and never
overwrites a verified folder, so the worst case is one process waiting for the other.
"""
from __future__ import annotations

import contextvars
import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import Any, Callable

from .storage import Store, _atomic_write

logger = logging.getLogger(__name__)

WRITERS = ("builtin", "model")
GUIDANCE_MAX = 600
SETTINGS_FILE = "daily.json"
STATE_FILE = "daily_state.json"
TIMER_FILE = "daily_timer.json"
THREAD_NAME = "homework-coach-daily"
FIRST_TICK_SECONDS = 45.0   # short-lived CLI processes exit before the first check
TICK_SECONDS = 60.0
TIMER_ALIVE_SECONDS = 3 * 60
RETRY_SECONDS = 10 * 60
RUNNING_STALE_SECONDS = 20 * 60  # a model-written sheet for several children takes minutes
MAX_ATTEMPTS = 6
WRITE_TRIES = 8
DOW = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


# -- settings ------------------------------------------------------------------------------------
def settings(store: Store) -> dict[str, Any]:
    """``{"enabled": bool, "writer": "builtin" | "model", "guidance": {child_id: text}}``.

    Off and built-in until a parent says otherwise. ``guidance`` is what the parent asked the
    model-written sheets to work on, per child."""
    try:
        raw = json.loads((store.root / SETTINGS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    writer = raw.get("writer")
    g = raw.get("guidance")
    guidance = {str(k): " ".join(v.split())[:GUIDANCE_MAX] for k, v in g.items()
                if isinstance(v, str) and v.strip()} if isinstance(g, dict) else {}
    return {"enabled": raw.get("enabled") is True, "writer": writer if writer in WRITERS else "builtin",
            "guidance": guidance}


def save_settings(store: Store, body: dict[str, Any]) -> dict[str, Any]:
    cur = settings(store)
    if "enabled" in body:
        if not isinstance(body["enabled"], bool):
            raise ValueError("enabled must be true or false")
        cur["enabled"] = body["enabled"]
    if "writer" in body:
        if body["writer"] not in WRITERS:
            raise ValueError(f"writer must be one of {list(WRITERS)}")
        cur["writer"] = body["writer"]
    if "guidance" in body:
        g = body["guidance"]
        if not isinstance(g, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in g.items()):
            raise ValueError("guidance must give text for a child id")
        for k, v in g.items():
            v = " ".join(v.split())[:GUIDANCE_MAX]
            if v:
                cur["guidance"][k] = v
            else:
                cur["guidance"].pop(k, None)
    _atomic_write(store.root / SETTINGS_FILE, json.dumps(cur, indent=2) + "\n")
    return cur


# -- state ---------------------------------------------------------------------------------------
def _read(store: Store, name: str) -> dict[str, Any]:
    try:
        raw = json.loads((store.root / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def state(store: Store) -> dict[str, Any]:
    return _read(store, STATE_FILE)


def _write(store: Store, name: str, data: dict[str, Any]) -> None:
    text = json.dumps(data, indent=2) + "\n"
    for attempt in range(WRITE_TRIES):
        try:
            _atomic_write(store.root / name, text)
            return
        except OSError:
            # Windows refuses to replace a file another thread is reading at that instant; the
            # reader is gone a moment later. A status note must never stop a sheet being made.
            if attempt == WRITE_TRIES - 1:
                logger.debug("homework-coach: could not write %s", name, exc_info=True)
            else:
                time.sleep(0.05 * (attempt + 1))


def timer_alive(store: Store) -> bool:
    """True when a Hermes process ran the once-a-minute check in the last few minutes."""
    try:
        return time.time() - float(_read(store, TIMER_FILE).get("at") or 0) < TIMER_ALIVE_SECONDS
    except (TypeError, ValueError):
        return False


def model_ready(rt: Any) -> bool:
    return rt.llm is not None and hasattr(rt.llm, "complete_structured")


def status(rt: Any) -> dict[str, Any]:
    """What the settings page and Today show: the switch, the writer and the last automatic run."""
    last = state(rt.store)
    return {**settings(rt.store), "model_ready": model_ready(rt), "timer_alive": timer_alive(rt.store),
            "last": {k: last.get(k) for k in ("date", "status", "at", "error", "children")} if last else None}


def describe(rt: Any) -> str:
    """One plain paragraph for ``/homework daily``."""
    s = settings(rt.store)
    fam = rt.family()
    who = "your model (the built-in writer steps in if it is unavailable)" if s["writer"] == "model" \
        else "the built-in writer"
    if not s["enabled"]:
        return (f"Daily sheets are off. Turn them on with /homework daily on. "
                f"Problems would be written by {who}.")
    times = sorted({c.schedule.time for c in fam.children} or {fam.schedule.time})
    return (f"Daily sheets are on: each child's sheet and the parent key are made at "
            f"{' / '.join(times)} ({fam.timezone}) on their practice days. Problems are written by {who}.")


# -- due check -----------------------------------------------------------------------------------
def _now(family: Any) -> datetime:
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo(family.timezone))


def due(rt: Any, now: datetime | None = None) -> tuple[str, list[str]]:
    """``(today, [child ids])``: scheduled today, practice time reached, and no sheet in today's folder."""
    from . import packet

    fam = rt.family()
    now = now or _now(fam)
    day, hhmm, dow = now.date().isoformat(), now.strftime("%H:%M"), DOW[now.weekday()]
    pdir = rt.store.packet_dir(day, create=False)
    data = packet._load(pdir) if packet._is_verified(pdir) else None
    have = set((data or {}).get("children") or {})
    return day, [c.id for c in fam.children
                 if dow in c.schedule.days and c.schedule.time <= hhmm and c.id not in have]


def _blocked(st: dict[str, Any], day: str) -> str | None:
    if st.get("date") != day:
        return None
    since = time.time() - float(st.get("last_attempt") or 0)
    if st.get("status") == "running" and since < RUNNING_STALE_SECONDS:
        return "already running"
    if st.get("status") == "failed":
        if int(st.get("attempts") or 0) >= MAX_ATTEMPTS:
            return "gave up for today"
        if since < RETRY_SECONDS:
            return "waiting to retry"
    return None


def should_run(rt: Any, now: datetime | None = None) -> bool:
    """Cheap pre-check for the catch-up on open; never raises."""
    try:
        if not settings(rt.store)["enabled"]:
            return False
        day, ids = due(rt, now)
        return bool(ids) and _blocked(state(rt.store), day) is None
    except Exception:
        return False


def run_due(rt: Any, now: datetime | None = None) -> dict[str, Any]:
    """Build today's sheet for every child who is due. Idempotent; never raises."""
    try:
        store = rt.store
        if not settings(store)["enabled"]:
            return {"ran": False, "reason": "off"}
        day, ids = due(rt, now)
        if not ids:
            return {"ran": False, "reason": "nothing due", "date": day}
        st = state(store)
        wait = _blocked(st, day)
        if wait:
            return {"ran": False, "reason": wait, "date": day}
        stamp = (now or _now(rt.family())).isoformat(timespec="minutes")
        attempts = (int(st.get("attempts") or 0) if st.get("date") == day else 0) + 1
        base = {"date": day, "children": ids, "attempts": attempts, "last_attempt": time.time(), "at": stamp}
        _write(store, STATE_FILE, {**base, "status": "running", "error": ""})
        from .tools import make_handlers

        res = json.loads(make_handlers(rt)["homework_coach_generate_packet"]({"date": day, "child_ids": ids}))
        ok = res.get("ok") is True
        if not ok and not due(rt, now)[1]:
            ok = True  # another Hermes process finished the same sheet while this one waited
        err = "" if ok else str(res.get("error") or "the sheet could not be made")[:300]
        _write(store, STATE_FILE, {**base, "status": "ok" if ok else "failed", "error": err})
        return {"ran": True, "ok": ok, "date": day, "children": ids, "error": err}
    except Exception as e:  # config missing, disk error...: report, try again next tick
        logger.debug("homework-coach: daily check failed", exc_info=True)
        return {"ran": False, "reason": f"{type(e).__name__}: {e}"}


# -- timer ---------------------------------------------------------------------------------------
def tick(rt: Any) -> dict[str, Any]:
    """One timer pass: note that the check is alive (only while Daily sheets is on), then build."""
    if settings(rt.store)["enabled"]:
        _write(rt.store, TIMER_FILE, {"at": time.time(), "pid": os.getpid()})
    return run_due(rt)


def start_timer(make_runtime: Callable[[], Any], *, first: float = FIRST_TICK_SECONDS,
                every: float = TICK_SECONDS) -> Callable[[], None] | None:
    """Start the once-a-minute check in this process. Returns a stop function, or ``None`` when a
    timer is already running here (the plugin package can be loaded twice in one process)."""
    for t in threading.enumerate():
        other = getattr(t, "hc_stop", None)
        if t.name == THREAD_NAME and t.is_alive() and other is not None and not other.is_set():
            return None
    stop = threading.Event()

    def loop() -> None:
        if stop.wait(first):
            return
        while True:
            try:
                tick(make_runtime())
            except Exception:
                logger.debug("homework-coach: daily timer tick failed", exc_info=True)
            if stop.wait(every):
                return

    ctx = contextvars.copy_context()  # keep the profile scope the plugin was loaded in
    thread = threading.Thread(target=ctx.run, args=(loop,), daemon=True, name=THREAD_NAME)
    thread.hc_stop = stop  # type: ignore[attr-defined]
    thread.start()
    return stop.set
