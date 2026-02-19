"""Pytest configuration: ensure src/ is importable in tests.

This allows importing `genrepo` without installing the package in editable mode.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for p in (REPO_ROOT, SRC_ROOT):
    sys.path.insert(0, str(p))
