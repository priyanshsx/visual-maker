#---------------------beginning-of-code------------------------#
#--------------------------------------------------------------#

# File: tests/test_specs.py
# Purpose: check input files are read correctly and mistakes give clear messages.
# Usage:   python -m pytest tests/test_specs.py -v
#--------------------------------------------------------------#

# Imports Libraries
import pytest
from pydantic import ValidationError

from visuals.cli import friendly_errors
from visuals.paths import INPUTS_DIR
from visuals.specs import load_batch, spec_from_dict
#--------------------------------------------------------------#

# Tests: reading files
def test_example_file_loads():
    specs = load_batch(INPUTS_DIR / "vizcorn" / "example.yaml")
    assert [s.template for s in specs] == ["quote", "stat", "carousel"]
    assert specs[1].sizes == ["portrait", "landscape"]


def test_single_entry_file_is_fine(tmp_path):
    f = tmp_path / "one.yaml"
    f.write_text("template: quote\nquote: Hello\n")
    assert len(load_batch(f)) == 1


def test_default_size_is_portrait():
    assert spec_from_dict({"template": "quote", "quote": "Hi"}).sizes == ["portrait"]
#--------------------------------------------------------------#

# Tests: mistakes are caught, with plain-English messages
def test_typo_in_field_name():
    with pytest.raises(ValidationError) as e:
        spec_from_dict({"template": "quote", "qoute": "Hi"})
    msg = friendly_errors(e.value)
    assert '"quote" is missing' in msg and '"qoute" is not a field' in msg


def test_too_long_text():
    with pytest.raises(ValidationError) as e:
        spec_from_dict({"template": "stat", "stat": "x" * 13, "headline": "ok"})
    assert "too long (max 12 characters)" in friendly_errors(e.value)


def test_carousel_needs_two_slides(tmp_path):
    f = tmp_path / "c.yaml"
    f.write_text("- template: carousel\n  slides:\n    - title: only one\n")
    with pytest.raises(ValidationError) as e:
        load_batch(f)
    assert "entry 1 (carousel): a carousel needs at least 2 slides" in friendly_errors(e.value)


def test_unknown_template():
    with pytest.raises(ValidationError) as e:
        spec_from_dict({"template": "poster"})
    assert "template must be one of" in friendly_errors(e.value)


def test_bad_size_and_name():
    with pytest.raises(ValidationError):
        spec_from_dict({"template": "quote", "quote": "Hi", "sizes": ["huge"]})
    with pytest.raises(ValidationError):
        spec_from_dict({"template": "quote", "quote": "Hi", "name": "has spaces"})
#--------------------------------------------------------------#
#----------------------End-of-code-----------------------------#
