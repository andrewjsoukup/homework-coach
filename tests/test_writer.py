"""Model-written sheets: the model writes the problems; nothing it writes is printed on trust."""
from __future__ import annotations

import json
import random
import re
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
SLOT = {"slot": 1, "role": "target", "skill": "multiplication", "dims": DIMS, "default": "equal_groups",
        "allowed": ["equal_groups", "array_to_equation"]}
NO_PIC = {"type": "", "numbers": []}


def raw(**kw):
    base = {"slot": 1, "kind": "written", "prompt": "A baker fills 4 trays with 6 rolls each, then adds 3 more. How many rolls?",
            "answer_type": "number", "answer": "27", "check": "4 * 6 + 3", "choices": [], "picture": NO_PIC,
            "hint": "Find the rolls on the trays first.", "solution": "4 x 6 = 24, then 24 + 3 = 27.",
            "tip": "Ask what the story wants first.", "format": "", "numbers": [], "who": "", "things": "", "why": "two steps"}
    return {**base, **kw}


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


# -- ready-made formats (the model may still pick one) ---------------------------------------------
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


@pytest.mark.parametrize("fmt", sorted(GENERATORS))
def test_any_numbers_a_model_sends_still_give_a_verified_item(fmt):
    skill = catalog.FORMATS[fmt].skill
    for seed, nums in enumerate(([0, 0, 0, 0], [1, 1, 1, 1], [9999, 9999, 9999], [7, 3, 2, 5, 4, 6], [2], [])):
        it = GENERATORS[fmt](Gen(random.Random(seed), "3", DIMS, skill, {"numbers": list(nums)}))
        it.id = "1"
        assert verify.check_item(it) == [], (fmt, nums)


def test_builtin_choice_keeps_only_what_the_generators_can_use():
    counts: dict[str, int] = {}
    g = writer.builtin_choice({"format": "equal_groups", "numbers": [3, "7", 4, True, -2, 123456], "who": "Priya",
                               "things": "crayons", "why": "slipped on 3 x 4"}, SLOT, counts)
    assert g == {"format": "equal_groups", "numbers": [3, 4], "who": "Priya", "things": "crayons",
                 "why": "slipped on 3 x 4"}
    g = writer.builtin_choice({"format": "equal_groups", "who": "priya smith", "things": "My Things"}, SLOT, counts)
    assert g["who"] == "" and g["things"] == "" and g["numbers"] == []
    assert writer.builtin_choice({"format": "equal_groups"}, SLOT, counts) is None        # third repeat
    assert writer.builtin_choice({"format": "essay_question"}, SLOT, counts) is None      # unknown
    assert writer.builtin_choice({"format": "fact_family"}, SLOT, counts) is None         # not for this slot


# -- one written problem ---------------------------------------------------------------------------
def test_a_number_problem_prints_the_recomputed_answer_and_verifies():
    it = writer.written_item(raw(answer=" 27. "), SLOT, "3")
    it.id = "1"
    assert it.format == "written" and it.answer == "27" and it.spec == {"kind": "free", "type": "number", "check": "4 * 6 + 3"}
    assert it.hint and it.parent_tip == "Ask what the story wants first." and verify.check_item(it) == []
    frac = writer.written_item(raw(prompt="What fraction of 8 equal slices is 6 slices? Use the smallest numbers.",
                                   answer="3/4", check="6/8"), SLOT, "3")
    assert frac.answer == "3/4"
    no_hint = writer.written_item(raw(), {**SLOT, "dims": {**DIMS, "scaffold": 4}}, "3")
    assert no_hint.hint == ""  # hints are for children who still need the scaffold


@pytest.mark.parametrize("change, why", [
    ({"answer": "26"}, "does not match its own arithmetic"),
    ({"check": "__import__('os')"}, "not plain arithmetic"),
    ({"check": ""}, "not plain arithmetic"),
    ({"answer": "27 rolls"}, "not a plain number"),
    ({"answer": "-3", "check": "3 - 6"}, "negative"),
    ({"prompt": "Hi"}, "missing or too long"),
    ({"prompt": "x" * 500}, "missing or too long"),
    ({"prompt": "Count the " + "z" * 40 + " please"}, "too long to print"),
    ({"prompt": "Circle the bigger number: 4 or 7 \u2603"}, "cannot print"),
    ({"answer_type": ""}, "no answer type"),
    ({"picture": {"type": "hexagon", "numbers": [3]}}, "unknown picture"),
    ({"picture": {"type": "array", "numbers": [40, 3]}}, "rows must be"),
])
def test_unsound_written_problems_are_refused(change, why):
    with pytest.raises(writer.WriterError, match=why):
        writer.written_item(raw(**change), SLOT, "3")


def test_the_page_never_trusts_a_changed_answer():
    it = writer.written_item(raw(), SLOT, "3")
    it.id, it.answer = "1", "99"
    assert any("recomputed" in e for e in verify.check_item(it))


def test_choice_and_explain_problems():
    c = writer.written_item(raw(prompt="Which equation matches 3 bags with 5 apples in each bag?", answer_type="choice",
                                answer="b", check="", choices=["A. 3 + 5 = 8", "3 x 5 = 15", "5 - 3 = 2"],
                                solution="Equal groups mean multiply."), SLOT, "3")
    c.id = "1"
    assert c.display == ["A. 3 + 5 = 8", "B. 3 x 5 = 15", "C. 5 - 3 = 2"] and c.answer == "B"
    assert c.worked_solution.startswith("B. 3 x 5 = 15.") and verify.check_item(c) == []
    for bad in ({"answer": "D"}, {"choices": ["one"]}, {"choices": ["same", "Same"]}, {"choices": ["a", "b", "c", "d", "e"]}):
        with pytest.raises(writer.WriterError):
            writer.written_item(raw(**{"answer_type": "choice", "answer": "A", "choices": ["yes", "no"], **bad}), SLOT, "3")
    o = writer.written_item(raw(prompt="Sam says 4 x 6 = 10. Explain his mistake and fix it.", answer_type="open",
                                answer="He added instead of multiplying; 4 x 6 = 24.", check=""), SLOT, "3")
    o.id = "2"
    assert o.answer == "Answers vary" and o.worked_solution.startswith("Look for: He added")
    assert o.spec["box"] and o.work_lines == 3 and verify.check_item(o) == []
    with pytest.raises(writer.WriterError, match="good answer"):
        writer.written_item(raw(answer_type="open", answer="yes", check=""), SLOT, "3")


@pytest.mark.parametrize("ptype, nums, want", [
    ("objects", [7], {"type": "objects", "count": 7}),
    ("ten_frame", [10, 4], {"type": "ten_frame", "filled": [10, 4]}),
    ("two_groups", [3, 5], {"type": "two_groups", "a": 3, "b": 5}),
    ("array", [3, 4], {"type": "array", "rows": 3, "cols": 4}),
    ("groups", [4, 5], {"type": "groups", "groups": 4, "per_group": 5}),
    ("share", [12, 3], {"type": "share", "total": 12, "groups": 3}),
    ("bar", [20, 8, 0], {"type": "bar", "total": 20, "parts": [8, None], "true_total": 20}),
    ("bar", [0, 8, 12], {"type": "bar", "total": None, "parts": [8, 12], "true_total": 20}),
    ("bar_equal", [24, 4], {"type": "bar_equal", "total": 24, "parts": 4}),
    ("fraction_bar", [4, 3], {"type": "fraction_bar", "parts": 4, "shaded": 3}),
    ("set", [8, 2], {"type": "set", "total": 8, "shaded": 2}),
    ("number_line", [0, 20, 2], {"type": "number_line", "lo": 0, "hi": 20, "jump": 2}),
    ("base_ten", [1, 2, 3], {"type": "base_ten", "hundreds": 1, "tens": 2, "ones": 3}),
])
def test_every_picture_the_model_may_ask_for_is_drawn_and_checked(ptype, nums, want, tmp_path, fam):
    from homework_coach import render

    assert writer.picture_inventory(ptype, nums) == want
    it = writer.written_item(raw(picture={"type": ptype, "numbers": nums}), SLOT, "3")
    it.id = "1"
    assert it.visual_inventory == want and verify.check_item(it) == []
    plan = packet.ChildPlan(child=fam.child("nova"), items=[it], target_skill="multiplication",
                            review_skill="add_sub", dims={})
    drawn = render.child_pdf(tmp_path / "p.pdf", plan, MON)
    assert render.check_drawn([it], drawn) == [] and render.visual_description(it)
    assert verify.render_check(tmp_path / "p.pdf")["errors"] == []


def test_every_listed_picture_is_tested_and_bad_pictures_are_refused():
    assert set(writer.PICTURES) == verify.FREE_VISUALS
    for ptype, nums in (("objects", [0]), ("objects", [31]), ("array", [3]), ("bar", [10, 0, 0]), ("bar", [10, 4, 5]),
                        ("bar", [5, 9, 0]), ("fraction_bar", [4, 5]), ("set", [3, 4]), ("number_line", [0, 21, 2]),
                        ("number_line", [0, 500, 2]), ("number_line", [3, 13, 2]), ("base_ten", [0, 0, 0]),
                        ("share", [12, 9])):
        with pytest.raises(writer.WriterError):
            writer.picture_inventory(ptype, nums)


# -- the writer end to end -------------------------------------------------------------------------
class FakeLlm:
    """Writes one sum per slot and checks them the way a second model pass would."""

    def __init__(self, write=None, check=None, fail=None):
        self.write, self.check, self.fail, self.calls = write or write_sums, check or check_sums, fail, []

    def complete_structured(self, **kw):
        self.calls.append(kw)
        if self.fail and (self.fail == "always" or kw.get("task")):
            raise self.fail_exc()
        payload = json.loads(kw["input"][0]["text"])
        fn = self.check if kw["schema_name"] == "homework_coach_check" else self.write
        return SimpleNamespace(parsed=fn(payload), text="", model="fake-model")

    def fail_exc(self):
        return type("PluginLlmTrustError", (Exception,), {})("not registered") if self.fail == "trust" \
            else RuntimeError("provider down")

    def names(self):
        return [c["schema_name"] for c in self.calls]


def write_sums(payload, offset=10):
    return {"note": "Two-step stories, after a slip on 6 x 4.", "items": [
        raw(slot=s["slot"], prompt=f"Problem for slot {s['slot']}: what is {s['slot']} + {offset}?",
            answer=str(s["slot"] + offset), check=f"{s['slot']} + {offset}", hint="", solution="")
        for s in payload["slots"]]}


def check_sums(payload):
    out = []
    for p in payload["problems"]:
        a, b = map(int, re.findall(r"is (\d+) \+ (\d+)", p["prompt"])[0])
        out.append({"slot": p["slot"], "answer": f"The answer is {a + b}", "ok": True, "issue": ""})
    return {"answers": out}


def test_the_model_writes_the_sheet_and_every_answer_is_checked_twice(store, fam):
    llm = FakeLlm()
    child = fam.child("nova")
    p = packet.plan_child(store, fam, child, MON, writer=writer.make(llm, store))
    assert p.written_by == "model" and p.writer_model == "fake-model" and p.writer_note.startswith("Two-step")
    assert p.writer_rejected == [] and llm.names() == ["homework_coach_sheet", "homework_coach_check"]
    assert all(i.format == "written" for i in p.items) and len(p.items) == child.item_budget + 1
    assert p.items[-1].optional and p.items[-1].id == "S1" and p.items[-1].spec.get("box")
    assert verify.check_items(p.items[:-1], budget=child.item_budget) == []
    assert all(c["task"] == writer.AUX_TASK and c["json_schema"]["additionalProperties"] is False for c in llm.calls)
    seen = json.loads(llm.calls[1]["input"][0]["text"])  # the second pass sees only what the child sees
    assert set(seen["problems"][0]) == {"slot", "type", "prompt", "picture", "choices", "hint"}
    assert "answer" not in json.dumps(seen) and "check" not in json.dumps(seen["problems"])


def test_a_written_sheet_builds_verified_pdfs_with_answers_only_on_the_key(store, fam):
    res = packet.build_packet(store, fam, MON, only=["nova"], writer=writer.make(FakeLlm(), store))
    assert res["ok"] and res["written_by"] == {"nova": "model"} and res["verification"]["ok"]
    folder = Path(res["folder"])
    kid = json.loads((folder / "packet.json").read_text(encoding="utf-8"))["children"]["nova"]
    assert all(i["format"] == "written" for i in kid["items"]) and kid["writer_rejected"] == []
    page, key = verify.pdf_text(folder / "nova_practice.pdf")[0], verify.pdf_text(folder / "parent_key.pdf")[0]
    assert "Problem for slot 1" in page and "Two-step stories" not in page
    assert all(f"Answer: {i['answer']}" in key for i in kid["items"])
    assert "written by: your model" in (folder / "progression.md").read_text(encoding="utf-8")


def test_a_problem_the_second_pass_disputes_is_rewritten_once(store, fam):
    rounds = []

    def write(payload):
        rounds.append(payload)
        return write_sums(payload, offset=10 if len(rounds) == 1 else 50)

    def check(payload):
        out = check_sums(payload)
        if len(rounds) == 1:
            out["answers"][0].update(answer="999")                              # a different answer
            out["answers"][1].update(ok=False, issue="two readings are possible")  # ambiguous
        return out

    llm = FakeLlm(write, check)
    p = packet.plan_child(store, fam, fam.child("nova"), MON, writer=writer.make(llm, store))
    assert llm.names() == ["homework_coach_sheet", "homework_coach_check"] * 2
    again = rounds[1]
    assert [s["slot"] for s in again["slots"]] == [1, 2]
    assert len(again["already_on_sheet"]) == len(p.items) - 2 and "Problem for slot 3" in again["already_on_sheet"][0]
    assert again["rewrite"][0]["thrown_away_because"] == "second check worked out 999, not 11"
    assert "two readings are possible" in again["rewrite"][1]["thrown_away_because"]
    assert p.written_by == "model" and p.writer_rejected == [] and all(i.format == "written" for i in p.items)
    assert {"what is 1 + 50?", "what is 2 + 50?"} <= {i.prompt.split(": ")[1] for i in p.items}


def test_a_problem_that_fails_twice_is_replaced_by_a_built_in_one(store, fam):
    def write(payload):
        out = write_sums(payload)
        for it in out["items"]:
            if it["slot"] == 1:
                it["answer"] = "5"   # never matches its own arithmetic
        return out

    child = fam.child("nova")
    p = packet.plan_child(store, fam, child, MON, writer=writer.make(FakeLlm(write), store))
    assert p.written_by == "model" and len(p.writer_rejected) == 1 and "does not match" in p.writer_rejected[0]
    built_in = [i for i in p.items if i.format != "written"]
    assert len(built_in) == 1 and built_in[0].format in catalog.FORMATS
    assert verify.check_items(p.items[:-1], budget=child.item_budget) == []


def test_the_same_problem_twice_on_one_sheet_is_refused(store, fam):
    def write(payload):
        out = write_sums(payload)
        if len(out["items"]) > 2:
            out["items"][1].update(prompt="A different story with the same sum: what is 1 + 10?", answer="11",
                                   check="1+10")
            out["items"][2]["prompt"] = out["items"][3]["prompt"].upper()
            out["items"][2].update(answer=out["items"][3]["answer"], check="0 + " + out["items"][3]["check"])
            out["items"][2], out["items"][3] = out["items"][3], out["items"][2]
        return out

    llm = FakeLlm(write)
    p = packet.plan_child(store, fam, fam.child("nova"), MON, writer=writer.make(llm, store))
    second = json.loads(llm.calls[2]["input"][0]["text"])
    assert [r["thrown_away_because"] for r in second["rewrite"]] == ["it repeats another problem on this sheet"] * 2
    assert len({i.prompt.lower() for i in p.items}) == len(p.items) and p.writer_rejected == []


def test_ready_made_formats_mix_with_written_problems(store, fam):
    def write(payload):
        out = write_sums(payload)
        name = payload["slots"][0]["skill"]
        out["items"][0] = raw(slot=payload["slots"][0]["slot"], kind="builtin", prompt="", answer_type="", answer="",
                              check="", format=payload["formats"][name][0]["id"], numbers=[3, 4])
        return out

    p = packet.plan_child(store, fam, fam.child("nova"), MON, writer=writer.make(FakeLlm(write), store))
    kinds = [i.format for i in p.items]
    assert kinds.count("written") == len(kinds) - 1 and p.writer_rejected == []


def test_the_child_s_name_and_too_many_explain_problems_are_refused(store, fam):
    def write(payload):
        out = write_sums(payload)
        out["items"][0]["prompt"] = "Nova has 1 + 10 stickers. What is 1 + 10?"
        for it in out["items"][1:5]:
            it.update(answer_type="open", answer="Shows the two numbers added together.", check="")
        return out

    p = packet.plan_child(store, fam, fam.child("nova"), MON, writer=writer.make(FakeLlm(write), store))
    opens = [i for i in p.items if i.spec.get("type") == "open"]
    assert len(opens) == writer.MAX_OPEN and all("Nova" not in i.prompt for i in p.items)
    assert any("own name" in r for r in p.writer_rejected) and any("too many explain" in r for r in p.writer_rejected)


def test_request_tells_the_model_what_it_needs_and_nothing_private(store, fam, tmp_path):
    child = fam.child("nova")
    store.add_observation(Observation(child_id="nova", date="2026-10-30", source=str(tmp_path / "secret-photo.jpg"),
                                      lesson="Lesson 3-2", notes="Nova rushed the last page",
                                      items=[ObservedItem(prompt="6 x 4", child_answer="26", expected_answer="24",
                                                          status="slip", skill="multiplication", format="equation")]))
    store.append_brief_section("nova", "Learning brief — Nova", f"Nova and Pip. Photo at {tmp_path / 'secret-photo.jpg'}")
    packet.build_packet(store, fam, MON)
    store.add_feedback(Feedback(date=MON, child_id="nova", packet_date=MON, item_ratings={"1": "N", "2": "I"},
                                note="Nova rushed the arrays"))
    daily.save_settings(store, {"guidance": {"nova": "Two-step stories. Nova loves dinosaurs."}})
    slots, info = _slots(store, fam, date=TUE)
    req = writer.request(child, TUE, slots, info, store)
    text = json.dumps(req)
    kid = req["child"]
    assert kid["grade"] == "3" and kid["latest_homework"]["problems"][0]["child_wrote"] == "26"
    assert kid["latest_homework"]["notes"] == "the child rushed the last page"
    assert kid["parent_guidance"] == "Two-step stories. the child loves dinosaurs."
    assert "the child and a sibling" in kid["learning_brief"] and "[file]" in kid["learning_brief"]
    rated = kid["recent_parent_ratings"][0]
    assert rated["parent_note"] == "the child rushed the arrays" and {"not yet", "on their own"} <= {
        p["parent_rating"] for p in rated["problems"]}
    assert kid["recent_sheets"][0]["sheet"] == MON and kid["recent_sheets"][0]["problems"]
    assert len(req["slots"]) == len(slots) and all(s["max_number"] >= 2 and s["difficulty"]["steps"] >= 1 for s in req["slots"])
    for private in ("Nova", "nova", "Pip", "maple", "secret-photo", str(tmp_path), "worked"):
        assert private not in text, private
    for s in req["slots"]:
        assert s["skill"] in req["formats"] and req["formats"][s["skill"]]
    assert set(req["pictures"]) == set(writer.PICTURES)


def test_make_falls_back_to_the_main_model_when_the_task_is_not_registered(store, fam):
    llm = FakeLlm(fail="trust")
    slots, info = _slots(store, fam)
    out = writer.make(llm, store)(child=fam.child("nova"), date=MON, slots=slots, info=info)
    assert len(out["slots"]) == len(slots)
    assert [c.get("task") for c in llm.calls] == [writer.AUX_TASK, None, writer.AUX_TASK, None]


# -- falling back ----------------------------------------------------------------------------------
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


def test_unusable_replies_a_dead_checker_and_provider_errors_become_the_built_in_sheet(store, fam):
    child = fam.child("nova")
    builtin = [i.to_dict() for i in packet.plan_child(store, fam, child, MON).items]

    def dead_check(payload):
        raise RuntimeError("checker down")

    for llm in (FakeLlm(fail="always"), FakeLlm(lambda p: {"note": "", "items": []}), FakeLlm(lambda p: ["x"]),
                FakeLlm(check=dead_check), FakeLlm(check=lambda p: {"answers": []}), None):
        p = packet.plan_child(store, fam, child, MON, writer=writer.make(llm, store))
        assert [i.to_dict() for i in p.items] == builtin and p.writer_fallback and p.written_by == "builtin"


def test_a_written_problem_is_verified_again_when_the_sheet_is_planned(store, fam):
    def fake(*, child, date, slots, info):
        good = writer.written_item(raw(), slots[0], child.grade)
        bad = writer.written_item(raw(prompt="What is 5 + 5 in this second problem?", answer="10", check="5 + 5"),
                                  slots[1], child.grade)
        bad.answer = "11"  # tampered after the writer's own checks
        return {"note": "", "slots": {slots[0]["slot"]: {"written": good}, slots[1]["slot"]: {"written": bad}}}

    p = packet.plan_child(store, fam, fam.child("nova"), MON, writer=fake)
    assert [i.format for i in p.items].count("written") == 1 and all(i.answer != "11" for i in p.items)
    assert len(p.writer_rejected) == 1 and "recomputed" in p.writer_rejected[0]


def test_a_made_sheet_is_never_rewritten(store, fam):
    first = packet.build_packet(store, fam, MON, writer=writer.make(FakeLlm(), store))
    again = packet.build_packet(store, fam, MON, writer=lambda **kw: pytest.fail("a made sheet is never rewritten"))
    assert first["ok"] and again["reused"] and again["written_by"] == {"nova": "model", "pip": "model"}


def test_a_model_sheet_that_fails_page_checks_is_rebuilt_by_the_built_in_writer(store, fam, monkeypatch):
    real, seen = packet._build_into, []

    def flaky(store_, family, date, kids, history_days, existing, writer_=None):
        seen.append(writer_ is not None)
        if writer_ is not None:
            return {"date": date, "ok": False, "error": "verification failed", "files": {}}
        return real(store_, family, date, kids, history_days, existing, None)

    monkeypatch.setattr(packet, "_build_into", flaky)
    res = packet.build_packet(store, fam, MON, writer=lambda **kw: {"slots": {}})
    assert res["ok"] and seen == [True, False] and res["written_by"] == {"nova": "builtin", "pip": "builtin"}


def test_the_tool_uses_the_model_only_when_the_parent_chose_it(tmp_path, family_file):
    s = {"family_config": str(family_file)}

    def run(llm, date):
        rt = Runtime(get_setting=lambda k, d=None: s.get(k, d), store=Store(root=tmp_path / "data"), llm=llm)
        return rt, json.loads(make_handlers(rt)["homework_coach_generate_packet"]({"date": date}))

    llm = FakeLlm()
    rt, res = run(llm, MON)
    assert res["ok"] and res["written_by"]["nova"] == "builtin" and llm.calls == []
    daily.save_settings(rt.store, {"writer": "model"})
    rt, res = run(llm, TUE)
    assert res["ok"] and res["written_by"] == {"nova": "model"}   # Pip is off on Tuesdays
    assert llm.names() == ["homework_coach_sheet", "homework_coach_check"]
    rt, res = run(None, "2026-11-04")  # no model connection: the built-in writer, not an error
    assert res["ok"] and res["written_by"]["nova"] == "builtin"
