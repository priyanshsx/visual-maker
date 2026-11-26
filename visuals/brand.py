#---------------------beginning-of-code------------------------#
#--------------------------------------------------------------#

# File: visuals/brand.py
# Purpose: load a client's look (colours, font, logo, footer) from brands/<client>/brand.yaml.
#          Logo and font files are embedded into the HTML, so rendering works offline and
#          looks identical on every machine.
#          No logo file yet? The brand name is shown as a text wordmark instead.
#--------------------------------------------------------------#

# Imports Libraries
import base64
import re

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from visuals.paths import BRANDS_DIR, ROOT
#--------------------------------------------------------------#

# Global variables
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
FONT_FILE = re.compile(r"-(latin-ext|latin)-(\d{3})-normal\.woff2$")
# Character ranges of the two subsets (latin-ext covers Hungarian ő/ű, Polish, Czech, ...)
UNICODE_RANGES = {
    "latin": "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,"
             "U+0329,U+2000-206F,U+2074,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD",
    "latin-ext": "U+0100-02AF,U+0304,U+0308,U+0329,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,"
                 "U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF",
}
LOGO_TYPES = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg",
              ".jpeg": "image/jpeg", ".webp": "image/webp"}
#--------------------------------------------------------------#

# Classes describing a brand file (unknown keys are errors, so typos are caught)
class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Colors(Strict):
    primary: str                 # main brand colour (accents, cover slides)
    text: str                    # headings and body text
    muted: str                   # secondary text (author lines, sources)
    background: str              # slide background
    surface: str                 # cards and boxes on top of the background
    on_primary: str              # text colour on top of the primary colour

    @field_validator("*")
    @classmethod
    def must_be_hex(cls, v: str) -> str:
        if not HEX.match(v):
            raise ValueError(f"{v!r} is not a colour like #155EEF")
        return v


class Font(Strict):
    family: str = "Inter"
    folder: str | None = "fonts/inter"   # bundled font files (repo-relative); works offline
    google: bool = False                 # or load from Google Fonts (needs internet)
    weights: list[int] = Field(default_factory=lambda: [400, 600, 700, 800])


class Brand(Strict):
    client: str = ""             # filled in from the folder name
    display_name: str
    website: str | None = None
    handle: str | None = None    # shown in the footer, e.g. vizcorn.com or @vizcorn
    footer: str | None = None    # optional tagline line in the footer
    logo: str | None = None      # file name inside brands/<client>/
    logo_with_name: bool = False # show the brand name next to the logo (for icon-only logos)
    colors: Colors
    font: Font = Field(default_factory=Font)
    logo_data_uri: str | None = None   # filled in by load_brand, never written by hand
#--------------------------------------------------------------#

# Read the logo file and turn it into a data URI (returns None if there is no file yet)
def _logo_data_uri(client: str, filename: str | None) -> str | None:
    if not filename:
        return None
    path = BRANDS_DIR / client / filename
    if not path.exists():
        return None
    mime = LOGO_TYPES.get(path.suffix.lower())
    if mime is None:
        raise ValueError(f"Logo {path.name}: use one of {sorted(LOGO_TYPES)}")
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()
#--------------------------------------------------------------#

# Main entry point
def load_brand(client: str) -> Brand:
    path = BRANDS_DIR / client / "brand.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No brand file: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    data["client"] = client
    brand = Brand.model_validate(data)
    brand.logo_data_uri = _logo_data_uri(client, brand.logo)
    return brand
#--------------------------------------------------------------#

# @font-face rules for the bundled font files, embedded as data URIs ("" if none)
def font_face_css(brand: Brand) -> str:
    if not brand.font.folder:
        return ""
    folder = ROOT / brand.font.folder
    if not folder.is_dir():
        raise FileNotFoundError(f"Font folder not found: {folder}")
    rules = []
    for path in sorted(folder.glob("*.woff2")):
        match = FONT_FILE.search(path.name)
        if not match:
            continue
        subset, weight = match.group(1), int(match.group(2))
        if weight not in brand.font.weights:
            continue
        data = base64.b64encode(path.read_bytes()).decode()
        rules.append(
            f"@font-face {{ font-family: '{brand.font.family}'; font-style: normal; "
            f"font-weight: {weight}; font-display: block; "
            f"src: url(data:font/woff2;base64,{data}) format('woff2'); "
            f"unicode-range: {UNICODE_RANGES[subset]}; }}")
    if not rules:
        raise FileNotFoundError(f"No font files like '<name>-latin-400-normal.woff2' in {folder}")
    return "\n".join(rules)
#--------------------------------------------------------------#

# Google Fonts stylesheet link for the brand font (None unless font.google is true)
def font_css_url(brand: Brand) -> str | None:
    if not brand.font.google:
        return None
    family = brand.font.family.replace(" ", "+")
    weights = ";".join(str(w) for w in sorted(set(brand.font.weights)))
    return f"https://fonts.googleapis.com/css2?family={family}:wght@{weights}&display=block"
#--------------------------------------------------------------#
#----------------------End-of-code-----------------------------#
