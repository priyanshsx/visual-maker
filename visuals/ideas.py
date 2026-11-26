#---------------------beginning-of-code------------------------#
#--------------------------------------------------------------#

# File: visuals/ideas.py
# Purpose: turn a plain-language idea into a ready-to-render YAML spec, following the
#          client's bucket (brands/<client>/buckets.yaml).
#
#   1. picks the bucket, format (video / image) and template
#   2. reads the attached files: images (size), videos (length), CSVs (header + first rows),
#      notes and transcripts (text)
#   3. asks the LLM (fast or smart tier, per bucket) for a spec of that template
#   4. checks it: valid for the template, files exist, every number appears in the sources
#      (problems are sent back to the LLM to fix; anything left is flagged CHECK in the file)
#   5. applies the bucket's defaults and saves inputs/<client>/<name>.yaml for review
#
# Usage:
#   python -m visuals buckets --client quartermaster
#   python -m visuals idea --client quartermaster --bucket feature_launch \
#       --files heatmap.png --idea "Announce the new sector heatmap: ..."
#   python -m visuals idea --client vizcorn --bucket linkedin_image --idea-file post.md
#   options: --format video|image, --template <one of the bucket's>, --model fast|smart,
#            --render (render right after writing the file)
#--------------------------------------------------------------#

# Imports Libraries
import argparse
import csv
import io
import re
import sys
from datetime import date
from pathlib import Path

import yaml
from PIL import Image
from pydantic import ValidationError

from visuals.brand import load_brand
from visuals.buckets import Bucket, get_bucket, load_buckets
from visuals.paths import INPUTS_DIR, ROOT
from visuals.specs import SPEC_CLASSES, spec_from_dict
#--------------------------------------------------------------#

# Global variables
PROMPT_FILE = ROOT / "prompts" / "idea.md"
IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
VIDEO_TYPES = {".mp4", ".mov", ".m4v", ".webm"}
TEXT_TYPES = {".txt", ".md", ".srt", ".vtt", ".json"}
CSV_ROWS = 25                     # rows of each CSV shown to the LLM (all rows count as sources)
TEXT_CHARS = 15000                # characters of each notes / transcript file shown to the LLM
SMALL_NUMBERS = {str(n) for n in range(11)}
# Fields that hold settings or file names, not words: not checked for numbers
NOT_WORDS = {"template", "name", "sizes", "image", "footage", "focus", "zoom", "seconds", "at",
             "start", "end", "duration", "music", "look", "text_style", "kind", "icon", "marker",
             "video", "seconds_per_slide"}
# Which templates cannot be made without an attached file
NEEDS = {"device_demo": "image", "talking_head": "video"}
#--------------------------------------------------------------#

# Read the attached files: what the LLM is shown, and the full text used to check numbers
def describe_files(client: str, names: list[str]) -> tuple[str, str, dict[str, str]]:
    shown, sources, kinds = [], [], {}
    for name in names:
        path = Path(name) if Path(name).exists() else INPUTS_DIR / client / name
        if not path.exists():
            raise FileNotFoundError(f"File not found: {name} (also looked in {INPUTS_DIR / client})")
        ext = path.suffix.lower()
        sources.append(path.name)
        if ext in IMAGE_TYPES:
            kinds[path.name] = "image"
            size = ""
            if ext != ".svg":
                with Image.open(path) as img:
                    size = f", {img.size[0]}x{img.size[1]} px"
            shown.append(f"- {path.name} (image{size})")
        elif ext in VIDEO_TYPES:
            kinds[path.name] = "video"
            from visuals.remotion_bridge import RemotionError, media_seconds
            try:
                length = f", {media_seconds(str(path)):.1f} seconds"
            except RemotionError:
                length = ""
            shown.append(f"- {path.name} (video{length})")
        elif ext == ".csv":
            kinds[path.name] = "data"
            text = path.read_text(encoding="utf-8", errors="replace")
            rows = list(csv.reader(io.StringIO(text)))
            head = "\n".join(",".join(r) for r in rows[:CSV_ROWS + 1])
            more = f"\n... ({len(rows) - 1} rows in total)" if len(rows) > CSV_ROWS + 1 else ""
            shown.append(f"- {path.name} (data):\n```\n{head}{more}\n```")
            sources.append(text)
        elif ext in TEXT_TYPES:
            kinds[path.name] = "text"
            text = path.read_text(encoding="utf-8", errors="replace")
            cut = "\n... (cut)" if len(text) > TEXT_CHARS else ""
            shown.append(f"- {path.name} (notes / transcript):\n```\n{text[:TEXT_CHARS]}{cut}\n```")
            sources.append(text)
        else:
            raise ValueError(f"Can't use {path.name}: attach images, videos, CSVs or text files")
    return "\n".join(shown) or "(none)", "\n".join(sources), kinds
#--------------------------------------------------------------#

# Numbers: "5,000" and "5000" are the same; "57%" counts as 57; "−1" as 1
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def numbers_in(text: str) -> set[str]:
    found = set()
    for raw in _NUMBER.findall(text):
        value = raw.replace(",", "").rstrip(".")
        if "." in value:
            value = value.rstrip("0").rstrip(".") or "0"
        found.add(value)
    return found


def word_fields(data, key: str = "") -> list[str]:
    if key in NOT_WORDS:
        return []
    if isinstance(data, str):
        return [data]
    if isinstance(data, dict):
        return [t for k, v in data.items() for t in word_fields(v, k)]
    if isinstance(data, list):
        return [t for v in data for t in word_fields(v, key)]
    return []


def file_fields(data) -> list[str]:
    if isinstance(data, dict):
        own = [v for k, v in data.items() if k in ("image", "footage") and isinstance(v, str)]
        return own + [f for v in data.values() for f in file_fields(v)]
    if isinstance(data, list):
        return [f for v in data for f in file_fields(v)]
    return []


# Rules checked on every LLM draft (problems go back to the LLM to fix)
def make_check(sources: str, kinds: dict[str, str]):
    allowed = numbers_in(sources) | SMALL_NUMBERS

    def check(spec) -> list[str]:
        data = spec.model_dump(exclude_none=True)
        problems = []
        for name in file_fields(data):
            if name not in kinds:
                problems.append(f'"{name}" is not an attached file (attached: {", ".join(kinds) or "none"})')
        for text in word_fields(data):
            unknown = sorted(numbers_in(text) - allowed)
            if unknown:
                problems.append(f'numbers {", ".join(unknown)} in "{text}" are not in the idea or files: '
                                "remove them or use only numbers from the sources")
        return problems
    return check
#--------------------------------------------------------------#

# Build the prompt from prompts/idea.md (fails loudly if a placeholder is left unfilled)
def build_prompt(brand_name: str, bucket: Bucket, fmt_key: str, template: str, idea: str, files: str) -> str:
    fmt = bucket.formats[fmt_key]
    brief = bucket.brief.strip() + (f"\n{fmt.hint.strip()}" if fmt.hint else "")
    values = {
        "template": template,
        "brand": brand_name,
        "bucket_label": f"{bucket.label} ({fmt_key})",
        "brief": brief,
        "rules": "\n".join(f"- {r}" for r in bucket.rules) or "- (none)",
        "locked": "\n".join(f"- {k}: {v}" for k, v in fmt.defaults.items()) or "- (nothing)",
        "idea": idea.strip(),
        "files": files,
    }
    text = PROMPT_FILE.read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    left = re.findall(r"\{\{\w+\}\}", text)
    if left:
        raise ValueError(f"prompts/idea.md has unfilled placeholders: {', '.join(left)}")
    return text
#--------------------------------------------------------------#

# Pick the format and template: --format / --template, else the bucket's first ones
def choose(bucket: Bucket, fmt: str | None, template: str | None) -> tuple[str, str]:
    fmt = fmt or next(iter(bucket.formats))
    if fmt not in bucket.formats:
        raise ValueError(f"This bucket makes {' / '.join(bucket.formats)}, not {fmt}")
    templates = bucket.formats[fmt].templates
    template = template or templates[0]
    if template not in templates:
        raise ValueError(f"{fmt} in this bucket uses {', '.join(templates)}, not {template}")
    return fmt, template
#--------------------------------------------------------------#

# Save the spec for review, never overwriting an earlier draft
def save_spec(client: str, data: dict, header: list[str]) -> Path:
    folder = INPUTS_DIR / client
    folder.mkdir(parents=True, exist_ok=True)
    base = data.get("name") or f"{data['template']}-{date.today().isoformat()}"
    path, n = folder / f"{base}.yaml", 2
    while path.exists():
        path, n = folder / f"{base}-{n}.yaml", n + 1
    if path.stem != base:
        data["name"] = path.stem                  # outputs get the same name as the file
    body = yaml.safe_dump([data], sort_keys=False, allow_unicode=True, width=100)
    path.write_text("".join(f"# {line}\n" for line in header) + "\n" + body, encoding="utf-8")
    return path
#--------------------------------------------------------------#

# The whole flow: idea -> checked spec -> YAML file. Returns (path, warnings).
def make_spec(client: str, bucket_name: str, idea: str, files: list[str], fmt: str | None = None,
              template: str | None = None, tier: str | None = None) -> tuple[Path, list[str]]:
    from visuals.llm import call_llm
    bucket = get_bucket(client, bucket_name)
    fmt, template = choose(bucket, fmt, template)
    shown, sources, kinds = describe_files(client, files)
    need = NEEDS.get(template)
    if need and need not in kinds.values():
        raise ValueError(f"{template} needs an attached {need} file (use --files)")
    brand = load_brand(client)
    prompt = build_prompt(brand.display_name, bucket, fmt, template, idea, shown)
    spec_class = SPEC_CLASSES[template]
    draft, warnings = call_llm(f"idea:{client}:{bucket_name}:{template}", prompt, spec_class,
                               tier or bucket.model, make_check(idea + "\n" + sources, kinds))

    data = draft.model_dump(exclude_none=True)
    data.update(bucket.formats[fmt].defaults)               # bucket settings always win
    data["template"] = template
    spec_from_dict(data)                                    # still valid after the defaults?
    header = [f"Draft from the idea command, {date.today().isoformat()}: review before rendering.",
              f"Client: {client} | bucket: {bucket_name} ({bucket.label}) | {fmt} | template: {template}",
              f"Idea: {' '.join(idea.split())[:300]}"]
    if bucket.status_note():
        header.append("NOTE: " + " ".join(bucket.status_note().split()))
    header += [f"CHECK: {w}" for w in warnings]
    path = save_spec(client, data, header)
    return path, warnings
#--------------------------------------------------------------#

# Command line: "python -m visuals idea ..." and "python -m visuals buckets ..."
def list_buckets(client: str) -> int:
    buckets = load_buckets(client)
    if not buckets:
        print(f"No buckets for {client} yet (add brands/{client}/buckets.yaml)")
        return 1
    for name, b in buckets.items():
        formats = "; ".join(f"{k}: {', '.join(f.templates)}" for k, f in b.formats.items())
        print(f"{name:18} {b.label}  [{b.status}, {b.model} model]\n{'':18} {formats}")
    return 0


def main(argv: list[str]) -> int:
    command, argv = argv[0], argv[1:]
    p = argparse.ArgumentParser(prog=f"visuals {command}")
    p.add_argument("--client", required=True)
    if command == "buckets":
        return list_buckets(p.parse_args(argv).client)
    p.add_argument("--bucket", required=True)
    p.add_argument("--idea", help="the idea in plain words, in quotes (or use --idea-file)")
    p.add_argument("--idea-file", help="read the idea from a text file (e.g. a LinkedIn post)")
    p.add_argument("--files", nargs="*", default=[], help="screenshots, charts, CSVs, notes, footage, transcripts")
    p.add_argument("--format", choices=["video", "image"])
    p.add_argument("--template")
    p.add_argument("--model", choices=["fast", "smart"], help="override the bucket's LLM tier")
    p.add_argument("--render", action="store_true", help="render straight after writing the file")
    args = p.parse_args(argv)

    idea = Path(args.idea_file).read_text(encoding="utf-8") if args.idea_file else args.idea
    if not idea:
        print('Give the idea with --idea "..." or --idea-file', file=sys.stderr)
        return 2
    from visuals.llm import LLMError
    try:
        path, warnings = make_spec(args.client, args.bucket, idea, args.files,
                                   args.format, args.template, args.model)
    except ValidationError as e:
        print(f"The draft does not fit the template after the bucket defaults:\n{e}", file=sys.stderr)
        return 2
    except (FileNotFoundError, ValueError, LLMError) as e:
        print(f"Problem: {e}", file=sys.stderr)
        return 2
    print(f"Wrote  {path}")
    for w in warnings:
        print(f"CHECK  {w}")
    if args.render:
        from visuals.cli import main as render
        return render(["--client", args.client, "--file", str(path)])
    print(f"Review it, then: python -m visuals --client {args.client} --file {path.name}")
    return 0
#--------------------------------------------------------------#
#----------------------End-of-code-----------------------------#
