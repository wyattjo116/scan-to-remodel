"""How far has an AI picture drifted from the model? A number and an overlay.

For every pixel of the model's line drawing, find the distance to the nearest strong edge in the
picture. If the picture kept the house where the model has it, each model line has an edge under
it and the distance is near zero.

    uv run pipeline.py run drift -- a-rear-wing-up --view street PICTURE [PICTURE ...]

Prints, per picture, the mean distance in pixels (capped at 25) and the share of line pixels with
an edge within 2 px and within 5 px, at 1536 px width, and writes <picture>-overlay.jpg with the
model's lines in red. The render itself is printed first as the yardstick: nothing scores better.

Read it with care. Busy textures (siding, roof seams, foliage) put edges everywhere and flatter
the number; a smooth picture is marked down. Compare pictures of one view with it, then look at
the overlay: the number does not replace looking.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

import common

W, H = 1536, 960
CAP = 25.0


def edges(im):
    g = np.asarray(im.convert("L").resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(1.2)), dtype=float)
    mag = np.hypot(ndimage.sobel(g, axis=0), ndimage.sobel(g, axis=1))
    return mag > np.percentile(mag, 85)


def main():
    ap = common.parser(__doc__)
    ap.add_argument("variant")
    ap.add_argument("pictures", nargs="+")
    ap.add_argument("--view", required=True)
    ap.add_argument("--style", default="massing")
    a = ap.parse_args()
    pdir, _ = common.project(a)
    (_, _, vdir), = common.targets(pdir, [a.variant])
    lines_f, render_f = vdir / "renders" / "lines" / f"{a.view}.png", vdir / "renders" / a.style / f"{a.view}.jpg"
    if not lines_f.exists() or not render_f.exists():
        sys.exit(f"Need {lines_f} and {render_f}: run the render stage first.")
    lines = np.asarray(Image.open(lines_f).convert("L").resize((W, H), Image.LANCZOS)) < 140
    print(f"{a.view}: {int(lines.sum())} line pixels at {W}x{H}")
    print(f"{'mean px':>8} {'<=2px':>6} {'<=5px':>6}  picture")
    for p in [render_f] + [common.resolve(x) for x in a.pictures]:
        im = Image.open(p).convert("RGB")
        d = np.minimum(ndimage.distance_transform_edt(~edges(im)), CAP)[lines]
        print(f"{d.mean():8.2f} {100 * (d <= 2).mean():5.0f}% {100 * (d <= 5).mean():5.0f}%  {p}")
        if p != render_f:
            big = im.resize((W, H), Image.LANCZOS)
            Image.composite(Image.new("RGB", (W, H), (255, 0, 0)), big, Image.fromarray((lines * 255).astype(np.uint8))) \
                .save(p.with_name(p.stem + "-overlay.jpg"), quality=86)


if __name__ == "__main__":
    main()
