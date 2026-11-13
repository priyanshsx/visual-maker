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
#   Every entry may also set: name (file name) and sizes (portrait / square / landscape).
#--------------------------------------------------------------#

# Imports Libraries
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
}
SizeName = Literal["portrait", "square", "landscape"]
#--------------------------------------------------------------#

# Shared fields for every template
class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BaseSpec(Strict):
    name: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]+$")
    sizes: list[SizeName] = Field(default_factory=lambda: ["portrait"], min_length=1)
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


Spec = Annotated[Union[QuoteSpec, StatSpec, CarouselSpec], Field(discriminator="template")]
_batch = TypeAdapter(list[Spec])
_single = TypeAdapter(Spec)
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
