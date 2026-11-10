# /// script
# requires-python = ">=3.11"
# dependencies = ["pypdfium2>=4,<6", "pillow>=10,<13"]
# ///
"""Render README screenshots from the fictional demo's real packet PDFs.

    python demo/run_demo.py --out demo/out --keep
    python demo/make_screenshots.py            # writes docs/screenshots/*.png

Every image comes from demo output (synthetic Maple family). No real child's work.
"""
from __future__ import annotations

from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PACKETS = ROOT / "demo" / "out" / "data" / "packets"
OUT = ROOT / "docs" / "screenshots"

PAGES = [
    ("2026-09-14/nova_practice.pdf", "02-child-packet-nova.png"),
    ("2026-09-14/parent_key.pdf", "03-parent-key.png"),
    ("2026-09-14/pip_practice.pdf", "04-child-packet-pip-k.png"),
    ("2026-09-16/nova_practice.pdf", "05-adapted-packet-nova-wed.png"),
]


def first_page(pdf: Path, scale: float = 1.6) -> Image.Image:
    doc = pdfium.PdfDocument(str(pdf))
    return doc[0].render(scale=scale).to_pil().convert("RGB")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for src, dst in PAGES:
        first_page(PACKETS / src).save(OUT / dst, optimize=True)
    hw = Image.open(ROOT / "demo" / "homework" / "nova_2026-09-14_arrays.png").convert("RGB")
    hw.thumbnail((1400, 1400))
    hw.save(OUT / "01-homework-photo.png", optimize=True)

    # 2:1 catalog banner: homework photo -> child packet -> parent key
    w, h = 1200, 600
    banner = Image.new("RGB", (w, h), (246, 244, 238))
    for k, img in enumerate([hw, Image.open(OUT / PAGES[0][1]), Image.open(OUT / PAGES[1][1])]):
        t = img.copy()
        t.thumbnail((360, 540))
        banner.paste(t, (30 + k * 390 + (360 - t.width) // 2, (h - t.height) // 2))
    banner.save(OUT / "flow.png", optimize=True)
    print(f"wrote {len(PAGES) + 2} images to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
