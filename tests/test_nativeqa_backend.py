"""Native-QA backend regressions: PDF preview fallback, photo provenance, progress honesty."""
from __future__ import annotations

import base64
import io
import json
import sys
import types
from pathlib import Path

import pytest

from homework_coach import workspace as ws
from homework_coach.panel import PanelError
from homework_coach.storage import Store
from homework_coach.tools import Runtime


def _rt(tmp_path: Path, family_file: Path) -> Runtime:
    s = {"family_config": str(family_file)}
    return Runtime(get_setting=lambda k, d=None: s.get(k, d), store=Store(root=tmp_path / "data"))


def _pdf_bytes(pages: int = 2) -> bytes:
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for n in range(pages):
        c.drawString(72, 720, f"Nova practice page {n + 1}")
        c.showPage()
    c.save()
    return buf.getvalue()


def _packet(rt: Runtime, date: str, pdf: bytes, extra: dict | None = None) -> Path:
    d = rt.store.packet_dir(date)
    items = [{"id": "1", "skill": "multiplication", "format": "array_to_equation", "prompt": "3 rows of 4",
              "answer": "12", "worked_solution": "4 + 4 + 4 = 12", "role": "target"}]
    child = {"name": "Nova", "focus": "arrays", "items": items, "steered_by": "homework photo",
             "class_unit": "Topic 3: Multiplication Facts", **(extra or {})}
    data = {"date": date, "verification": {"ok": True}, "files": {"nova": "nova_practice.pdf"},
            "children": {"nova": child}}
    (d / "packet.json").write_text(json.dumps(data), encoding="utf-8")
    (d / "nova_practice.pdf").write_bytes(pdf)
    (d / "parent_key.pdf").write_bytes(pdf)
    return d


class _FakeFitz(types.ModuleType):
    """Minimal PyMuPDF surface (open/load_page/rect/get_pixmap/tobytes) that really renders the PDF.

    PyMuPDF is not installed in this venv; the fake draws with pypdfium2 under the hood so the
    preview still comes from the actual file, and records which pages were opened.
    """

    def __init__(self):
        super().__init__("fitz")
        self.opened: list[str] = []
        self.rendered: list[tuple[int, float]] = []
        import pypdfium2 as pdfium

        fake = self

        class Matrix:
            def __init__(self, a, d):
                self.a, self.d = a, d

        class Pix:
            def __init__(self, img):
                self.img = img

            def tobytes(self, fmt="png"):
                b = io.BytesIO()
                self.img.convert("RGB").save(b, "PNG")
                return b.getvalue()

        class Page:
            def __init__(self, pg, n):
                self._pg, self._n = pg, n
                self.rect = types.SimpleNamespace(width=pg.get_width(), height=pg.get_height())

            def get_pixmap(self, matrix=None, alpha=True):
                s = matrix.a if matrix else 1.0
                fake.rendered.append((self._n, s))
                return Pix(self._pg.render(scale=s).to_pil())

        class Doc:
            def __init__(self, path):
                self._d = pdfium.PdfDocument(path)
                self.page_count = len(self._d)

            def __len__(self):
                return self.page_count

            def load_page(self, n):
                if not 0 <= n < self.page_count:
                    raise ValueError("page not in document")
                return Page(self._d[n], n)

            def close(self):
                self._d.close()

        def open_(path):
            fake.opened.append(str(path))
            return Doc(str(path))

        self.Matrix = Matrix
        self.open = open_


@pytest.fixture
def no_pdfium_with_fitz(monkeypatch):
    import pypdfium2  # noqa: F401  (imported before hiding so the fake can use it)

    fake = _FakeFitz()
    monkeypatch.setitem(sys.modules, "pypdfium2", None)  # import pypdfium2 -> ImportError
    monkeypatch.setitem(sys.modules, "fitz", fake)
    return fake


def _png_size(data_url: str) -> tuple[int, int]:
    from PIL import Image

    raw = base64.b64decode(data_url.split(",", 1)[1])
    with Image.open(io.BytesIO(raw)) as im:
        return im.size


# -- PDF preview fallback ------------------------------------------------------------------------
def test_preview_falls_back_to_pymupdf_when_pypdfium2_missing(tmp_path, family_file, no_pdfium_with_fitz):
    rt = _rt(tmp_path, family_file)
    d = _packet(rt, "2026-11-07", _pdf_bytes(2))
    r = ws.packet_preview(rt, "2026-11-07", "nova", page=1, kind="practice", width=600)
    assert r["pages"] == 2 and r["page"] == 1 and not r.get("unavailable")
    assert r["image"].startswith("data:image/png;base64,")
    assert _png_size(r["image"])[0] == 600  # rendered at the requested width
    assert no_pdfium_with_fitz.opened == [str(d / "nova_practice.pdf")]  # the packet's own file
    assert [n for n, _ in no_pdfium_with_fitz.rendered] == [1]


def test_fitz_fallback_keeps_page_validation(tmp_path, family_file, no_pdfium_with_fitz):
    rt = _rt(tmp_path, family_file)
    _packet(rt, "2026-11-07", _pdf_bytes(1))
    with pytest.raises(PanelError, match="does not exist"):
        ws.packet_preview(rt, "2026-11-07", "nova", page=3, kind="practice")
    with pytest.raises(PanelError, match="does not exist"):
        ws.packet_preview(rt, "2026-11-07", "nova", page=-1, kind="practice")
    assert no_pdfium_with_fitz.rendered == []


def test_fitz_fallback_keeps_containment(tmp_path, family_file, no_pdfium_with_fitz):
    rt = _rt(tmp_path, family_file)
    d = _packet(rt, "2026-11-07", _pdf_bytes(1))
    outside = tmp_path / "secret.pdf"
    outside.write_bytes(_pdf_bytes(1))
    data = json.loads((d / "packet.json").read_text(encoding="utf-8"))
    data["files"]["nova"] = str(Path("..") / ".." / ".." / "secret.pdf")
    (d / "packet.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(PanelError, match="not in the packet folder"):
        ws.packet_preview(rt, "2026-11-07", "nova", page=0, kind="practice")
    assert no_pdfium_with_fitz.opened == []


def test_preview_unavailable_only_when_no_renderer(tmp_path, family_file, monkeypatch):
    rt = _rt(tmp_path, family_file)
    _packet(rt, "2026-11-07", _pdf_bytes(1))
    monkeypatch.setitem(sys.modules, "pypdfium2", None)
    monkeypatch.setitem(sys.modules, "fitz", None)
    monkeypatch.setitem(sys.modules, "pymupdf", None)
    r = ws.packet_preview(rt, "2026-11-07", "nova", page=0, kind="practice")
    assert r["unavailable"] and r["image"] is None
    with pytest.raises(PanelError):  # validation still happens before the renderer check
        ws.packet_preview(rt, "2026-11-07", "nova", page=0, kind="../etc")


# -- exact photo provenance --------------------------------------------------------------------
from homework_coach import config as _config  # noqa: E402
from homework_coach import packet as _packet_mod  # noqa: E402
from homework_coach.models import Observation, ObservedItem  # noqa: E402


def _obs(rt: Runtime, date: str, source: str = "", skill: str = "multiplication") -> None:
    rt.store.add_observation(Observation(
        child_id="nova", date=date, source=source, lesson=f"Lesson {date} {source}",
        items=[ObservedItem(prompt="6 x 4", child_answer="24", expected_answer="24", status="correct",
                            skill=skill, format="equation")], skills=[skill]))


def _anchor(rt: Runtime, since: str) -> None:
    rt.store.save_anchor("nova", {"skill": "multiplication", "formats": ["equation"], "since": since,
                                  "lesson": "L", "previous_skill": None})


def test_new_packet_records_the_exact_photo_it_was_built_from(tmp_path, family_file):
    rt = _rt(tmp_path, family_file)
    fam = rt.family()
    _obs(rt, "2026-11-02", "a.png")
    _obs(rt, "2026-11-06", "b.png")
    _obs(rt, "2026-11-12", "future.png")  # dated after the packet: never its source
    _anchor(rt, "2026-11-02")
    res = _packet_mod.build_packet(rt.store, fam, "2026-11-07", only=["nova"])
    assert res["ok"], res
    data = json.loads((Path(res["folder"]) / "packet.json").read_text(encoding="utf-8"))
    rec = data["children"]["nova"]["steering_photo"]
    assert rec["index"] == 1 and rec["date"] == "2026-11-06" and rec["source"] == "b.png"
    # a same-day photo added AFTER the packet was built must not take over its provenance
    _obs(rt, "2026-11-07", "later-same-day.png")
    d = ws.packet_detail(rt, "2026-11-07", "nova")
    assert d["photo_index"] == 1 and d["photo_date"] == "2026-11-06"
    assert d["photo_provenance"] == "recorded"


def test_curriculum_steered_packet_records_no_photo(tmp_path, family_file):
    rt = _rt(tmp_path, family_file)
    fam = rt.family()
    res = _packet_mod.build_packet(rt.store, fam, "2026-11-07", only=["nova"])
    data = json.loads((Path(res["folder"]) / "packet.json").read_text(encoding="utf-8"))
    assert data["children"]["nova"]["steered_by"] == "grade default"
    assert data["children"]["nova"]["steering_photo"] is None
    d = ws.packet_detail(rt, "2026-11-07", "nova")
    assert d["photo_index"] is None and d["photo_provenance"] == "none"


def test_legacy_packet_photo_is_labelled_as_a_best_match(tmp_path, family_file):
    rt = _rt(tmp_path, family_file)
    _obs(rt, "2026-11-02")
    _obs(rt, "2026-11-06")
    _packet(rt, "2026-11-07", _pdf_bytes(1))  # written before provenance was stored
    d = ws.packet_detail(rt, "2026-11-07", "nova")
    assert d["photo_index"] == 1 and d["photo_date"] == "2026-11-06"
    assert d["photo_provenance"] == "inferred"
    assert "best match" in d["photo_label"]


def test_recorded_photo_that_no_longer_matches_is_not_claimed(tmp_path, family_file):
    rt = _rt(tmp_path, family_file)
    _obs(rt, "2026-11-06", "b.png")
    _packet(rt, "2026-11-07", _pdf_bytes(1),
            extra={"steering_photo": {"index": 3, "date": "2026-11-05", "source": "gone.png"}})
    d = ws.packet_detail(rt, "2026-11-07", "nova")
    assert d["photo_index"] is None and d["photo_provenance"] == "missing"
    assert d["photo_date"] == "2026-11-05"  # what was recorded, not a different photo


# -- steering freshness + honest progress wording ---------------------------------------------
from homework_coach import curriculum as _cur  # noqa: E402
from homework_coach import intake as _intake  # noqa: E402
from homework_coach.models import Feedback  # noqa: E402


class _Llm:
    def __init__(self, *responses):
        self.responses = list(responses)

    def complete_structured(self, **kw):
        return types.SimpleNamespace(parsed=self.responses.pop(0) if self.responses
                                     else {"child_answer": "", "confidence": 0})


def _vision(skill="multiplication", conf=0.95):
    return {"lesson": "Lesson 3-2", "main_skill": skill, "items": [
        {"number": "1", "printed_prompt": "6 x 4 = ___", "math_expression": "6 * 4", "child_answer": "24",
         "attempted": True, "skill": skill, "format": "equation", "status": "correct", "confidence": conf}]}


@pytest.fixture
def page(tmp_path) -> Path:
    from PIL import Image

    p = tmp_path / "hw.png"
    Image.new("RGB", (40, 40), "white").save(p)
    return p


def test_same_topic_photo_keeps_practice_steered_by_the_photo(tmp_path, family_file, page):
    rt = _rt(tmp_path, family_file)
    nova = rt.family().child("nova")
    _intake.run_intake(llm=_Llm(_vision()), store=rt.store, child=nova, image_paths=[str(page)], date="2026-10-26")
    _intake.run_intake(llm=_Llm(_vision()), store=rt.store, child=nova, image_paths=[str(page)], date="2026-11-06")
    # 15 days after the topic first appeared, but only 4 days after the newest photo of it
    s = _cur.steer(rt.store, nova, "2026-11-10")
    assert s["source"] == "homework photo" and s["anchor_fresh"]
    a = rt.store.load_anchor("nova")
    assert a["topic_since"] == "2026-10-26" and a["since"] == "2026-11-06"
    assert rt.store.read_brief("nova").count("## Current classroom anchor") == 1


def test_backdated_same_topic_photo_does_not_move_freshness_backwards(tmp_path, family_file, page):
    rt = _rt(tmp_path, family_file)
    nova = rt.family().child("nova")
    _intake.run_intake(llm=_Llm(_vision()), store=rt.store, child=nova, image_paths=[str(page)], date="2026-11-06")
    _intake.run_intake(llm=_Llm(_vision()), store=rt.store, child=nova, image_paths=[str(page)], date="2026-10-20")
    assert rt.store.load_anchor("nova")["since"] == "2026-11-06"


def test_handwriting_confidence_never_moves_difficulty(tmp_path, family_file, page):
    """Photo readings set the topic only; skill levels come from parent ratings alone."""
    rt = _rt(tmp_path, family_file)
    nova = rt.family().child("nova")
    _intake.run_intake(llm=_Llm(_vision(conf=0.2)), store=rt.store, child=nova, image_paths=[str(page)],
                       date="2026-11-06")
    assert rt.store.load_skills("nova") == {}
    plan = _packet_mod.plan_child(rt.store, rt.family(), nova, "2026-11-07")
    assert all(v == 1 for v in plan.dims["multiplication"].values())


def test_first_step_up_is_not_described_as_two_rounds(tmp_path, family_file):
    rt = _rt(tmp_path, family_file)
    _packet(rt, "2026-11-07", _pdf_bytes(1))
    data = json.loads((rt.store.packet_dir("2026-11-07") / "packet.json").read_text(encoding="utf-8"))
    data["children"]["nova"]["items"].append({**data["children"]["nova"]["items"][0], "id": "2"})
    (rt.store.packet_dir("2026-11-07") / "packet.json").write_text(json.dumps(data), encoding="utf-8")
    rt.store.add_feedback(Feedback(date="2026-11-07", child_id="nova", packet_date="2026-11-07",
                                   item_ratings={"1": "I", "2": "I"},
                                   item_skills={"1": "multiplication", "2": "multiplication"}))
    from homework_coach import difficulty

    states, _ = difficulty.replay(rt.store.feedback("nova"))
    rt.store.save_skills("nova", states)
    rt.today = lambda fam=None: "2026-11-08"
    row = next(r for r in ws.progress(rt, "nova")["skills"] if r["skill"] == "multiplication")
    assert row["changes"][0]["change"] == "up"
    assert "two rounds" not in row["changes"][0]["why"]
    assert row["level"] == 1 and row["dims"]["scaffold"] == 2  # one dim moved; overall level honest
