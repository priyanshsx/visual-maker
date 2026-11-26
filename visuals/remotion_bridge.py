#---------------------beginning-of-code------------------------#
#--------------------------------------------------------------#

# File: visuals/remotion_bridge.py
# Purpose: render the 3D templates (device_demo) with Remotion, the React video tool in
#          remotion/. Python turns the brand + YAML entry into JSON "props", runs
#          `npx remotion render`, adds music with FFmpeg if asked, and saves a poster PNG.
#
#          One-time setup on a new machine:  cd remotion && npm install
#          Preview and fine-tune in the browser (run with --html to keep the props file):
#            cd remotion && npx remotion studio src/index.ts --props=<file>.props.json
#--------------------------------------------------------------#

# Imports Libraries
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image

from visuals.brand import Brand, font_face_css
from visuals.paths import ROOT
from visuals.render import image_data_uri
from visuals.specs import (DEMO_INTRO, DEMO_MIN_STEP, DEMO_OUTRO, DEMO_STEP, SIZES, scene_seconds,
                           scene_total)
from visuals.video import AUDIO_ARGS, VideoError, audio_filter, even, ffmpeg_path
#--------------------------------------------------------------#

# Global variables
load_dotenv(ROOT / ".env")        # VISUALS_CHROME, VISUALS_GL, VISUALS_CONCURRENCY can live in .env
REMOTION_DIR = ROOT / "remotion"
ENTRY = "src/index.ts"
FPS = 30
INTRO_SECONDS, STEP_SECONDS, OUTRO_SECONDS = DEMO_INTRO, DEMO_STEP, DEMO_OUTRO
COMPOSITIONS = {"device_demo": "DeviceDemo", "event_recap": "EventRecap",
                "explainer": "Explainer", "talking_head": "TalkingHead"}
RECAP_SECONDS = 5.0              # animated event_recap; the image is its last frame
#--------------------------------------------------------------#

class RemotionError(VideoError):
    """Remotion is missing or the render failed (shown as FAILED by the CLI)."""
#--------------------------------------------------------------#

# How long each step lasts: 3s by default, or stretched/squeezed to fit `duration`
# (the spec already checked that every step gets at least DEMO_MIN_STEP seconds)
def step_seconds(spec) -> float:
    if spec.duration is None:
        return STEP_SECONDS
    seconds = (spec.duration - INTRO_SECONDS - OUTRO_SECONDS) / len(spec.steps)
    return round(max(seconds, DEMO_MIN_STEP), 3)


def total_seconds(spec) -> float:
    return INTRO_SECONDS + OUTRO_SECONDS + step_seconds(spec) * len(spec.steps)
#--------------------------------------------------------------#

# Brand settings in the shape the React code expects (remotion/src/types.ts)
def brand_props(brand: Brand) -> dict:
    return {
        "name": brand.display_name,
        "handle": brand.handle or brand.website,
        "footer": brand.footer,
        "logo": brand.logo_data_uri,
        "logoWithName": brand.logo_with_name,
        "fontFamily": brand.font.family,
        "fontCss": font_face_css(brand),
        "colors": brand.colors.model_dump(),
    }


def image_props(path: str) -> dict:
    with Image.open(path) as img:
        width, height = img.size
    return {"src": image_data_uri(path), "aspect": round(width / height, 5)}


# Props for an event_recap (remotion/src/types.ts: EventRecapProps)
def recap_props(spec, brand: Brand, size: str) -> dict:
    width, height = SIZES[size]
    bp = spec.big_picture
    return {
        "width": even(width),
        "height": even(height),
        "brand": brand_props(brand),
        "badge": spec.badge,
        "title": spec.title,
        "titleAccent": spec.title_accent,
        "intro": spec.intro,
        "stats": [s.model_dump() for s in spec.stats],
        "cardsLabel": spec.cards_label,
        "cards": [c.model_dump() for c in spec.cards],
        "bigPicture": {"label": bp.label, "title": bp.title, "pointsLabel": bp.points_label,
                       "points": [pt.model_dump() for pt in bp.points]},
        "closing": spec.closing,
        "seconds": RECAP_SECONDS,
    }


# Props for an explainer: each scene with its length in frames; chart images embedded
def explainer_props(spec, brand: Brand, size: str) -> dict:
    width, height = SIZES[size]
    scenes = []
    for scene in spec.scenes:
        data = scene.model_dump(exclude={"seconds"})
        if scene.kind == "chart":
            data["image"] = image_props(scene.image)
            data["focus"] = list(scene.focus)
        data["frames"] = round(scene_seconds(scene) * FPS)
        scenes.append(data)
    return {"width": even(width), "height": even(height), "brand": brand_props(brand),
            "look": spec.look, "scenes": scenes}


# Length of a video file in seconds (ffprobe comes with FFmpeg)
def media_seconds(path: str) -> float:
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        raise RemotionError("ffprobe is missing (it comes with FFmpeg). Mac: brew install ffmpeg")
    result = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration",
                             "-of", "csv=p=0", path], capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        raise RemotionError(f"Could not read the length of {path}: {result.stderr.strip()[-300:]}")


# Props for a talking head. Overlay times ("at") are seconds in the ORIGINAL footage, so they
# match a transcript's timestamps even when start/end trim the video.
def talking_head_props(spec, brand: Brand, size: str) -> dict:
    width, height = SIZES[size]
    end = spec.end if spec.end is not None else media_seconds(spec.footage)
    overlays = []
    for o in spec.overlays:
        if o.at < spec.start or o.at + o.seconds > end + 0.01:
            raise RemotionError(f"overlay at {o.at}s is outside the video ({spec.start}s to {end:.1f}s)")
        data = o.model_dump(exclude={"at", "seconds"})
        if o.kind == "chart":
            data["image"] = image_props(o.image)
        data["from"] = round((o.at - spec.start) * FPS)
        data["frames"] = round(o.seconds * FPS)
        overlays.append(data)
    return {"width": even(width), "height": even(height), "brand": brand_props(brand),
            "footage": Path(spec.footage).name, "startFrame": round(spec.start * FPS),
            "durationFrames": round((end - spec.start) * FPS), "overlays": overlays}


# Everything the composition needs for one size
def build_props(spec, brand: Brand, size: str) -> dict:
    if spec.template == "event_recap":
        return recap_props(spec, brand, size)
    if spec.template == "explainer":
        return explainer_props(spec, brand, size)
    if spec.template == "talking_head":
        return talking_head_props(spec, brand, size)
    width, height = SIZES[size]
    images = [spec.image] + [s.image for s in spec.steps if s.image and s.image != spec.image]
    images = list(dict.fromkeys(images))                  # unique, main screenshot first
    return {
        "look": spec.look,
        "textStyle": spec.text_style,
        "width": even(width),
        "height": even(height),
        "brand": brand_props(brand),
        "kicker": spec.kicker,
        "title": spec.title,
        "cta": spec.cta,
        "images": [image_props(path) for path in images],
        "steps": [{
            "image": images.index(step.image or spec.image),
            "caption": step.caption,
            "focus": list(step.focus),
            "zoom": step.zoom,
            "marker": step.marker,
        } for step in spec.steps],
        "introSeconds": INTRO_SECONDS,
        "stepSeconds": step_seconds(spec),
        "outroSeconds": OUTRO_SECONDS,
    }
#--------------------------------------------------------------#

# The npx command, with a clear message if Node.js or the packages are missing
def npx_path() -> str:
    path = shutil.which("npx")
    if path is None:
        raise RemotionError("Node.js is not installed (needed for 3D videos). Mac: brew install node")
    if not (REMOTION_DIR / "node_modules" / "remotion").exists():
        raise RemotionError(f"Remotion is not installed yet. Run once: cd {REMOTION_DIR} && npm install")
    return path


# Templates with live 3D: each parallel browser tab holds its own 3D scene, so too many at
# once can run the graphics memory out and crash the browser. Others use Remotion's default.
HEAVY_3D = {"device_demo", "event_recap"}


# Extra flags: WebGL backend (Mac GPU by default, software on Linux), how many frames render
# in parallel (VISUALS_CONCURRENCY, default 2 for 3D templates) and an optional browser
def render_flags(template: str | None = None) -> list[str]:
    gl = os.environ.get("VISUALS_GL") or ("angle" if sys.platform == "darwin" else "swangle")
    flags = [f"--gl={gl}", "--log=error"]
    concurrency = os.environ.get("VISUALS_CONCURRENCY") or ("2" if template in HEAVY_3D else None)
    if concurrency:
        flags.append(f"--concurrency={concurrency}")
    browser = os.environ.get("VISUALS_CHROME")             # only if Remotion can't download its own
    if browser:
        flags.append(f"--browser-executable={browser}")
    return flags


# Show the useful part of a failure: the first lines (the actual error), not just the stack trace
def error_summary(output: str) -> str:
    lines = [ln for ln in output.strip().splitlines() if ln.strip()]
    trace = [i for i, ln in enumerate(lines) if ln.lstrip().startswith("at ")]
    head = lines[:trace[0]] if trace else lines
    text = "\n".join(head[-25:]) or "\n".join(lines[:25])
    return text[-2500:]


def run(cmd: list[str], what: str) -> None:
    result = subprocess.run(cmd, cwd=REMOTION_DIR, capture_output=True, text=True)
    if result.returncode != 0:
        detail = error_summary("\n".join(x for x in (result.stdout, result.stderr) if x))
        raise RemotionError(f"{what} failed:\n{detail}")
#--------------------------------------------------------------#

# Add background music to a finished video (trimmed, faded in and out)
def add_music(video: Path, music: Path, length: float, out_path: Path) -> None:
    if not music.exists():
        raise RemotionError(f"Music file not found: {music}")
    cmd = [ffmpeg_path(), "-y", "-loglevel", "error", "-i", str(video), "-i", str(music),
           "-filter_complex", f"[1:a]{audio_filter(length)}[a]", "-map", "0:v", "-map", "[a]",
           "-c:v", "copy", *AUDIO_ARGS, "-t", f"{length:.3f}", "-movflags", "+faststart",
           str(out_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RemotionError(f"Adding music failed: {result.stderr.strip()[-500:]}")
#--------------------------------------------------------------#

# Video length (seconds) and which frame becomes the poster PNG
def timing(spec, props: dict) -> tuple[float, int]:
    if spec.template == "explainer":
        first = props["scenes"][0]["frames"]
        return scene_total(spec.scenes), max(first - 12, 0)        # the opening line, fully shown
    if spec.template == "talking_head":
        frames = props["durationFrames"]
        first = props["overlays"][0] if props["overlays"] else None
        return frames / FPS, (first["from"] + first["frames"] // 2) if first else 0
    return total_seconds(spec), round(total_seconds(spec) * FPS) - 1   # device_demo: closing frame
#--------------------------------------------------------------#

# Image templates: a sharp PNG at twice the size (the last frame), plus an MP4 if asked
def render_image(npx: str, composition: str, props: dict, spec, out_dir: Path, base_name: str,
                 size: str, keep_props: bool) -> list[Path]:
    image = out_dir / f"{base_name}_{size}.png"
    last_frame = round(RECAP_SECONDS * FPS) - 1
    with tempfile.TemporaryDirectory() as tmp:
        props_file = Path(tmp) / "props.json"
        props_file.write_text(json.dumps(props), encoding="utf-8")
        flags = [f"--props={props_file}", *render_flags(spec.template)]
        run([npx, "remotion", "still", ENTRY, composition, str(image), f"--frame={last_frame}",
             "--scale=2", *flags], "Remotion image")
        made = [image]
        if spec.video:
            video = out_dir / f"{base_name}_{size}.mp4"
            run([npx, "remotion", "render", ENTRY, composition, str(video), *flags], "Remotion render")
            made.append(video)
        if keep_props:
            kept = out_dir / f"{base_name}_{size}.props.json"
            shutil.copy(props_file, kept)
            made.append(kept)
    return made
#--------------------------------------------------------------#

# Main entry point: one MP4 + one poster PNG (the closing frame) per size
def render_remotion(spec, brand: Brand, size: str, out_dir: Path, base_name: str,
                    music: Path | None = None, keep_props: bool = False) -> list[Path]:
    npx = npx_path()
    composition = COMPOSITIONS[spec.template]
    props = build_props(spec, brand, size)
    out_dir.mkdir(parents=True, exist_ok=True)
    if spec.template == "event_recap":
        return render_image(npx, composition, props, spec, out_dir, base_name, size, keep_props)
    video = out_dir / f"{base_name}_{size}.mp4"
    poster = out_dir / f"{base_name}_{size}.png"
    length, poster_frame = timing(spec, props)

    with tempfile.TemporaryDirectory() as tmp:
        props_file = Path(tmp) / "props.json"
        props_file.write_text(json.dumps(props), encoding="utf-8")
        silent = Path(tmp) / "silent.mp4" if music else video
        flags = [f"--props={props_file}", *render_flags(spec.template)]
        if spec.template == "talking_head":               # footage is served from its own folder
            flags.append(f"--public-dir={Path(spec.footage).parent}")
        run([npx, "remotion", "render", ENTRY, composition, str(silent), *flags], "Remotion render")
        run([npx, "remotion", "still", ENTRY, composition, str(poster), f"--frame={poster_frame}",
             *flags], "Remotion poster")
        if music:
            add_music(silent, music, length, video)
        made = [video, poster]
        if keep_props:                                     # for previewing in Remotion Studio
            kept = out_dir / f"{base_name}_{size}.props.json"
            shutil.copy(props_file, kept)
            made.append(kept)
    return made
#--------------------------------------------------------------#
#----------------------End-of-code-----------------------------#
