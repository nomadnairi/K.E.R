#!/usr/bin/env python3
"""
Draw the KER application icon.

Kept as code rather than a mystery binary: the mark can be re-rendered at any
size, and a theme change is an edit here instead of a round trip through a
design tool.

The mark is a robot head — a wide visor under a single antenna — because that
silhouette survives being shrunk to 16 px in a taskbar, where a detailed logo
turns to mush. Amber on near-black, matching the app's default palette.

    python scripts/make_icon.py

Writes jarvis/desktop_app/assets/ker.ico (multi-size) and ker.png (512 px).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "jarvis" / "desktop_app" / "assets"
#: Sizes Windows actually asks for, from the taskbar up to the store tile.
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)

BG = (10, 15, 13, 255)          # near-black green, the app background
AMBER = (232, 179, 65, 255)     # the accent
AMBER_HI = (243, 197, 90, 255)
VISOR = (12, 18, 16, 255)
GLOW = (232, 179, 65, 60)


def draw(size: int) -> Image.Image:
    """Render the mark at ``size`` px, drawn 4x and downsampled for clean edges."""
    s = size * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    u = s / 100.0                                  # 1 unit = 1% of the icon

    # Tile: rounded square so the mark keeps a shape of its own on any
    # wallpaper, light or dark.
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(22 * u), fill=BG)

    # Antenna: stalk then bulb, the detail that says "robot" at a glance.
    d.line([(s / 2, 12 * u), (s / 2, 24 * u)], fill=AMBER, width=int(4 * u))
    d.ellipse([s / 2 - 6 * u, 6 * u, s / 2 + 6 * u, 18 * u], fill=AMBER_HI)

    # Head: a wide rounded block, inset from the tile edges.
    head = [16 * u, 26 * u, 84 * u, 84 * u]
    d.rounded_rectangle(head, radius=int(20 * u), fill=AMBER)

    # Visor: one big dark band. This is the shape that reads at 16 px.
    visor = [26 * u, 40 * u, 74 * u, 64 * u]
    d.rounded_rectangle(visor, radius=int(12 * u), fill=VISOR)

    # Eyes: two glints in the visor. They vanish when tiny, which is fine —
    # the visor still carries the silhouette.
    for cx in (40 * u, 60 * u):
        d.ellipse([cx - 5 * u, 47 * u, cx + 5 * u, 57 * u], fill=AMBER_HI)

    # Mouth line: a small grille under the visor.
    d.rounded_rectangle([38 * u, 70 * u, 62 * u, 75 * u],
                        radius=int(2.5 * u), fill=VISOR)

    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    master = draw(512)
    master.save(OUT / "ker.png")
    # Pillow builds the multi-resolution .ico from one image, but rendering
    # each size separately keeps the small ones crisp.
    frames = [draw(n) for n in ICO_SIZES]
    frames[-1].save(OUT / "ker.ico", format="ICO",
                    sizes=[(n, n) for n in ICO_SIZES],
                    append_images=frames[:-1])
    print(f"wrote {OUT / 'ker.ico'} and {OUT / 'ker.png'}")


if __name__ == "__main__":
    main()
