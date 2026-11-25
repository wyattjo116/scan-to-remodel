"""Optional: turn a render into a photograph-like picture with an image model, held to the model.

Two steps, both through OpenAI's image-edit endpoint:

  trace    sends the render and its line drawing; the prompt says to treat the line drawing as a
           tracing guide. The size sent is the render's own 8:5, so nothing is squeezed.
  correct  sends a picture made earlier, the render, and the line drawing as thin red lines on a
           transparent sheet; the prompt says to move what is off the red lines back onto them.

    uv run pipeline.py run picture -- trace a-rear-wing-up --view street --style white-cottage --dry-run
    uv run pipeline.py run picture -- trace a-rear-wing-up --view street --style white-cottage \
        --look "white painted brick cottage, standing-seam metal roof, mature garden, overcast light"
    uv run pipeline.py run picture -- correct a-rear-wing-up --view street --base <picture.jpg>

Reads   <variant>/renders/<style>/<view>.jpg and renders/lines/<view>.png; optional --refs photos
Writes  <variant>/pictures/<view>-<step>[-take].jpg and a .json with the prompt, usage and cost

Sent to the outside service: the render, the line drawing, the prompt and any --refs you name.
Nothing else: no address, no names. Use --refs only with photographs you may share. The key is
read from OPENAI_API_KEY and never printed. It costs money per picture, so this is a manual
stage: run it only when the owner asks. --dry-run prints the prompt and sends nothing.

The result is an illustration. Image models move windows and invent details; never use one to
check a design. Run drift_check.py on every picture and look at its overlay.
"""
from __future__ import annotations

import base64
import datetime
import io
import json
import os
import sys
import urllib.error
import urllib.request

import numpy as np
from PIL import Image

import common
import house_geom as G
import keys

ENDPOINT = "https://api.openai.com/v1/images/edits"
DEFAULT_MODEL = os.environ.get("REMODEL_IMAGE_MODEL", "gpt-image-2.6-sunburst")   # models change; pass --model
SIZE = (1536, 960)
STOP_ABOVE = 0.50      # stop if one picture costs more than this many dollars

TRACE = """Image 1 is a plain 3D massing render of a house. Image 2 is a line drawing of exactly
the same view: black lines on white, one line for every edge of the building, its roofs,
windows, doors and posts.
{refs}
Produce a photorealistic photograph of exactly this house from exactly this camera position.
Treat image 2 as a tracing guide: every line in it must still be an edge in the same place in
the photograph. Preserve the exact layout, proportions and perspective.

Keep unchanged: the outline of the building, every roof shape and pitch, the number, size and
position of every window and door, the porches and their posts, and the camera angle and framing.
Do not add or remove windows, doors, dormers, chimneys, storeys or wings.

The look: {look}

You may add: materials and textures on the surfaces that are there, planting, sky, and the
ordinary small details of a real house (gutters, trim, window frames) where they do not change
a shape."""

CORRECT = """Image 1 is a photograph-like picture of a house. Image 2 is the 3D model it must
match. The red lines on the markup layer are the model's edges: roof edges, walls, windows,
doors and posts.

Correct image 1 so that it matches the red lines: move, resize or redraw anything on the house
that is off them, and remove anything on the house that image 2 does not have. {remove}Change
nothing else: keep the materials, colours, light, planting and sky of image 1. Do not draw the
red lines in the result."""

REFS = """Images {first} to {last} are style references only: take materials, colours and mood from
them. Do not copy their shapes, windows, roofs or layout."""


def data_url(im, fmt="PNG"):
    buf = io.BytesIO()
    im.save(buf, fmt, **({"quality": 92} if fmt == "JPEG" else {}))
    return f"data:image/{fmt.lower()};base64," + base64.b64encode(buf.getvalue()).decode()


def red_lines(lines_png, thick):
    ln = np.asarray(Image.open(lines_png).convert("L").resize(SIZE, Image.LANCZOS)) < 140
    if thick > 1:
        from scipy import ndimage
        ln = ndimage.binary_dilation(ln, iterations=thick - 1)
    rgba = np.zeros((*ln.shape, 4), np.uint8)
    rgba[ln] = (255, 0, 0, 255)
    return Image.fromarray(rgba, "RGBA")


def main():
    ap = common.parser(__doc__)
    ap.add_argument("step", choices=["trace", "correct"])
    ap.add_argument("variant")
    ap.add_argument("--view", default="street")
    ap.add_argument("--style", default="massing", help="which render set to send")
    ap.add_argument("--look", default="", help="the materials, colours, planting and light, in words")
    ap.add_argument("--refs", nargs="*", default=[], help="style reference photographs you may share")
    ap.add_argument("--base", help="correct: the picture to correct")
    ap.add_argument("--remove", default="", help="correct: things to take out, in words")
    ap.add_argument("--line-width", type=int, default=2)
    ap.add_argument("--take", default="")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--quality", default="medium")
    ap.add_argument("--env-file")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    pdir, _ = common.project(a)
    (_, _, vdir), = common.targets(pdir, [a.variant])
    render_f, lines_f = vdir / "renders" / a.style / f"{a.view}.jpg", vdir / "renders" / "lines" / f"{a.view}.png"
    for f in (render_f, lines_f):
        if not f.exists():
            sys.exit(f"{f} is missing. Run the render stage for this variant, style and view first.")
    render = Image.open(render_f).convert("RGB").resize(SIZE, Image.LANCZOS)
    stem = f"{a.view}-{a.step}" + (f"-{a.take}" if a.take else "")
    dst = vdir / "pictures" / f"{stem}.jpg"
    dst.parent.mkdir(parents=True, exist_ok=True)
    body = {"model": a.model, "size": f"{SIZE[0]}x{SIZE[1]}", "quality": a.quality, "n": 1, "output_format": "png"}
    record = {"step": a.step, "model": a.model, "variant": a.variant, "view": a.view, "style": a.style}
    if a.step == "trace":
        if not a.look:
            sys.exit("trace needs --look: say the materials, colours, planting and light in words.")
        refs = [Image.open(common.resolve(r)).convert("RGB") for r in a.refs]
        for r in refs:
            r.thumbnail((1024, 1024), Image.LANCZOS)
        prompt = TRACE.format(look=a.look, refs=REFS.format(first=3, last=2 + len(refs)) if refs else "")
        lines = Image.open(lines_f).convert("RGB").resize(SIZE, Image.LANCZOS)
        body["images"] = [{"image_url": data_url(render, "JPEG")}, {"image_url": data_url(lines)}] + \
                         [{"image_url": data_url(r, "JPEG")} for r in refs]
        record["sent"] = [render_f.name, "lines/" + lines_f.name] + [f"style reference {i + 1}" for i in range(len(refs))]
    else:
        if not a.base:
            sys.exit("correct needs --base")
        base = Image.open(common.resolve(a.base)).convert("RGB").resize(SIZE, Image.LANCZOS)
        markup = red_lines(lines_f, a.line_width)
        prompt = CORRECT.format(remove=f"Also remove these, which are not in image 2: {a.remove}. " if a.remove else "")
        body["images"] = [{"image_url": data_url(base, "JPEG")}, {"image_url": data_url(render, "JPEG")}]
        body["markup"] = {"image_url": data_url(markup)}
        record["sent"] = [str(a.base), render_f.name, "lines as red markup"]
    body["prompt"] = prompt
    print(f"{a.step} {a.variant} {a.view}: {len(body['images'])} image(s), {body['size']}, model {a.model} -> {dst}")
    if a.dry_run:
        print("\n--- prompt (nothing was sent)\n" + prompt)
        return
    req = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode(), headers={
        "Authorization": "Bearer " + keys.get("OPENAI_API_KEY", a.env_file), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            res = json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"FAIL  HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:600]}")
    except (urllib.error.URLError, TimeoutError) as e:
        sys.exit(f"FAIL  {e}")
    item = (res.get("data") or [{}])[0]
    if not item.get("b64_json"):
        sys.exit(f"FAIL  no image in the response: {json.dumps(res)[:600]}")
    im = Image.open(io.BytesIO(base64.b64decode(item["b64_json"]))).convert("RGB")
    im.save(dst, quality=93)
    usage = res.get("usage") or {}
    G.dump(dst.with_suffix(".json"), {"note": "AI illustration of a planning study. Not a design check.", **record,
                                      "prompt": prompt, "usage": usage, "returned_size": list(im.size),
                                      "date": datetime.date.today().isoformat()})
    print(f"ok    {dst}  {im.size[0]}x{im.size[1]}  usage {usage or 'not reported'}")
    print("Work out the cost from the usage and the provider's current price page, and report it.")


if __name__ == "__main__":
    main()
