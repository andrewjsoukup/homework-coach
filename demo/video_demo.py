"""Build the exact artifacts the 90-second demo video shows — offline, sends nothing.

    python demo/video_demo.py [--out demo/out/video]

Fictional Maple family only. Everything goes through the real tool handlers and the real
difficulty engine; nothing is hand-edited:

1. Intake Nova's synthetic arrays worksheet (FixtureVision stands in for the model).
2. "A week in": replay practice days where the parent rated every item I until support
   has faded the honest way (hint lines disappear at scaffold level 3). Five days today.
3. Hero day A: packet with no hint lines. The parent replies with one N on a multiplication item.
4. Hero day B: the next packet. Multiplication support comes back (hint lines return).

With ``--seed DIR`` it stops after step 2 and copies that state (plus the demo family
config) into DIR, e.g. a throwaway profile's ``plugin-data/homework-coach``, so the live
recording starts from the same faded-support state and steps 3-4 happen on camera.

Writes ``<out>/video_transcript.md`` (chat lines for the script), the two hero packets, and
1920x1080 PNG frames of each hero child page under ``<out>/frames/`` for B-roll.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date as Date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "demo"))

from homework_coach import config  # noqa: E402
from homework_coach.storage import Store  # noqa: E402
from homework_coach.tools import Runtime, make_handlers  # noqa: E402
from scenario import FixtureVision  # noqa: E402

FAMILY = ROOT / "demo" / "family.yaml"
PHOTO = ROOT / "demo" / "homework" / "nova_2026-09-14_arrays.png"
START = Date(2026, 9, 14)  # Monday: first photo
CHILD = "nova"
SKILL = "multiplication"


def _practice_days(start: Date, n: int, days: tuple[str, ...]) -> list[str]:
    names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    out, d = [], start
    while len(out) < n:
        if names[d.weekday()] in days:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _items(store: Store, date: str) -> list[dict]:
    pj = store.packet_dir(date, create=False) / "packet.json"
    return json.loads(pj.read_text("utf-8"))["children"][CHILD]["items"]


def _frame(pdf: Path, png: Path) -> None:
    import pypdfium2 as pdfium
    from PIL import Image

    page = pdfium.PdfDocument(str(pdf))[0].render(scale=1080 / 792 * 0.96).to_pil().convert("RGB")
    canvas = Image.new("RGB", (1920, 1080), (245, 243, 238))
    canvas.paste(page, ((1920 - page.width) // 2, (1080 - page.height) // 2))
    png.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(png, optimize=True)


def run(out: Path, warmup_days: int = 10, seed: Path | None = None) -> dict:
    if out.exists():
        shutil.rmtree(out)
    store = Store(root=out / "data", output_dir=out / "data" / "packets")
    settings = {"family_config": str(FAMILY)}
    state = {"today": START.isoformat()}
    rt = Runtime(get_setting=lambda k, d=None: settings.get(k, d), llm=FixtureVision(), store=store)
    rt.today = lambda _f: state["today"]  # type: ignore[method-assign]
    tools = make_handlers(rt)
    fam = config.load(FAMILY)
    days = _practice_days(START, warmup_days + 2, tuple(fam.child(CHILD).schedule.days))
    log = ["# Homework Coach — video run (fictional Maple family)", ""]

    intake = json.loads(tools["homework_coach_intake"](
        {"child_id": CHILD, "image_paths": [str(PHOTO)], "date": days[0]}))
    assert intake.get("ok"), intake
    log += ["## Photo in", "", f"- summary: {intake.get('summary')}",
            f"- parent message: {intake.get('message', '')}", ""]

    def packet(date: str) -> dict:
        state["today"] = date
        res = json.loads(tools["homework_coach_generate_packet"]({"date": date, "child_ids": [CHILD]}))
        assert res.get("ok"), res
        return res

    def rate(date: str, reply: str) -> dict:
        res = json.loads(tools["homework_coach_record_feedback"]({"reply": reply, "packet_date": date}))
        assert res.get("ok"), res
        return res

    # Rate everything I until multiplication support has just faded (scaffold raised to 3, the
    # level where hint lines disappear). The engine undoes the most recent raise on an N, so
    # stopping here makes the next N bring the hints back: a change you can see on paper.
    used = 0
    for date in days[:warmup_days]:
        packet(date)
        rate(date, f"{CHILD} " + " ".join(f"{i['id']}=I" for i in _items(store, date) if not i.get("optional")))
        used += 1
        st = store.load_skills(CHILD).get(SKILL)
        if st and st.dims["scaffold"] >= 3 and st.raised and st.raised[-1] == "scaffold":
            break
    else:
        raise SystemExit("multiplication scaffold never reached 3; raise --warmup-days")
    dims_before = json.loads(tools["homework_coach_status"]({"child_id": CHILD}))["children"][0]["skills"]
    log += [f"## After {used} all-I practice days", "", f"- skills: {json.dumps(dims_before)}", ""]
    if seed is not None:
        if seed.exists() and any(seed.iterdir()):
            raise SystemExit(f"refusing to seed into non-empty {seed}")
        shutil.copytree(out / "data", seed, dirs_exist_ok=True)
        shutil.copy2(FAMILY, seed / "family.yaml")
        return {"seeded": str(seed), "warmup_days_used": used, "dims": dims_before}

    day_a, day_b = days[used], days[used + 1]
    a = packet(day_a)
    items_a = [i for i in _items(store, day_a) if not i.get("optional")]
    mult_a = [i for i in items_a if i["skill"] == SKILL]
    assert mult_a, "hero day A has no multiplication item"
    miss = mult_a[0]["id"]
    reply = f"{CHILD} " + " ".join(f"{i['id']}={'N' if i['id'] == miss else 'I'}" for i in items_a)
    fb = rate(day_a, reply)
    b = packet(day_b)
    items_b = [i for i in _items(store, day_b) if not i.get("optional")]

    def hints(items: list[dict]) -> int:
        return sum(1 for i in items if i["skill"] == SKILL and i.get("hint"))

    log += [f"## Hero day A — {day_a}", "", "```text", a["message"], "```", "",
            f"Multiplication items with a hint line: {hints(items_a)} of {len(mult_a)}", "",
            "Parent replies:", "", "```text", reply, "```", "", "Hermes:", "", "```text", fb["message"], "```", "",
            f"## Hero day B — {day_b}", "", "```text", b["message"], "```", "",
            f"Multiplication items with a hint line: {hints(items_b)} of "
            f"{sum(1 for i in items_b if i['skill'] == SKILL)}", ""]

    frames = out / "frames"
    _frame(store.packet_dir(day_a) / f"{CHILD}_practice.pdf", frames / "A_child_packet.png")
    _frame(store.packet_dir(day_a) / "parent_key.pdf", frames / "A_parent_key.png")
    _frame(store.packet_dir(day_b) / f"{CHILD}_practice.pdf", frames / "B_child_packet.png")
    out.mkdir(parents=True, exist_ok=True)
    (out / "video_transcript.md").write_text("\n".join(log) + "\n", encoding="utf-8", newline="\n")
    return {"warmup_days_used": used, "day_a": day_a, "day_b": day_b, "dims_before": dims_before, "missed_item": miss,
            "changes": fb["children"][CHILD]["changes"], "hints_a": hints(items_a), "hints_b": hints(items_b),
            "mult_a": len(mult_a), "frames": sorted(str(p) for p in frames.glob("*.png"))}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=ROOT / "demo" / "out" / "video")
    ap.add_argument("--warmup-days", type=int, default=10)
    ap.add_argument("--seed", type=Path, help="copy the faded-support state into this (empty) plugin data dir and stop")
    a = ap.parse_args()
    print(json.dumps(run(a.out, a.warmup_days, a.seed), indent=2))


if __name__ == "__main__":
    main()
