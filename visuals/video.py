#---------------------beginning-of-code------------------------#
#--------------------------------------------------------------#

# File: visuals/video.py
# Purpose: everything that makes MP4s with FFmpeg.
#   make_slideshow: rendered slide PNGs -> slideshow MP4
#   - each slide holds for N seconds with a slow zoom (the "Ken Burns" effect)
#   - each slide slides in from the right, like swiping a carousel
#   - optional background music, faded in and out, trimmed to the video length
#   start_encoder: an FFmpeg process that motion templates stream frames into, one PNG per frame
# Output is H.264 MP4 (plays everywhere: LinkedIn, X, Instagram, WhatsApp).
# Needs FFmpeg installed once on the machine: brew install ffmpeg
#--------------------------------------------------------------#

# Imports Libraries
import shutil
import subprocess
from pathlib import Path
#--------------------------------------------------------------#

# Global variables
FPS = 30
FADE_SECONDS = 0.5            # length of the transition between slides
TRANSITION = "slideleft"      # FFmpeg xfade transition (no overlapping text, unlike a crossfade)
ZOOM_END = 1.05               # each slide zooms from 100% to 105%
UPSCALE = 3                   # zoom on a 3x larger image: avoids jittery motion


class VideoError(Exception):
    pass


# Video encoders need even pixel sizes (1200x675 becomes 1200x676; images keep their exact size)
def even(n: int) -> int:
    return n + (n % 2)
#--------------------------------------------------------------#

# Check FFmpeg is installed; returns its path
def ffmpeg_path() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise VideoError("FFmpeg is not installed. On a Mac run: brew install ffmpeg")
    return path
#--------------------------------------------------------------#

# Total video length: every slide's time, minus the overlap of each transition
def total_seconds(slide_count: int, seconds_per_slide: float) -> float:
    return slide_count * seconds_per_slide - (slide_count - 1) * FADE_SECONDS
#--------------------------------------------------------------#

# Audio filter: trim music to the video, fade in over 1s and out over the last 1.5s
def audio_filter(length: float) -> str:
    fade_out_start = max(length - 1.5, 0)
    return (f"atrim=0:{length:.3f},afade=t=in:d=1,"
            f"afade=t=out:st={fade_out_start:.3f}:d=1.5,volume=0.8")


VIDEO_ARGS = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
              "-r", str(FPS), "-movflags", "+faststart"]
AUDIO_ARGS = ["-c:a", "aac", "-b:a", "160k"]
#--------------------------------------------------------------#

# Build the FFmpeg filter that zooms each slide and joins them with transitions
def build_filter(slide_count: int, seconds_per_slide: float, width: int, height: int) -> str:
    frames = round(seconds_per_slide * FPS)
    step = (ZOOM_END - 1) / frames
    parts = []
    for i in range(slide_count):
        parts.append(
            f"[{i}:v]scale={width * UPSCALE}:{height * UPSCALE},"
            f"zoompan=z='min(1+{step:.6f}*on,{ZOOM_END})':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={frames}:s={width}x{height}:fps={FPS},setsar=1,format=yuv420p[s{i}]")
    if slide_count == 1:
        parts.append("[s0]null[v]")
        return ";".join(parts)
    prev = "s0"
    for i in range(1, slide_count):
        offset = i * (seconds_per_slide - FADE_SECONDS)
        out = "v" if i == slide_count - 1 else f"x{i}"
        parts.append(f"[{prev}][s{i}]xfade=transition={TRANSITION}:duration={FADE_SECONDS}:"
                     f"offset={offset:.3f}[{out}]")
        prev = out
    return ";".join(parts)
#--------------------------------------------------------------#

# Main entry point: PNG slides (in order) -> MP4
def make_slideshow(slides: list[Path], out_path: Path, width: int, height: int,
                   seconds_per_slide: float = 3.5, music: Path | None = None) -> Path:
    if not slides:
        raise VideoError("No slides to turn into a video")
    if music is not None and not music.exists():
        raise VideoError(f"Music file not found: {music}")

    length = total_seconds(len(slides), seconds_per_slide)
    cmd = [ffmpeg_path(), "-y", "-loglevel", "error"]
    for slide in slides:
        cmd += ["-i", str(slide)]
    filters = build_filter(len(slides), seconds_per_slide, even(width), even(height))
    maps = ["-map", "[v]"]

    if music is not None:
        cmd += ["-i", str(music)]
        filters += f";[{len(slides)}:a]{audio_filter(length)}[a]"
        maps += ["-map", "[a]", *AUDIO_ARGS]

    cmd += ["-filter_complex", filters, *maps, *VIDEO_ARGS, "-t", f"{length:.3f}", str(out_path)]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise VideoError(f"FFmpeg failed: {result.stderr.strip()[-500:]}")
    return out_path
#--------------------------------------------------------------#

# Start an FFmpeg process that turns PNG frames (written to its stdin) into an MP4.
# Write every frame with proc.stdin.write(png_bytes), then call finish_encoder(proc).
def start_encoder(out_path: Path, length: float, music: Path | None = None) -> subprocess.Popen:
    if music is not None and not music.exists():
        raise VideoError(f"Music file not found: {music}")
    cmd = [ffmpeg_path(), "-y", "-loglevel", "error",
           "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "png", "-i", "-"]
    filters = "[0:v]scale=ceil(iw/2)*2:ceil(ih/2)*2,setsar=1[v]"
    maps = ["-map", "[v]"]
    if music is not None:
        cmd += ["-i", str(music)]
        filters += f";[1:a]{audio_filter(length)}[a]"
        maps += ["-map", "[a]", *AUDIO_ARGS]
    cmd += ["-filter_complex", filters]
    cmd += [*maps, *VIDEO_ARGS, "-t", f"{length:.3f}", str(out_path)]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    return subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)


# Close the frame stream and wait for FFmpeg; raises VideoError if it failed
def finish_encoder(proc: subprocess.Popen) -> None:
    proc.stdin.close()
    stderr = proc.stderr.read().decode(errors="replace")
    if proc.wait() != 0:
        raise VideoError(f"FFmpeg failed: {stderr.strip()[-500:]}")
#--------------------------------------------------------------#
#----------------------End-of-code-----------------------------#
