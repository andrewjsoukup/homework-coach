"""Run the 90-second demo one on-camera beat at a time — offline, fixture data only.

    python demo/demo_beats.py reset                      # wipe the take folder
    python demo/demo_beats.py photo                      # beat 1: intake Nova's synthetic worksheet
    python demo/demo_beats.py packet 2026-09-14          # beat 2: build + verify a packet for that date
    python demo/demo_beats.py fastforward                # "a week in": rate every item I until hints fade
    python demo/demo_beats.py feedback "nova 1=N 2=I 3=I 4=I 5=I 6=I" 2026-09-19   # beat 3
    python demo/demo_beats.py packet 2026-09-21          # beat 4: the next packet
    python demo/demo_beats.py hints 2026-09-19 2026-09-21  # on-screen proof: hint lines before/after
    python demo/demo_beats.py frames 2026-09-14 2026-09-19 2026-09-21  # 1920x1080 PNGs of page 1 (B-roll)

Same real tool handlers and difficulty engine as ``demo/video_demo.py``; ``FixtureVision``
stands in for the model, so nothing leaves the machine and no chat/email is sent. All state
lives in ``demo/out/take`` (git-ignored); ``--out`` picks another folder. Fictional Maple family.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "demo"))

from homework_coach import config  # noqa: E402
from homework_coach.storage import Store  # noqa: E402
from homework_coach.tools import Runtime, make_handlers  # noqa: E402
from scenario import FixtureVision  # noqa: E402
from video_demo import CHILD, FAMILY, PHOTO, SKILL, START, _frame, _practice_days  # noqa: E402

DEFAULT_OUT = ROOT / "demo" / "out" / "take"


def _tools(out: Path, today: str):
    store = Store(root=out / "data", output_dir=out / "data" / "packets")
    settings = {"family_config": str(FAMILY)}
    rt = Runtime(get_setting=lambda k, d=None: settings.get(k, d), llm=FixtureVision(), store=store)
    rt.today = lambda _f: today  # type: ignore[method-assign]
    return make_handlers(rt), store


def _items(store: Store, date: str) -> list[dict]:
    pj = store.packet_dir(date, create=False) / "packet.json"
    return [i for i in json.loads(pj.read_text("utf-8"))["children"][CHILD]["items"] if not i.get("optional")]


def _call(tools, name: str, args: dict) -> dict:
    res = json.loads(tools[name](args))
    if not res.get("ok"):
        raise SystemExit(f"{name} failed: {res.get('error')}")
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("reset")
    sub.add_parser("photo")
    p = sub.add_parser("packet"); p.add_argument("date")
    sub.add_parser("fastforward")
    f = sub.add_parser("feedback"); f.add_argument("reply"); f.add_argument("date")
    h = sub.add_parser("hints"); h.add_argument("dates", nargs="+")
    fr = sub.add_parser("frames"); fr.add_argument("dates", nargs="+")
    a = ap.parse_args()
    out: Path = a.out

    if a.cmd == "reset":
        if out.exists():
            shutil.rmtree(out)
        print(f"clean take folder: {out}")
        return

    if a.cmd == "photo":
        tools, _ = _tools(out, START.isoformat())
        res = _call(tools, "homework_coach_intake",
                    {"child_id": CHILD, "image_paths": [str(PHOTO)], "date": START.isoformat()})
        s = res["summary"]
        print(f"Homework read for Nova — {PHOTO.name}")
        print(f"  attempted {s['attempted']}, correct {s['correct']}, not scored {s['not_scored']} (crossed out / blank)")
        print(f"  strengths: {', '.join(s['strengths'])}")
        print(f"  likely slip: {'; '.join(s['likely_slips'])}")
        print(f"  checking target: {'; '.join(s['checking_targets'])}")
        print(f"  {s['caution']}")
        return

    if a.cmd == "packet":
        tools, _ = _tools(out, a.date)
        msg = _call(tools, "homework_coach_generate_packet", {"date": a.date, "child_ids": [CHILD]})["message"]
        # Show repo-relative paths on camera: absolute paths would put the OS user folder in frame.
        print(msg.replace(str(ROOT) + "\\", "").replace(str(ROOT) + "/", ""))
        return

    if a.cmd == "fastforward":
        fam = config.load(FAMILY)
        days = _practice_days(START, 12, tuple(fam.child(CHILD).schedule.days))
        for n, date in enumerate(days[:10], 1):
            tools, store = _tools(out, date)
            if not (store.packet_dir(date, create=False) / "packet.json").is_file():
                _call(tools, "homework_coach_generate_packet", {"date": date, "child_ids": [CHILD]})
            reply = f"{CHILD} " + " ".join(f"{i['id']}=I" for i in _items(store, date))
            _call(tools, "homework_coach_record_feedback", {"reply": reply, "packet_date": date})
            st = store.load_skills(CHILD).get(SKILL)
            if st and st.dims["scaffold"] >= 3 and st.raised and st.raised[-1] == "scaffold":
                print(f"{n} practice days ({days[0]}..{date}), every item rated I.")
                print(f"Multiplication support has faded: hint lines gone. Next practice day: {days[n]}")
                return
        raise SystemExit("multiplication support never faded; check the fixture data")

    if a.cmd == "feedback":
        tools, _ = _tools(out, a.date)
        print(_call(tools, "homework_coach_record_feedback", {"reply": a.reply, "packet_date": a.date})["message"])
        return

    if a.cmd == "hints":
        _, store = _tools(out, a.dates[0])
        for date in a.dates:
            mult = [i for i in _items(store, date) if i["skill"] == SKILL]
            print(f"{date}: multiplication items with a hint line: {sum(1 for i in mult if i.get('hint'))} of {len(mult)}")
        return

    if a.cmd == "frames":
        _, store = _tools(out, a.dates[0])
        for date in a.dates:
            d = store.packet_dir(date, create=False)
            for pdf in (d / f"{CHILD}_practice.pdf", d / "parent_key.pdf"):
                png = out / "frames" / f"{date}_{pdf.stem}.png"
                _frame(pdf, png)
                print(png)
        return


if __name__ == "__main__":
    main()
