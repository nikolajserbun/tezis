"""Render the «Тезис» bot avatar locally.

The mark follows docs/02-brand.md: three brass strokes of different lengths
(thesis, argument, conclusion) and the brass period at the lower right.
Run: python scripts/make_avatar.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "assets" / "brand"

SIZE = 512
SCALE = 4
GRAPHITE = "#16161A"
BRASS = "#D3B98C"

BARS = [
    (212, 276, 812, 380),
    (297, 450, 727, 554),
    (382, 624, 642, 728),
]
DOT = (760, 780, 52)


def scaled(value: int) -> int:
    return value * SCALE


def render_png(path: Path) -> None:
    canvas_size = SIZE * SCALE
    image = Image.new("RGB", (canvas_size, canvas_size), GRAPHITE)
    draw = ImageDraw.Draw(image)

    for x0, y0, x1, y1 in BARS:
        draw.rounded_rectangle(
            (scaled(x0), scaled(y0), scaled(x1), scaled(y1)),
            radius=scaled(28),
            fill=BRASS,
        )

    cx, cy, radius = DOT
    draw.ellipse(
        (
            scaled(cx - radius),
            scaled(cy - radius),
            scaled(cx + radius),
            scaled(cy + radius),
        ),
        fill=BRASS,
    )

    image.resize((SIZE, SIZE), Image.Resampling.LANCZOS).save(path, "PNG")
    print(f"Written: {path}")


def render_svg(path: Path) -> None:
    bars = "\n".join(
        f'  <rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" '
        'rx="28" fill="#D3B98C"/>'
        for x0, y0, x1, y1 in BARS
    )
    cx, cy, radius = DOT
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" '
        'width="512" height="512">\n'
        '<rect width="1024" height="1024" fill="#16161A"/>\n'
        f"{bars}\n"
        f'  <circle cx="{cx}" cy="{cy}" r="{radius}" fill="#D3B98C"/>\n'
        "</svg>\n"
    )
    path.write_text(svg, encoding="utf-8")
    print(f"Written: {path}")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    render_png(OUT_DIR / "tezis-avatar.png")
    render_svg(OUT_DIR / "tezis-avatar.svg")


if __name__ == "__main__":
    main()
