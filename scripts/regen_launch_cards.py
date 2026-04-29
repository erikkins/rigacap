"""
Regenerate launch card PNGs from design/brand/social-launch-cards-v2.html.

For each of the 5 <div class="card"> elements in the V2 HTML, isolates that
card (hides the other four via CSS), renders to a slightly oversize viewport
via headless Chrome, then crops the result to exact 1080×1350 with PIL.

The oversize-then-crop dance is necessary because Chrome's --screenshot at
exact dimensions sometimes clips the bottom of fixed-height content (browser
chrome / scrollbar artifacts / sub-pixel rounding). Rendering at 1080×1450
and cropping to 1080×1350 reliably captures the full card including the
footer (logo + CTA button).

Idempotent — overwrites existing PNGs.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = REPO_ROOT / "design" / "brand" / "social-launch-cards-v2.html"
OUTPUT_DIR = REPO_ROOT / "frontend" / "public" / "launch-cards"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
NUM_CARDS = 5
CARD_W, CARD_H = 1080, 1350
RENDER_W, RENDER_H = 1080, 1450  # oversize viewport — extra 100px guards against bottom clip


def make_isolated_html(source_html: str, card_index: int) -> str:
    """Inject CSS that hides every .card except the Nth (1-indexed), zeroes
    body/html padding+margin, and locks both to exact card dimensions so the
    visible card is anchored to the top-left of the viewport."""
    extra_css = f"""
<style>
  html, body {{
    margin: 0 !important; padding: 0 !important;
    width: {CARD_W}px !important; min-height: {CARD_H}px !important;
    background: #F5F1E8 !important;
    overflow: hidden !important;
  }}
  body {{ display: block !important; gap: 0 !important; }}
  .card {{ display: none !important; }}
  .card:nth-of-type({card_index}) {{ display: block !important; }}
</style>
"""
    return source_html.replace("</head>", extra_css + "</head>")


def render_card(source_html: str, card_index: int, output_path: Path) -> None:
    isolated = make_isolated_html(source_html, card_index)

    with tempfile.NamedTemporaryFile(
        suffix=f"-card-{card_index}.html", delete=False, mode="w", encoding="utf-8"
    ) as tmp:
        tmp.write(isolated)
        tmp_path = tmp.name

    raw_screenshot = output_path.parent / f".launch-{card_index}.raw.png"
    try:
        subprocess.run(
            [
                CHROME,
                "--headless",
                "--disable-gpu",
                "--hide-scrollbars",
                "--force-device-scale-factor=1",
                f"--screenshot={raw_screenshot}",
                f"--window-size={RENDER_W},{RENDER_H}",
                "--default-background-color=F5F1E8",
                f"file://{tmp_path}",
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )
        # Crop the raw screenshot to exact CARD_W × CARD_H from the top-left.
        with Image.open(raw_screenshot) as im:
            cropped = im.crop((0, 0, CARD_W, CARD_H))
            cropped.save(output_path, "PNG", optimize=True)
    finally:
        os.unlink(tmp_path)
        if raw_screenshot.exists():
            os.unlink(raw_screenshot)


def main():
    if not SOURCE.exists():
        raise SystemExit(f"Source HTML not found: {SOURCE}")
    if not Path(CHROME).exists():
        raise SystemExit(f"Chrome not found at: {CHROME}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    source_html = SOURCE.read_text(encoding="utf-8")
    actual = source_html.count('<div class="card">')
    if actual != NUM_CARDS:
        print(f"  WARNING: expected {NUM_CARDS} <div class=\"card\"> elements, found {actual}")

    for i in range(1, NUM_CARDS + 1):
        out = OUTPUT_DIR / f"launch-{i}.png"
        # Render to a tmp first to avoid clobbering on failure
        tmp_out = OUTPUT_DIR / f".launch-{i}.tmp.png"
        render_card(source_html, i, tmp_out)
        shutil.move(str(tmp_out), str(out))
        size_kb = out.stat().st_size / 1024
        print(f"  ✓ launch-{i}.png ({size_kb:.0f} KB)")

    print(f"\nAll {NUM_CARDS} cards regenerated → {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
