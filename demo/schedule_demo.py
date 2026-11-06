"""Play out a scheduled week for the fictional Maple family — offline, sends nothing.

    python demo/schedule_demo.py [--out demo/out/schedule]

Simulates per-child cron jobs made from the ``homework-coach:daily-packet`` blueprint
(one job per child, to show additive same-day parts), using the real tool handlers with
a stand-in cron identity in place of Hermes's scheduler:

  Mon  Pip job -> Nova job -> Nova job re-run (same files re-sent)
       parent replies "nova ..." / "pip ..." -> difficulty moves
  Sun  Nova job -> [SILENT] (not a practice day)
  Wed  Nova job -> packet one notch harder where the parent rated I

Each job's chat message is written to the transcript exactly as the agent would send it;
when Hermes is importable, the gateway's own MEDIA parser lists which files would attach.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from homework_coach import config, delivery  # noqa: E402
from homework_coach.storage import Store  # noqa: E402
from homework_coach.tools import Runtime, make_handlers  # noqa: E402

FAMILY = ROOT / "demo" / "family.yaml"
MON, WED, SUN = "2026-09-14", "2026-09-16", "2026-09-20"


def _attachments(msg: str) -> list[str]:
    try:
        from gateway.platforms.base import BasePlatformAdapter
    except Exception:
        return [ln[6:] for ln in msg.splitlines() if ln.startswith("MEDIA:")]
    return [p for p, _ in BasePlatformAdapter.extract_media(msg)[0]]


def run(out: Path) -> dict:
    if out.exists():
        shutil.rmtree(out)
    store = Store(root=out / "data", output_dir=out / "data" / "packets")
    settings = {"family_config": str(FAMILY)}
    state = {"cron": None, "today": MON}
    rt = Runtime(get_setting=lambda k, d=None: settings.get(k, d), store=store, cron_run=lambda: state["cron"])
    rt.today = lambda _f: state["today"]  # type: ignore[method-assign]
    tools = make_handlers(rt)
    fam = config.load(FAMILY)
    log = ["# Homework Coach — a scheduled week (fictional Maple family)", "",
           "## Jobs the parent created (from `/homework schedule`)", ""]
    log += [f"- `{g['blueprint_command']}`  → cron `{g['cron']}`" for g in delivery.schedule_groups(fam)]
    summary: dict = {"jobs": []}

    def job(date: str, children: str, label: str) -> dict:
        state.update(cron=SimpleNamespace(job_id=f"daily-{children}", scheduled_instant=f"{date}T09:00"),
                     today=date)
        res = json.loads(tools["homework_coach_generate_packet"]({"child_ids": [children]}))
        state["cron"] = None
        files = _attachments(res.get("message", ""))
        log.extend(["", f"## {label}", "", "```text", res.get("message", ""), "```",
                    f"Attachments the gateway would upload: {[Path(f).name for f in files] or 'none'}"])
        summary["jobs"].append({"label": label, "ok": res.get("ok"), "reused": res.get("reused"),
                                "added": res.get("added"), "attachments": files})
        return res

    pip = job(MON, "pip", "Mon — per-child job for Pip (children=pip)")
    nova = job(MON, "nova", "Mon — per-child job for Nova (children=nova)")
    mtimes = {f: Path(f).stat().st_mtime_ns for f in nova["paths"] + pip["paths"]}
    job(MON, "nova", "Mon — Nova job re-run (retry)")
    unchanged = all(Path(f).stat().st_mtime_ns == m for f, m in mtimes.items())
    log.append(f"\nAll Monday PDFs unchanged after the re-run: **{unchanged}**")

    data = json.loads((store.packets_root / MON / "packet.json").read_text(encoding="utf-8"))["children"]
    nova_t = data["nova"]["target_skill"]
    nova_ids = [i["id"] for i in data["nova"]["items"] if i["skill"] == nova_t]
    pip_ids = [i["id"] for i in data["pip"]["items"]][:2]
    reply = "nova " + " ".join(f"{i}=I" for i in nova_ids) + "\npip " + f"{pip_ids[0]}=S {pip_ids[1]}=N"
    state["today"] = MON
    fb = json.loads(tools["homework_coach_record_feedback"]({"reply": reply}))
    again = json.loads(tools["homework_coach_record_feedback"]({"reply": reply}))
    log += ["", "## Mon evening — parent replies in the chat", "", "```text", reply, "```",
            "Recorded:", "", "```text", fb.get("message", fb.get("error", "")), "```",
            f"Same reply sent twice → state unchanged: **{fb['children'] == again['children'] or again['ok']}**"]
    summary["feedback"] = fb

    sun = job(SUN, "nova", "Sun 09:00 — Nova's job (not a practice day)")
    wed = job(WED, "nova", "Wed 09:00 — Nova's job after Monday's feedback")
    wdata = json.loads((store.packets_root / WED / "packet.json").read_text(encoding="utf-8"))["children"]["nova"]
    before, after = data["nova"]["dims"][nova_t], wdata["dims"].get(nova_t, {})
    log += ["", f"Nova `{nova_t}` difficulty dims: Mon {before} → Wed {after}",
            f"Sunday job posted nothing ([SILENT]): **{sun.get('message') == '[SILENT]'}**"]
    summary.update(sun_silent=sun.get("message") == "[SILENT]", wed_ok=wed.get("ok"), dims_before=before,
                   dims_after=after, unchanged_after_rerun=unchanged)
    out.mkdir(parents=True, exist_ok=True)
    (out / "schedule_transcript.md").write_text("\n".join(log) + "\n", encoding="utf-8", newline="\n")
    (out / "schedule_results.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "demo" / "out" / "schedule")
    s = run(ap.parse_args().out)
    print(json.dumps({k: v for k, v in s.items() if k != "feedback"}, indent=2, default=str))
