# backend/tests/test_release.py
import importlib.util
import re
from pathlib import Path

from app import __version__

RELEASE = Path(__file__).resolve().parents[2] / "scripts" / "release.py"


def load_next_version():
    spec = importlib.util.spec_from_file_location("release_script", RELEASE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.next_version


def test_version_is_yyyymmdd_dot_counter():
    assert re.fullmatch(r"\d{8}\.\d+", __version__)


def test_next_version_counts_todays_tags_only():
    next_version = load_next_version()
    assert next_version([], "20261119") == "20261119.1"
    assert next_version(["20261119.1", "20261119.3", "20261118.9", "v1"], "20261119") == "20261119.4"
