#---------------------beginning-of-code------------------------#
#--------------------------------------------------------------#

# File: visuals/buckets.py
# Purpose: read and check a client's content buckets (brands/<client>/buckets.yaml).
#          A bucket = one kind of post (e.g. "feature launch") with its templates per format
#          (video / image), the defaults always applied, which LLM tier writes it, and the
#          brief + rules the LLM follows.
#--------------------------------------------------------------#

# Imports Libraries
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from visuals.paths import BRANDS_DIR
from visuals.specs import SPEC_CLASSES
#--------------------------------------------------------------#

# Models
class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Format(Strict):
    templates: list[str] = Field(min_length=1)     # first one is the default
    defaults: dict = Field(default_factory=dict)   # always applied on top of the LLM's draft
    hint: str | None = None                        # extra guidance for this format only

    @field_validator("templates")
    @classmethod
    def known_templates(cls, value):
        unknown = [t for t in value if t not in SPEC_CLASSES]
        if unknown:
            raise ValueError(f"unknown template(s): {', '.join(unknown)}")
        return value

    @model_validator(mode="after")
    def defaults_fit(self):
        for template in self.templates:
            fields = SPEC_CLASSES[template].model_fields
            wrong = [k for k in self.defaults if k not in fields]
            if wrong:
                raise ValueError(f"defaults {wrong} are not fields of the {template} template")
        return self


class Bucket(Strict):
    label: str
    status: Literal["ready", "draft", "samples_needed"] = "ready"
    notes: str | None = None
    model: Literal["fast", "smart"] = "fast"
    formats: dict[Literal["video", "image"], Format] = Field(min_length=1)
    brief: str
    rules: list[str] = Field(default_factory=list)

    def status_note(self) -> str | None:
        if self.status == "draft":
            return "Basic draft template: the design will change. " + (self.notes or "")
        if self.status == "samples_needed":
            return "Sample for team review, not final. " + (self.notes or "")
        return None
#--------------------------------------------------------------#

# Load all buckets for a client (empty dict if the client has none yet)
def load_buckets(client: str) -> dict[str, Bucket]:
    path = BRANDS_DIR / client / "buckets.yaml"
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {name: Bucket.model_validate(value) for name, value in data.items()}


def get_bucket(client: str, name: str) -> Bucket:
    buckets = load_buckets(client)
    if name not in buckets:
        known = ", ".join(buckets) or "none yet"
        raise ValueError(f"No bucket '{name}' for {client} (buckets: {known})")
    return buckets[name]
#--------------------------------------------------------------#
#----------------------End-of-code-----------------------------#
