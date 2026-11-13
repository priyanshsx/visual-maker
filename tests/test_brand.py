#---------------------beginning-of-code------------------------#
#--------------------------------------------------------------#

# File: tests/test_brand.py
# Purpose: check brand files load, bad colours are caught, and fonts/logos are embedded.
# Usage:   python -m pytest tests/test_brand.py -v
#--------------------------------------------------------------#

# Imports Libraries
import pytest
from pydantic import ValidationError

from visuals import brand as brand_mod
from visuals.brand import Brand, font_face_css, load_brand
#--------------------------------------------------------------#

# Helper: a minimal valid brand as a dict
def minimal(**over):
    data = {"display_name": "Acme",
            "colors": {"primary": "#155EEF", "text": "#0B1B3F", "muted": "#51607F",
                       "background": "#F5F8FF", "surface": "#FFFFFF", "on_primary": "#FFFFFF"}}
    data.update(over)
    return data
#--------------------------------------------------------------#

# Tests: loading
def test_vizcorn_brand_loads():
    b = load_brand("vizcorn")
    assert b.display_name == "VizCorn" and b.colors.primary == "#155EEF"


def test_missing_brand_folder():
    with pytest.raises(FileNotFoundError):
        load_brand("no_such_client")
#--------------------------------------------------------------#

# Tests: validation
def test_bad_colour_rejected():
    data = minimal()
    data["colors"]["primary"] = "blue"
    with pytest.raises(ValidationError, match="not a colour"):
        Brand.model_validate(data)


def test_unknown_key_rejected():
    with pytest.raises(ValidationError):
        Brand.model_validate(minimal(colours={}))            # British spelling = typo here
#--------------------------------------------------------------#

# Tests: logo and font embedding
def test_missing_logo_file_falls_back_to_wordmark(tmp_path, monkeypatch):
    (tmp_path / "acme").mkdir()
    (tmp_path / "acme" / "brand.yaml").write_text(
        "display_name: Acme\nlogo: logo.svg\ncolors: {primary: '#111111', text: '#111111', "
        "muted: '#111111', background: '#FFFFFF', surface: '#FFFFFF', on_primary: '#FFFFFF'}\n")
    monkeypatch.setattr(brand_mod, "BRANDS_DIR", tmp_path)
    assert load_brand("acme").logo_data_uri is None


def test_logo_is_embedded(tmp_path, monkeypatch):
    (tmp_path / "acme").mkdir()
    (tmp_path / "acme" / "logo.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>")
    (tmp_path / "acme" / "brand.yaml").write_text(
        "display_name: Acme\nlogo: logo.svg\ncolors: {primary: '#111111', text: '#111111', "
        "muted: '#111111', background: '#FFFFFF', surface: '#FFFFFF', on_primary: '#FFFFFF'}\n")
    monkeypatch.setattr(brand_mod, "BRANDS_DIR", tmp_path)
    assert load_brand("acme").logo_data_uri.startswith("data:image/svg+xml;base64,")


def test_bundled_font_is_embedded_for_both_subsets():
    css = font_face_css(load_brand("vizcorn"))
    assert css.count("@font-face") == 8                      # 4 weights x (latin + latin-ext)
    assert "U+0100-02AF" in css                              # latin-ext: Hungarian ő, ű
#--------------------------------------------------------------#
#----------------------End-of-code-----------------------------#
