"""Replay the fictional Maple family's 3 days through the real plugin handlers.

    python demo/run_demo.py [--out demo/out] [--keep]

Uses an isolated data directory (never your Hermes profile), the demo family in
``demo/family.yaml``, and ``FixtureVision`` in place of a real model, so it runs
offline and sends nothing anywhere. For each day it calls the same tool
handlers Hermes would: intake -> generate_packet -> record_feedback -> status,
and writes a Markdown transcript to ``<out>/transcript.md``.

If a pipeline stage is not implemented yet (``not_implemented`` from the tool),
the runner says so in the transcript and, for packets only, writes a minimal
stand-in ``packet.json`` listing one item per rated skill so the feedback and
difficulty steps can still be demonstrated. Stand-ins are labelled as such.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "demo"))

from homework_coach.storage import Store  # noqa: E402
from homework_coach.tools import Runtime, make_handlers  # noqa: E402
from scenario import FixtureVision, format_ratings, load_scenario, ratings_for_packet  # noqa: E402


def stand_in_packet(store: Store, date: str, day: dict[str, Any]) -> None:
    children = {}
    for child_id, fb in (day.get("feedback") or {}).items():
        items, n = [], 0
        for skill, rs in fb["ratings"].items():
            for _ in rs:
                n += 1
                items.append({"id": str(n), "skill": skill, "format": "stand-in", "prompt": "", "answer": ""})
        children[child_id] = {"items": items}
    p = store.packet_dir(date) / "packet.json"
    p.write_text(json.dumps({"date": date, "stand_in": True, "children": children}, indent=2), encoding="utf-8")


def run(out: Path) -> dict[str, Any]:
    scenario = load_scenario()
    data_root = out / "data"
    store = Store(root=data_root, output_dir=data_root / "packets")
    settings = {"family_config": str(scenario["family_path"])}
    rt = Runtime(get_setting=lambda k, d=None: settings.get(k, d), llm=FixtureVision(), store=store)
    tools = make_handlers(rt)
    log: list[str] = ["# Homework Coach demo — the (fictional) Maple family", ""]
    results: dict[str, Any] = {"days": []}

    for day in scenario["days"]:
        date = day["date"]
        log += [f"## {day['label']}", ""]
        day_result: dict[str, Any] = {"date": date, "intake": [], "packet": None, "feedback": {}}

        for intake in day.get("intake") or []:
            res = json.loads(tools["homework_coach_intake"](
                {"child_id": intake["child"], "image_paths": [str(intake["image_path"])], "date": date}))
            day_result["intake"].append(res)
            shown = intake["image"]
            if res.get("ok"):
                log.append(f"- **Intake** {intake['child']}: `{shown}` → {res.get('summary', 'recorded')}")
            else:
                log.append(f"- **Intake** {intake['child']}: `{shown}` → _{res.get('error')}_")
        if day.get("intake"):
            log.append("")

        pkt = json.loads(tools["homework_coach_generate_packet"]({"date": date}))
        day_result["packet"] = pkt
        packet_items: dict[str, list] = {}
        if pkt.get("ok"):
            log.append(f"- **Packet** {date}: " + ", ".join(f"`{Path(p).name}`" for p in pkt.get("paths", [])))
            pj = store.packet_dir(date, create=False) / "packet.json"
            if pj.exists():
                packet_items = {c: v.get("items", []) for c, v in json.loads(pj.read_text("utf-8"))["children"].items()}
        else:
            log.append(f"- **Packet** {date}: _{pkt.get('error')}_ — using a labelled stand-in item list")
            stand_in_packet(store, date, day)
        log.append("")

        for child_id, fb in (day.get("feedback") or {}).items():
            ratings, _ = ratings_for_packet(fb["ratings"], packet_items.get(child_id))
            if not ratings:  # stand-in path
                ratings, _ = ratings_for_packet(fb["ratings"], None)
            res = json.loads(tools["homework_coach_record_feedback"](
                {"child_id": child_id, "packet_date": date, "ratings": format_ratings(ratings), "note": fb.get("note", "")}))
            day_result["feedback"][child_id] = res
            changes = res.get("changes") or {}
            change_txt = ", ".join(f"{s} **{d}**" for s, d in sorted(changes.items())) or "no change (hold)"
            log.append(f"- **Feedback** {child_id} `{format_ratings(ratings)}` — “{fb.get('note', '')}” → {change_txt}")
        log.append("")

        status = json.loads(tools["homework_coach_status"]({}))
        day_result["status"] = status
        for kid in status.get("children", []):
            levels = "; ".join(f"{s}: {v['dims']}" for s, v in sorted(kid["skills"].items())) or "—"
            log.append(f"  - {kid['name']} (grade {kid['grade']}, {kid['item_budget']} items): {levels}")
        log.append("")
        results["days"].append(day_result)

    out.mkdir(parents=True, exist_ok=True)
    (out / "transcript.md").write_text("\n".join(log) + "\n", encoding="utf-8", newline="\n")
    (out / "results.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8", newline="\n")
    return results


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=ROOT / "demo" / "out")
    ap.add_argument("--keep", action="store_true", help="keep an existing output dir instead of starting fresh")
    a = ap.parse_args()
    if a.out.exists() and not a.keep:
        shutil.rmtree(a.out)
    run(a.out)
    print((a.out / "transcript.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
