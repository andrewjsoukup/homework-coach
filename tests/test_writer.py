"""Model-written sheets: the model only chooses; the generators build, compute and verify."""
from __future__ import annotations

import json
import random
from pathlib import Path
from types import SimpleNamespace

import pytest

from homework_coach import catalog, config, daily, packet, verify, writer
from homework_coach.generators import GENERATORS, Gen
from homework_coach.models import Feedback, Observation, ObservedItem
from homework_coach.storage import Store
from homework_coach.tools import Runtime, make_handlers

from .conftest import EXAMPLE_FAMILY

MON, TUE = "2026-11-02", "2026-11-03"
DIMS = {"scaffold": 1, "steps": 1, "representation": 1, "number_range": 3}


@pytest.fixture
def fam():
    return config.load(EXAMPLE_FAMILY)


@pytest.fixture
def store(tmp_path):
    return Store(root=tmp_path / "data", output_dir=tmp_path / "packets")


def _slots(store, fam, cid="nova", date=MON):
    """The slots plan_child offers a writer, captured through a writer that declines."""
    got = {}

    def spy(**kw):
        got.update(kw)
        raise RuntimeError("declined")

    packet.plan_child(store, fam, fam.child(cid), date, writer=spy)
    return got["slots"], got["info"]


def test_every_format_documents_its_numbers():
    assert set(writer.NUMBERS) == set(GENERATORS) == set(catalog.FORMATS)


def test_generator_uses_the_chosen_numbers_and_computes_the_answer_itself():
    it = GENERATORS["array_to_equation"](Gen(random.Random(1), "3", DIMS, "multiplication", {"numbers": [3, 7]}))
    assert it.answer == "3 × 7 = 21" and it.visual_inventory == {"type": "array", "rows": 3, "cols": 7}
    it.id = "1"
    assert verify.check_item(it) == []
    wp = GENERATORS["mult_word_problem"](Gen(random.Random(1), "3", DIMS, "multiplication",
                                             {"numbers": [4, 6], "who": "Priya", "things": "crayons"}))
    assert "Priya" in wp.prompt and "crayons" in wp.prompt and wp.answer == "24"


def test_numbers_outside_the_childs_range_are_replaced():
    g = Gen(random.Random(1), "3", DIMS, "multiplication", {"numbers": [500, 7]})
    it = GENERATORS["array_to_equation"](g)
    it.id = "1"
    rows = it.visual_inventory["rows"]
    assert 2 <= rows <= g.nmax and it.visual_inventory["cols"] == 7 and verify.check_item(it) == []


@pytest.mark.parametrize("fmt", sorted(GENERATORS))
def test_any_numbers_a_model_sends_still_give_a_verified_item(fmt):
    skill = catalog.FORMATS[fmt].skill
    for seed, nums in enumerate(([0, 0, 0, 0], [1, 1, 1, 1], [9999, 9999, 9999], [7, 3, 2, 5, 4, 6], [2], [])):
        it = GENERATORS[fmt](Gen(random.Random(seed), "3", DIMS, skill, {"numbers": list(nums)}))
        it.id = "1"
        assert verify.check_item(it) == [], (fmt, nums)


def test_clean_keeps_only_choices_the_generators_can_use(store, fam):
    slots, _ = _slots(store, fam)
    target = [s for s in slots if s["role"] == "target"]
    fmt = target[0]["allowed"][0]
    parsed = {"note": "n", "items": [
        {"slot": target[0]["slot"], "format": fmt, "numbers": [3, "7", 4, True, -2, 123456], "who": "Priya",
         "things": "crayons", "why": "slipped on 3 x 4"},
        {"slot": target[1]["slot"], "format": fmt, "numbers": [2, 2], "who": "priya smith", "things": "My Things",
         "why": ""},
        {"slot": target[2]["slot"], "format": fmt, "numbers": [2, 3], "who": "", "things": "", "why": ""},
        {"slot": target[3]["slot"], "format": "essay_question", "numbers": [1], "who": "", "things": "", "why": ""},
        {"slot": target[0]["slot"], "format": fmt, "numbers": [9, 9], "who": "", "things": "", "why": "duplicate"},
        {"slot": 99, "format": fmt, "numbers": [], "who": "", "things": "", "why": ""},
        "nonsense",
    ]}
    g = writer.clean(parsed, slots)
    assert set(g) == {s["slot"] for s in target}
    a, b, c, d = (g[s["slot"]] for s in target)
    assert a == {"format": fmt, "numbers": [3, 4], "chosen": True, "who": "Priya", "things": "crayons",
                 "why": "slipped on 3 x 4"}
    assert b["chosen"] and b["who"] == "" and b["things"] == ""       # free text that is not one word is dropped
    assert c["chosen"] is False and c["format"] == target[2]["default"] and c["numbers"] == []  # third repeat
    assert d["chosen"] is False and d["format"] == target[3]["default"]                          # unknown format
    for junk in ({}, {"items": []}, {"items": [{"slot": 1, "format": "nope", "numbers": []}]}, None):
        with pytest.raises(writer.WriterError):
            writer.clean(junk, slots)


def test_plan_follows_the_writer_but_answers_come_from_the_generators(store, fam):
    child = fam.child("nova")
    slots, _ = _slots(store, fam)

    def fake(*, child, date, slots, info):
        first = next(s for s in slots if "array_to_equation" in s["allowed"])
        return {"note": "Arrays first, because 3 x 4 was a slip.", "model": "test-model", "slots": {
            first["slot"]: {"format": "array_to_equation", "numbers": [3, 4], "who": "", "things": "",
                            "answer": "999", "prompt": "ignore me"}}}

    p = packet.plan_child(store, fam, child, MON, writer=fake)
    assert p.written_by == "model" and p.writer_note.startswith("Arrays first") and p.writer_model == "test-model"
    core = [i for i in p.items if not i.optional]
    assert len(core) == child.item_budget and len(p.items) == len(slots)
    assert any(i.format == "array_to_equation" and i.answer == "3 × 4 = 12" for i in p.items)
    assert all("999" not in i.answer and "ignore me" not in i.prompt for i in p.items)
    assert verify.check_items(core, budget=child.item_budget) == [] and verify.check_items(p.items[-1:]) == []
    assert p.items[-1].optional and p.items[-1].id == "S1"


def test_a_failing_writer_gives_exactly_the_built_in_sheet(store, fam):
    child = fam.child("nova")
    builtin = packet.plan_child(store, fam, child, MON)

    def broken(**kw):
        raise TimeoutError("model timed out")

    fell = packet.plan_child(store, fam, child, MON, writer=broken)
    assert [i.to_dict() for i in fell.items] == [i.to_dict() for i in builtin.items]
    assert fell.written_by == "builtin" and "model timed out" in fell.writer_fallback
    assert builtin.written_by == "builtin" and builtin.writer_fallback == ""
    empty = packet.plan_child(store, fam, child, MON, writer=lambda **kw: {"slots": {}})
    assert [i.to_dict() for i in empty.items] == [i.to_dict() for i in builtin.items]


def test_build_records_who_wrote_it_and_keeps_the_note_off_the_child_page(store, fam):
    def fake(*, child, date, slots, info):
        return {"note": "ZEBRANOTE for the grown-up", "slots": {
            s["slot"]: {"format": s["default"], "numbers": [], "who": "", "things": ""} for s in slots}}

    res = packet.build_packet(store, fam, MON, writer=fake)
    assert res["ok"] and res["written_by"] == {"nova": "model", "pip": "model"}
    folder = Path(res["folder"])
    data = json.loads((folder / "packet.json").read_text(encoding="utf-8"))
    assert data["verification"]["ok"] and data["children"]["nova"]["written_by"] == "model"
    assert "ZEBRANOTE" in (folder / "progression.md").read_text(encoding="utf-8")
    for cid in ("nova", "pip"):
        assert "ZEBRANOTE" not in verify.pdf_text(folder / f"{cid}_practice.pdf")[0]
    again = packet.build_packet(store, fam, MON, writer=lambda **kw: pytest.fail("a made sheet is never rewritten"))
    assert again["reused"] and again["written_by"]["nova"] == "model"


def test_a_model_sheet_that_fails_checks_is_rebuilt_by_the_built_in_writer(store, fam, monkeypatch):
    real, seen = packet._build_into, []

    def flaky(store_, family, date, kids, history_days, existing, writer_=None):
        seen.append(writer_ is not None)
        if writer_ is not None:
            return {"date": date, "ok": False, "error": "verification failed", "files": {}}
        return real(store_, family, date, kids, history_days, existing, None)

    monkeypatch.setattr(packet, "_build_into", flaky)
    res = packet.build_packet(store, fam, MON, writer=lambda **kw: {"slots": {}})
    assert res["ok"] and seen == [True, False] and res["written_by"] == {"nova": "builtin", "pip": "builtin"}


class FakeLlm:
    def __init__(self, parsed=None, fail=None):
        self.parsed, self.fail, self.calls = parsed, fail, []

    def complete_structured(self, **kw):
        self.calls.append(kw)
        if self.fail and (self.fail == "always" or kw.get("task")):
            raise self.fail_exc()
        parsed = self.parsed(kw) if callable(self.parsed) else self.parsed
        return SimpleNamespace(parsed=parsed, text="", model="fake-model")

    def fail_exc(self):
        return type("PluginLlmTrustError", (Exception,), {})("not registered") if self.fail == "trust" \
            else RuntimeError("provider down")


def _echo_defaults(kw):
    payload = json.loads(kw["input"][0]["text"])
    return {"note": "Review first.", "items": [
        {"slot": s["slot"], "format": next(iter(payload["formats"][s["skill"]]))["id"], "numbers": [2, 3],
         "who": "", "things": "", "why": "x"} for s in payload["slots"]]}


def test_request_tells_the_model_what_it_needs_and_nothing_private(store, fam, tmp_path):
    child = fam.child("nova")
    store.add_observation(Observation(child_id="nova", date="2026-10-30", source=str(tmp_path / "secret-photo.jpg"),
                                      lesson="Lesson 3-2", items=[ObservedItem(
                                          prompt="6 x 4", child_answer="26", expected_answer="24", status="slip",
                                          skill="multiplication", format="equation")]))
    packet.build_packet(store, fam, MON)
    store.add_feedback(Feedback(date=MON, child_id="nova", packet_date=MON, item_ratings={"1": "N", "2": "I"},
                                note="rushed the arrays"))
    slots, info = _slots(store, fam, date=TUE)
    req = writer.request(child, TUE, slots, info, store)
    text = json.dumps(req)
    assert req["child"]["grade"] == "3" and req["child"]["latest_homework"]["problems"][0]["child_wrote"] == "26"
    rated = req["child"]["recent_parent_ratings"][0]
    assert rated["parent_note"] == "rushed the arrays" and {"not yet", "on their own"} <= {
        p["parent_rating"] for p in rated["problems"]}
    assert len(req["slots"]) == len(slots) and all(s["max_number"] >= 2 for s in req["slots"])
    for private in ("Nova", "nova", "maple", "secret-photo", str(tmp_path), "answer", "worked"):
        assert private not in text, private
    for s in req["slots"]:
        assert s["skill"] in req["formats"] and req["formats"][s["skill"]]


def test_make_calls_the_writer_task_and_returns_usable_choices(store, fam):
    llm = FakeLlm(parsed=_echo_defaults)
    slots, info = _slots(store, fam)
    out = writer.make(llm, store)(child=fam.child("nova"), date=MON, slots=slots, info=info)
    assert out["model"] == "fake-model" and out["note"] == "Review first." and set(out["slots"]) <= {
        s["slot"] for s in slots}
    call = llm.calls[0]
    assert call["task"] == writer.AUX_TASK and call["schema_name"] == "homework_coach_sheet"
    assert call["json_schema"]["additionalProperties"] is False
    p = packet.plan_child(store, fam, fam.child("nova"), MON, writer=writer.make(llm, store))
    assert p.written_by == "model" and verify.check_items(p.items[:-1], budget=fam.child("nova").item_budget) == []


def test_make_falls_back_to_the_main_model_when_the_task_is_not_registered(store, fam):
    llm = FakeLlm(parsed=_echo_defaults, fail="trust")
    slots, info = _slots(store, fam)
    out = writer.make(llm, store)(child=fam.child("nova"), date=MON, slots=slots, info=info)
    assert out["slots"] and [c.get("task") for c in llm.calls] == [writer.AUX_TASK, None]


def test_unusable_replies_and_provider_errors_become_the_built_in_sheet(store, fam):
    child = fam.child("nova")
    builtin = [i.to_dict() for i in packet.plan_child(store, fam, child, MON).items]
    for llm in (FakeLlm(fail="always"), FakeLlm(parsed={"note": "", "items": []}), FakeLlm(parsed=["x"]), None):
        p = packet.plan_child(store, fam, child, MON, writer=writer.make(llm, store))
        assert [i.to_dict() for i in p.items] == builtin and p.writer_fallback


def test_the_tool_uses_the_model_only_when_the_parent_chose_it(tmp_path, family_file):
    s = {"family_config": str(family_file)}

    def run(llm, date):
        rt = Runtime(get_setting=lambda k, d=None: s.get(k, d), store=Store(root=tmp_path / "data"), llm=llm)
        return rt, json.loads(make_handlers(rt)["homework_coach_generate_packet"]({"date": date}))

    llm = FakeLlm(parsed=_echo_defaults)
    rt, res = run(llm, MON)
    assert res["ok"] and res["written_by"]["nova"] == "builtin" and llm.calls == []
    daily.save_settings(rt.store, {"writer": "model"})
    rt, res = run(llm, TUE)
    assert res["ok"] and res["written_by"] == {"nova": "model"} and len(llm.calls) == 1  # Pip is off on Tuesdays
    rt, res = run(None, "2026-11-04")  # no model connection: the built-in writer, not an error
    assert res["ok"] and res["written_by"]["nova"] == "builtin"
