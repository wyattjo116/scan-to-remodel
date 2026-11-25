---
name: render-pictures
description: Make pictures of the existing house or a variant - Cycles renders in a chosen finish set, line drawings, and optional AI photograph-like pictures held to the model, with a drift check. Use when someone asks what a variant would look like, for renders, a different material or colour, a street or rear view, an AI or photorealistic picture, or when an AI picture has moved windows, roofs or doors.
---

# Render

## 1. Renders from the model (free, local)

```bash
uv run pipeline.py run render -- <id> --style white-cottage                      # all views, about 5 minutes on a CPU
uv run pipeline.py run render -- <id> --style sage --views street rear --quick   # half size, under a minute
```

- Views: `street`, `rear`, `aerial`, and `cutaway-<level>` for each floor. Output: `variants/<id>/renders/<style>/<view>.jpg` at 1600 x 1000, and `renders/lines/<view>.png`, the same view as black lines on white.
- Styles live in `scripts/styles.json`: `massing` (kept walls cream, new walls blue; the one to use when discussing what changes), `white-cottage`, `sage`, `old-front-new-back`. To try a new look, add a palette to `<project>/styles.json` (colours by role, 0 to 1) and pass its name. A style only recolours; it never changes the model.
- Needs `house.blend`: run the `model` stage first, and again after any change to `variant.json`.
- Look at every picture with the Read tool before showing it. Check gable ends and roof junctions at full size, not as thumbnails.

Long batches (every variant, every style) take tens of minutes on a CPU. Say how long before starting, and render only the views that were asked for.

## 2. AI pictures (optional, paid, manual)

A render is a massing model: flat colours, no texture. An image model can turn it into something that looks like a photograph. It will also move windows and invent dormers if allowed to. The route here holds it to the model:

```bash
uv run pipeline.py run picture -- trace <id> --view street --style white-cottage \
    --look "white painted brick cottage, grey standing-seam metal roof, timber front door, mature garden, soft overcast light" --dry-run
```

1. **Ask first.** It costs money per picture and sends images to an outside service. Run it only when the owner asks, and say roughly what it will cost from the provider's current prices.
2. **Dry run.** `--dry-run` prints the prompt and sends nothing. Show the owner the `--look` wording.
3. **Trace.** Without `--dry-run` it sends the render and its line drawing at the render's own 8:5 size and saves `variants/<id>/pictures/<view>-trace.jpg` with a `.json` of the prompt and usage.
4. **Check drift.** `uv run pipeline.py run drift -- <id> --view street --style white-cottage variants/.../street-trace.jpg`. It prints how far the model's lines are from edges in the picture and writes `-overlay.jpg` with the lines in red. Open the overlay and look: every window, door, roof edge and post should sit under a red line.
5. **Correct only what is wrong.** `picture -- correct <id> --view street --base <picture> --remove "the dormer on the front roof"` redraws against the red lines. Use it for specific faults; a second full redraw usually drifts more, not less.
6. **Report with every picture**: the drift numbers, what is still wrong in it, and what it cost.

What may be sent: the render, the line drawing, the look in words, and reference photographs the owner has the right to share (`--refs`, cropped to the photograph, no captions or account names). Never the address, names, the budget or listing photos. The key comes from `OPENAI_API_KEY` (see the `setup` skill); never print it. The default model name in `scripts/image_pass.py` goes out of date: check the provider's current image-edit model and pass `--model`.

**AI pictures are illustrations.** They are for mood and materials. Never use one to check a design, count windows or judge a proportion; use the render and the plan for that. Say so wherever one is shown.

## 3. Showing pictures

- Put the render and the AI picture of the same view side by side, with the plan near them.
- On any page with pictures, each one opens at full resolution on click and closes with Escape, a click outside, or a close button.
- Keep other people's photographs (listing photos, reference stills) out of git and off public pages.

Next: the `remodel-loop` skill reviews the variant with the owner and decides what happens to it.
