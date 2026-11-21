# backend/tests/test_privacy_scan.py
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "privacy_scan.py"


def load_scan():
    spec = importlib.util.spec_from_file_location("privacy_scan", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_key_like_strings_are_flagged_without_returning_the_text():
    scan = load_scan()
    patterns = scan.word_patterns()
    line = "GEMINI_API_KEY=" + "A" * 40
    assert scan.scan_lines([line], patterns) == [(1, "key-like string")]
    assert scan.scan_lines(["GEMINI_API_KEY=your-key-here"], patterns) == []


def test_private_paths_are_refused():
    scan = load_scan()
    assert scan.PRIVATE_PATH.search(".env")
    assert scan.PRIVATE_PATH.search("memory-bank/notes.md")
    assert scan.PRIVATE_PATH.search("backend/data/x.json")
    assert not scan.PRIVATE_PATH.search(".env.example")


def test_tracked_tree_is_clean():
    scan = load_scan()
    assert scan.scan_tree(scan.word_patterns()) == []


def test_public_author_email_is_allowed_but_other_addresses_are_not():
    scan = load_scan()
    patterns = scan.word_patterns()
    at = "@" + "gmail.com"
    assert scan.scan_lines(["Author - " + scan.PUBLIC_AUTHOR_EMAIL], patterns) == []
    assert scan.scan_lines(["someone" + at], patterns) == [(1, "sensitive word")]
