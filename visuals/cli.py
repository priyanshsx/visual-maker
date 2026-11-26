#---------------------beginning-of-code------------------------#
#--------------------------------------------------------------#

# File: visuals/cli.py
# Purpose: the command you run. Your words in, branded images out.
# Usage:
#   Batch file (one entry per image):
#     python -m visuals --client vizcorn --file example.yaml
#       (looks in inputs/<client>/ if the path isn't found as typed)
#   One image straight from the command line:
#     python -m visuals --client vizcorn --template quote --quote "Clean data first." --author "VizCorn"
#     python -m visuals --client vizcorn --template stat --stat "3 in 4" --headline "..." --source "..."
#     python -m visuals --client vizcorn --template carousel --slide "Title" --slide "Point | detail"
#   Options: --size portrait|square|landscape|story (repeat for several), --out <folder>, --html
#            --video (also make slideshow MP4s), --seconds 3.5 (time per slide)
#            --duration 8 (length of stat_motion / quote_motion videos), --music track.mp3
#   Motion:
#     python -m visuals --client vizcorn --template stat_motion --stat "75%" --headline "..."
#     python -m visuals --client vizcorn --template quote_motion --quote "Fix the *data* first."
#   From an idea (LLM writes the YAML for a client's bucket; see visuals/ideas.py):
#     python -m visuals buckets --client quartermaster
#     python -m visuals idea --client quartermaster --bucket feature_launch --files shot.png --idea "..."
#   3D product demo (device_demo, made with Remotion; YAML file only, see inputs/quartermaster/):
#     python -m visuals --client quartermaster --file correlations-demo.yaml
#     add --html to keep a props file for previewing in Remotion Studio
#   Output: outputs/<client>/<today>/
#--------------------------------------------------------------#

# Imports Libraries
import argparse
import sys
import tempfile
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from visuals.brand import load_brand
from visuals.paths import INPUTS_DIR, OUTPUTS_DIR
from visuals.specs import SIZES, TEMPLATES, load_batch, spec_from_dict
#--------------------------------------------------------------#

# Read the command-line arguments
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="visuals", description="Branded images from your words")
    p.add_argument("--client", required=True, help="brand folder name, e.g. vizcorn")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", help="YAML batch file (one entry per image)")
    src.add_argument("--template", choices=TEMPLATES)
    p.add_argument("--name", help="file name for a single image")
    p.add_argument("--quote")
    p.add_argument("--author")
    p.add_argument("--role")
    p.add_argument("--stat")
    p.add_argument("--headline")
    p.add_argument("--body")
    p.add_argument("--source")
    p.add_argument("--title")
    p.add_argument("--kicker")
    p.add_argument("--subtitle")
    p.add_argument("--image", help="title card image (file in inputs/<client>/)")
    p.add_argument("--slide", action="append", help='carousel slide: "Title" or "Title | body"')
    p.add_argument("--size", action="append", choices=list(SIZES),
                   help="output size (default: portrait); repeat for several")
    p.add_argument("--out", help="output folder (default: outputs/<client>/<today>)")
    p.add_argument("--html", action="store_true", help="also save the HTML (for checking designs)")
    p.add_argument("--video", action="store_true", help="also make a slideshow MP4 for every entry")
    p.add_argument("--seconds", type=float, help="seconds per slide in videos (default 3.5)")
    p.add_argument("--music", help="background music file for videos (looked up in inputs/<client>/)")
    p.add_argument("--duration", type=float, help="length of motion videos in seconds (default: auto)")
    return p.parse_args(argv)
#--------------------------------------------------------------#

# Turn validation errors into one plain line per problem, e.g.
#   entry 2 (quote): "qoute" is not a field for this template (typo?)
def friendly_errors(error: ValidationError) -> str:
    lines = []
    for err in error.errors():
        loc = [str(x) for x in err["loc"]]
        prefix = ""
        if loc and loc[0].isdigit():                       # batch file: (index, template, field...)
            prefix = f"entry {int(loc[0]) + 1}"
            loc = loc[1:]
        if loc and loc[0] in TEMPLATES:
            prefix = f"{prefix} ({loc[0]})" if prefix else loc[0]
            loc = loc[1:]
        names = {"slides": "slide", "steps": "step", "focus": "focus value", "cards": "card",
                 "stats": "stat", "points": "point", "scenes": "scene", "overlays": "overlay",
                 "items": "item"}
        field = " ".join(f"{names.get(loc[j - 1], 'item')} {int(x) + 1}" if x.isdigit() and j
                         else f'"{x}"' for j, x in enumerate(loc))
        kind, ctx = err["type"], err.get("ctx", {})
        if kind == "missing":
            msg = f"{field} is missing"
        elif kind == "extra_forbidden":
            msg = f"{field} is not a field for this template (typo?)"
        elif kind == "string_too_long":
            msg = f"{field} is too long (max {ctx.get('max_length')} characters)"
        elif kind == "too_short" and "slides" in field:
            msg = "a carousel needs at least 2 slides"
        elif kind == "too_long" and "slides" in field:
            msg = "a carousel can have at most 12 slides"
        elif kind == "union_tag_invalid":
            msg = "template must be one of: " + ", ".join(TEMPLATES)
        else:
            msg = f"{field} {err['msg']}".strip()
        lines.append(f"  {prefix}: {msg}" if prefix else f"  {msg}")
    return "\n".join(lines)
#--------------------------------------------------------------#

# Find the batch file: as typed, or inside inputs/<client>/
def resolve_file(client: str, file: str) -> Path:
    for candidate in (Path(file), INPUTS_DIR / client / file):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Batch file not found: {file} (also looked in {INPUTS_DIR / client})")
#--------------------------------------------------------------#

# Find an image file: as typed, or inside inputs/<client>/
def resolve_image(client: str, image: str) -> Path:
    for candidate in (Path(image), INPUTS_DIR / client / image):
        if candidate.exists():
            return candidate.resolve()
    raise FileNotFoundError(f"Image not found: {image} (also looked in {INPUTS_DIR / client})")
#--------------------------------------------------------------#

# Find the music file: as typed, or inside inputs/<client>/ (None if no music)
def resolve_music(client: str, music: str | None) -> Path | None:
    if not music:
        return None
    for candidate in (Path(music), INPUTS_DIR / client / music):
        if candidate.exists():
            return candidate
    return INPUTS_DIR / client / music          # missing: make_slideshow gives a clear error
#--------------------------------------------------------------#

# Replace every file name in a spec (screenshots, charts, footage) with its full path, so a
# missing file is reported before anything renders
def resolve_files(client: str, spec):
    def fix(item, field):
        value = getattr(item, field, None)
        return item.model_copy(update={field: str(resolve_image(client, value))}) if value else item
    spec = fix(fix(spec, "image"), "footage")
    for group in ("steps", "scenes", "overlays"):          # device_demo, explainer, talking_head
        if hasattr(spec, group):
            spec = spec.model_copy(update={group: [fix(x, "image") for x in getattr(spec, group)]})
    return spec
#--------------------------------------------------------------#

# Turn the single-image arguments into one spec
def spec_from_args(args: argparse.Namespace):
    data = {"template": args.template}
    if args.name:
        data["name"] = args.name
    if args.size:
        data["sizes"] = args.size
    if args.template in ("device_demo", "event_recap", "explainer", "talking_head"):
        raise ValueError(f"{args.template} has several parts: write it in a YAML file and use --file")
    motion = args.template.endswith("_motion")
    if args.video and not motion:
        data["video"] = True
    if args.seconds and not motion:
        data["seconds_per_slide"] = args.seconds
    if args.duration and motion:
        data["duration"] = args.duration
    if args.music:
        data["music"] = args.music
    if args.template == "carousel":
        slides = []
        for raw in args.slide or []:
            title, _, body = raw.partition("|")
            slides.append({"title": title.strip(), **({"body": body.strip()} if body.strip() else {})})
        data["slides"] = slides
    else:
        for key in ("quote", "author", "role", "stat", "headline", "body", "source",
                    "title", "kicker", "subtitle", "image"):
            value = getattr(args, key)
            if value is not None:
                data[key] = value
    return spec_from_dict(data)
#--------------------------------------------------------------#

# Main: load brand + words, render everything, report what was made
def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in ("idea", "buckets"):          # idea -> spec (LLM), list buckets
        from visuals.ideas import main as ideas_main
        return ideas_main(argv)
    args = parse_args(argv)
    try:
        brand = load_brand(args.client)
        if args.file:
            specs = load_batch(resolve_file(args.client, args.file))
            overrides = {}                                  # command-line options win over the file
            if args.size:
                overrides["sizes"] = args.size
            if args.video:
                overrides["video"] = True
            if args.seconds:
                overrides["seconds_per_slide"] = args.seconds
            if args.music:
                overrides["music"] = args.music
            if args.duration:
                overrides["duration"] = args.duration
            specs = [s.model_copy(update={k: v for k, v in overrides.items()
                                          if k in type(s).model_fields}) for s in specs]
            specs = [type(s).model_validate(s.model_dump()) for s in specs]   # re-check limits
        else:
            specs = [spec_from_args(args)]
        specs = [resolve_files(args.client, s) for s in specs]     # find every file up front
    except ValidationError as e:
        print(f"Your words don't fit the template rules:\n{friendly_errors(e)}", file=sys.stderr)
        return 2
    except (FileNotFoundError, ValueError) as e:
        print(f"Problem: {e}", file=sys.stderr)
        return 2

    from visuals.render import Renderer, TextOverflowError   # imported late: starts a browser
    from visuals.video import VideoError, make_slideshow
    out_dir = Path(args.out) if args.out else OUTPUTS_DIR / args.client / date.today().isoformat()
    made, failed = [], []
    with Renderer() as renderer:
        for i, spec in enumerate(specs, start=1):
            base = spec.name or f"{i:02d}-{spec.template}"
            for size in spec.sizes:
                try:
                    from visuals.remotion_bridge import COMPOSITIONS, render_remotion
                    if spec.template in COMPOSITIONS:      # made with Remotion
                        made += render_remotion(spec, brand, size, out_dir, base,
                                                resolve_music(args.client, getattr(spec, "music", None)),
                                                keep_props=args.html)
                        continue
                    if spec.template.endswith("_motion"):  # animated: MP4 + poster
                        made += renderer.render_motion(spec, brand, size, out_dir, base,
                                                       resolve_music(args.client, getattr(spec, "music", None)),
                                                       keep_html=args.html)
                        continue
                    files = renderer.render(spec, brand, size, out_dir, base, keep_html=args.html)
                    made += files
                    if spec.video:                          # video frames: separate, temporary
                        width, height = SIZES[size]
                        with tempfile.TemporaryDirectory() as tmp:
                            frames = renderer.render(spec, brand, size, Path(tmp), base,
                                                     for_video=True)
                            made.append(make_slideshow(
                                frames, out_dir / f"{base}_{size}.mp4", width, height,
                                spec.seconds_per_slide, resolve_music(args.client, spec.music)))
                except (TextOverflowError, VideoError) as e:
                    failed.append(str(e))

    for path in made:
        print(f"made   {path}")
    for msg in failed:
        print(f"FAILED {msg}", file=sys.stderr)
    print(f"\n{len(made)} file(s) in {out_dir}" + (f", {len(failed)} failed" if failed else ""))
    return 1 if failed else 0
#--------------------------------------------------------------#
#----------------------End-of-code-----------------------------#
