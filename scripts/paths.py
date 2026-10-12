"""Single source of truth for repository paths.

Every Python tool imports ROOT_DIR from here instead of walking up from
__file__ itself. The root is read from the REPO_ROOT environment variable when
a launcher sets one; otherwise it is resolved once, here, from this file's
location so a plain source checkout still works.
"""
from __future__ import annotations

import os
from pathlib import Path

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = Path(os.environ.get("REPO_ROOT") or os.path.dirname(_SCRIPTS_DIR)).resolve()