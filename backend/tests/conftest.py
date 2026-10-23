"""Pytest setup: point the app at a throwaway SQLite database *before*
anything imports ``app.core.database``."""

import os
import sys
import tempfile
from pathlib import Path

_DB_DIR = tempfile.mkdtemp(prefix="yoke-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_DIR}/test.db"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
