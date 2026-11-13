#---------------------beginning-of-code------------------------#
#--------------------------------------------------------------#

# File: visuals/specs.py
# Purpose: what words each template needs, with limits that keep text readable.
#          You write these in inputs/<client>/<file>.yaml (one entry per image):
#
#   - template: quote          -> quote, author (optional), role (optional)
#   - template: stat           -> stat, headline, body (optional), source (optional)
#   - template: carousel       -> slides: list of {title, body (optional)}
#
#   Motion templates (always an MP4 plus a poster PNG of the last frame):
#   - template: stat_motion    -> same fields as stat; the number counts up
#   - template: quote_motion   -> same fields as quote; lines appear one by one
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
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
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


TEMPLATES = ["quote", "stat", "carousel", "quote_motion", "stat_motion"]
Spec = Annotated[Union[QuoteSpec, StatSpec, CarouselSpec, QuoteMotionSpec, StatMotionSpec],
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
