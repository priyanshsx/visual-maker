#---------------------beginning-of-code------------------------#
#--------------------------------------------------------------#

# File: visuals/paths.py
# Purpose: one place that defines where every folder lives.
#--------------------------------------------------------------#

# Imports Libraries
from pathlib import Path
#--------------------------------------------------------------#

# Find the repo root (the folder that contains pyproject.toml)
def _find_root() -> Path:
    here = Path(__file__).resolve()
    for folder in [here, *here.parents]:
        if (folder / "pyproject.toml").exists():
            return folder
    raise RuntimeError("Could not find pyproject.toml above " + str(here))
#--------------------------------------------------------------#

# Global path variables
ROOT = _find_root()
BRANDS_DIR = ROOT / "brands"
TEMPLATES_DIR = ROOT / "templates"
INPUTS_DIR = ROOT / "inputs"
OUTPUTS_DIR = ROOT / "outputs"
#--------------------------------------------------------------#
#----------------------End-of-code-----------------------------#
