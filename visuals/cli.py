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
#   Options: --size portrait|square|landscape (repeat for several), --out <folder>, --html
#   Output: outputs/<client>/<today>/
#--------------------------------------------------------------#

# Imports Libraries
import argparse
import sys
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from visuals.brand import load_brand
from visuals.paths import INPUTS_DIR, OUTPUTS_DIR
from visuals.specs import SIZES, load_batch, spec_from_dict
#--------------------------------------------------------------#

# Read the command-line arguments
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="visuals", description="Branded images from your words")
    p.add_argument("--client", required=True, help="brand folder name, e.g. vizcorn")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", help="YAML batch file (one entry per image)")
    src.add_argument("--template", choices=["quote", "stat", "carousel"])
    p.add_argument("--name", help="file name for a single image")
    p.add_argument("--quote")
    p.add_argument("--author")
    p.add_argument("--role")
    p.add_argument("--stat")
    p.add_argument("--headline")
    p.add_argument("--body")
    p.add_argument("--source")
    p.add_argument("--slide", action="append", help='carousel slide: "Title" or "Title | body"')
    p.add_argument("--size", action="append", choices=list(SIZES),
                   help="output size (default: portrait); repeat for several")
    p.add_argument("--out", help="output folder (default: outputs/<client>/<today>)")
    p.add_argument("--html", action="store_true", help="also save the HTML (for checking designs)")
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
        if loc and loc[0] in ("quote", "stat", "carousel"):
            prefix = f"{prefix} ({loc[0]})" if prefix else loc[0]
            loc = loc[1:]
        field = " ".join(f"slide {int(x) + 1}" if x.isdigit() else f'"{x}"' for x in loc)
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
            msg = "template must be one of: quote, stat, carousel"
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

# Turn the single-image arguments into one spec
def spec_from_args(args: argparse.Namespace):
    data = {"template": args.template}
    if args.name:
        data["name"] = args.name
    if args.size:
        data["sizes"] = args.size
    if args.template == "carousel":
        slides = []
        for raw in args.slide or []:
            title, _, body = raw.partition("|")
            slides.append({"title": title.strip(), **({"body": body.strip()} if body.strip() else {})})
        data["slides"] = slides
    else:
        for key in ("quote", "author", "role", "stat", "headline", "body", "source"):
            value = getattr(args, key)
            if value is not None:
                data[key] = value
    return spec_from_dict(data)
#--------------------------------------------------------------#

# Main: load brand + words, render everything, report what was made
def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        brand = load_brand(args.client)
        if args.file:
            specs = load_batch(resolve_file(args.client, args.file))
            if args.size:                                   # --size overrides the file
                specs = [s.model_copy(update={"sizes": args.size}) for s in specs]
        else:
            specs = [spec_from_args(args)]
    except ValidationError as e:
        print(f"Your words don't fit the template rules:\n{friendly_errors(e)}", file=sys.stderr)
        return 2
    except (FileNotFoundError, ValueError) as e:
        print(f"Problem: {e}", file=sys.stderr)
        return 2

    from visuals.render import Renderer, TextOverflowError   # imported late: starts a browser
    out_dir = Path(args.out) if args.out else OUTPUTS_DIR / args.client / date.today().isoformat()
    made, failed = [], []
    with Renderer() as renderer:
        for i, spec in enumerate(specs, start=1):
            base = spec.name or f"{i:02d}-{spec.template}"
            for size in spec.sizes:
                try:
                    made += renderer.render(spec, brand, size, out_dir, base, keep_html=args.html)
                except TextOverflowError as e:
                    failed.append(str(e))

    for path in made:
        print(f"made   {path}")
    for msg in failed:
        print(f"FAILED {msg}", file=sys.stderr)
    print(f"\n{len(made)} file(s) in {out_dir}" + (f", {len(failed)} failed" if failed else ""))
    return 1 if failed else 0
#--------------------------------------------------------------#
#----------------------End-of-code-----------------------------#
