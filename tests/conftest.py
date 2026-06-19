from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "plugins/pr-review/skills/recipe-pr-review"
SCRIPTS_DIR = SKILL_DIR / "scripts"


def load_script(module_name: str, filename: str):
    sys.path.insert(0, str(SCRIPTS_DIR))
    path = SCRIPTS_DIR / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module
