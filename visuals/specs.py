#---------------------beginning-of-code------------------------#
#--------------------------------------------------------------#

# File: visuals/specs.py
# Purpose: what words each template needs, with limits that keep text readable.
#          You write these in inputs/<client>/<file>.yaml (one entry per image):
#
#   - template: quote          -> quote, author (optional), role (optional)
#   - template: stat           -> stat, headline, body (optional), source (optional)
#   - template: carousel       -> slides: list of {title, body (optional)}
#   - template: title          -> title, kicker (optional), subtitle (optional),
#                                 image (optional: a screenshot or picture in inputs/<client>/)
#
#   Motion templates (always an MP4 plus a poster PNG of the last frame):
#   - template: stat_motion    -> same fields as stat; the number counts up
#   - template: quote_motion   -> same fields as quote; lines appear one by one
#   - template: device_demo    -> title, image (a screenshot), steps: list of {caption, focus,
#                                 zoom, marker, image (optional)}, kicker, cta and
#                                 look: clean | cinematic (optional).
#                                 A 3D screen the camera glides over; made with Remotion
#                                 (needs Node.js: cd remotion && npm install, once).
#   - template: event_recap    -> one infographic image about an event: badge, title,
#                                 title_accent, intro, stats, cards (speakers), big_picture,
#                                 closing. Portrait only. Made with Remotion (3D hero).
#   Motion entries may set duration (seconds; default: as long as the animation needs,
#   plus a 2.5s hold) and music. In quotes, *words in asterisks* are shown in brand colour.
#
#   Every entry may also set: name (file name), sizes (portrait / square / landscape / story),
#   and video: true to also get a slideshow MP4 (seconds_per_slide, music optional).
#--------------------------------------------------------------#

# Imports Libraries
import re
from pathlib import Path
from typing import Annotated, Literal, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator
#--------------------------------------------------------------#

# Global variables: output sizes in pixels (width, height)
SIZES = {
    "portrait": (1080, 1350),    # LinkedIn / Instagram feed, LinkedIn carousels
    "square": (1080, 1080),
    "landscape": (1200, 675),    # X / Twitter
    "story": (1080, 1920),       # Reels, Shorts, LinkedIn vertical video
}
SizeName = Literal["portrait", "square", "landscape", "story"]
#--------------------------------------------------------------#

# Shared fields for every template
class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BaseSpec(Strict):
    name: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]+$")
    sizes: list[SizeName] = Field(default_factory=lambda: ["portrait"], min_length=1)
    video: bool = False                                   # also make a slideshow MP4
    seconds_per_slide: float = Field(default=3.5, ge=1.5, le=10)
    music: str | None = None                              # audio file in inputs/<client>/
#--------------------------------------------------------------#

# One class per template
class QuoteSpec(BaseSpec):
    template: Literal["quote"]
    quote: str = Field(min_length=1, max_length=280)
    author: str | None = Field(default=None, max_length=60)
    role: str | None = Field(default=None, max_length=80)


class StatSpec(BaseSpec):
    template: Literal["stat"]
    stat: str = Field(min_length=1, max_length=12)          # e.g. "3 in 4", "42%", "€1.2M"
    headline: str = Field(min_length=1, max_length=110)
    body: str | None = Field(default=None, max_length=240)
    source: str | None = Field(default=None, max_length=120)


class Slide(Strict):
    title: str = Field(min_length=1, max_length=90)
    body: str | None = Field(default=None, max_length=320)


class CarouselSpec(BaseSpec):
    template: Literal["carousel"]
    slides: list[Slide] = Field(min_length=2, max_length=12)
#--------------------------------------------------------------#

# Motion templates: always video, so no video / seconds_per_slide fields
class MotionSpec(Strict):
    name: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]+$")
    sizes: list[SizeName] = Field(default_factory=lambda: ["portrait"], min_length=1)
    duration: float | None = Field(default=None, ge=3, le=30)   # None = automatic
    music: str | None = None


class QuoteMotionSpec(MotionSpec):
    template: Literal["quote_motion"]
    quote: str = Field(min_length=1, max_length=280)
    author: str | None = Field(default=None, max_length=60)
    role: str | None = Field(default=None, max_length=80)


class StatMotionSpec(MotionSpec):
    template: Literal["stat_motion"]
    stat: str = Field(min_length=1, max_length=12)
    headline: str = Field(min_length=1, max_length=110)
    body: str | None = Field(default=None, max_length=240)
    source: str | None = Field(default=None, max_length=120)


class TitleSpec(BaseSpec):
    template: Literal["title"]
    kicker: str | None = Field(default=None, max_length=40)       # small label, e.g. "New in ..."
    title: str = Field(min_length=1, max_length=70)
    subtitle: str | None = Field(default=None, max_length=180)
    image: str | None = None                  # file in inputs/<client>/ (png, jpg, webp, svg)


Unit = Annotated[float, Field(ge=0, le=1)]


class DemoStep(Strict):
    caption: str = Field(min_length=1, max_length=90)      # *words* in brand colour
    focus: tuple[Unit, Unit] = (0.5, 0.5)    # where to look: across, down (0 = left/top, 1 = right/bottom)
    zoom: float = Field(default=1, ge=1, le=3)   # 1 = whole screenshot, 2 = twice as close
    marker: bool = False                      # pulse a ring on the focus point
    image: str | None = None                  # another screenshot for this step (default: the main one)


# device_demo timing (seconds): intro title, each step, closing frame
DEMO_INTRO, DEMO_STEP, DEMO_OUTRO, DEMO_MIN_STEP = 2.2, 3.0, 3.0, 2.0


class DeviceDemoSpec(MotionSpec):
    template: Literal["device_demo"]
    kicker: str | None = Field(default=None, max_length=40)
    title: str = Field(min_length=1, max_length=70)          # intro and closing line
    image: str                                # main screenshot in inputs/<client>/
    steps: list[DemoStep] = Field(min_length=1, max_length=6)
    cta: str | None = Field(default=None, max_length=60)     # closing button, e.g. a URL
    look: Literal["clean", "cinematic"] = "clean"   # cinematic: fog, reflections, glow, film grain

    @model_validator(mode="after")
    def duration_fits_steps(self):
        shortest = DEMO_INTRO + DEMO_OUTRO + DEMO_MIN_STEP * len(self.steps)
        if self.duration is not None and self.duration < shortest:
            raise ValueError(f"duration is too short for {len(self.steps)} steps "
                             f"(at least {shortest:.1f}s)")
        return self


# event_recap: one rich infographic image (Remotion), like a magazine page about an event
ICONS = Literal["flask", "leaf", "globe", "shield", "recycle", "thermometer", "droplet", "bearing",
                "mic", "molecule", "chart", "people", "scale", "gear"]


class RecapStat(Strict):
    value: str = Field(min_length=1, max_length=10)          # e.g. "~5,000"
    label: str = Field(min_length=1, max_length=22)          # e.g. "attendees"


class RecapCard(Strict):
    icon: ICONS
    name: str = Field(min_length=1, max_length=40)           # speaker
    org: str | None = Field(default=None, max_length=40)     # their organisation
    topic: str = Field(min_length=1, max_length=60)
    body: str = Field(min_length=1, max_length=175)          # what they said, in 2-4 lines


class RecapPoint(Strict):
    icon: ICONS
    text: str = Field(min_length=1, max_length=60)


class BigPicture(Strict):
    label: str = Field(default="The bigger picture", max_length=30)
    title: str = Field(min_length=1, max_length=150)         # *words* in a lighter blue
    points_label: str | None = Field(default=None, max_length=34)
    points: list[RecapPoint] = Field(default_factory=list, max_length=4)


class EventRecapSpec(Strict):
    template: Literal["event_recap"]
    name: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]+$")
    sizes: list[Literal["portrait"]] = Field(default_factory=lambda: ["portrait"], min_length=1)
    video: bool = False                       # also make a 5-second animated MP4
    badge: str | None = Field(default=None, max_length=50)   # e.g. event name and city
    title: str = Field(min_length=1, max_length=60)
    title_accent: str | None = Field(default=None, max_length=60)   # second line, brand colour
    intro: str = Field(min_length=1, max_length=230)
    stats: list[RecapStat] = Field(default_factory=list, max_length=3)
    cards_label: str = Field(default="Key takeaways", max_length=50)
    cards: list[RecapCard] = Field(min_length=2, max_length=4)
    big_picture: BigPicture
    closing: str = Field(min_length=1, max_length=130)


TEMPLATES = ["quote", "stat", "carousel", "title", "quote_motion", "stat_motion", "device_demo",
             "event_recap"]
Spec = Annotated[Union[QuoteSpec, StatSpec, CarouselSpec, TitleSpec, QuoteMotionSpec,
                       StatMotionSpec, DeviceDemoSpec, EventRecapSpec],
                 Field(discriminator="template")]
_batch = TypeAdapter(list[Spec])
_single = TypeAdapter(Spec)
#--------------------------------------------------------------#

# Split a stat into the part that counts up and the text around it, e.g.
#   "75%"   -> prefix "",  number 75,   suffix "%"
#   "€1.2M" -> prefix "€", number 1.2,  suffix "M"  (counts with 1 decimal)
#   "1,250" -> number 1250, shown with a thousands comma
# Returns None when counting would look wrong ("3 in 4", "24/7", "Q3", a year like "2025"):
# those simply fade in instead.
_STAT = re.compile(r"^(?P<prefix>[^\d]*?)(?P<num>\d{1,3}(?:,\d{3})+|\d+)(?:\.(?P<dec>\d+))?(?P<suffix>[^\d]*)$")


def split_stat(stat: str) -> dict | None:
    match = _STAT.match(stat.strip())
    if not match:
        return None
    num, dec = match.group("num"), match.group("dec") or ""
    prefix, suffix = match.group("prefix"), match.group("suffix")
    if re.search(r"[A-Za-z]", prefix):                    # Q3, FY24, H1
        return None
    if not dec and "," not in num and len(num) == 4 and 1900 <= int(num) <= 2100 \
            and not prefix.strip() and not suffix.strip():  # a year
        return None
    return {
        "prefix": prefix,
        "value": float(num.replace(",", "") + (f".{dec}" if dec else "")),
        "decimals": len(dec),
        "thousands": "," if "," in num else "",
        "suffix": suffix,
    }
#--------------------------------------------------------------#

# Read a batch file (a YAML list of entries) and validate every entry
def load_batch(path: Path) -> list:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):                     # a single entry is fine too
        data = [data]
    if not isinstance(data, list) or not data:
        raise ValueError(f"{path} must contain a list of entries (each starting with '- template:')")
    return _batch.validate_python(data)
#--------------------------------------------------------------#

# Build one spec from a plain dict (used by the command line)
def spec_from_dict(data: dict):
    return _single.validate_python(data)
#--------------------------------------------------------------#
#----------------------End-of-code-----------------------------#
