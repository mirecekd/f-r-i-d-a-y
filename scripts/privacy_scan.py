# scripts/privacy_scan.py
"""Refuses private files, company/customer words and key-like strings.

  python scripts/privacy_scan.py --staged   scan what is staged (used by scripts/pre-commit)
  python scripts/privacy_scan.py --tree     scan every tracked file (used by CI)

The word list is stored base64-encoded so this file does not carry the words in plain text.
Extra words (one regex per line) can be added in a local, gitignored .private-words file.
"""
from __future__ import annotations

import base64
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

WORDS_B64 = (
    "dHJhc2sKXGJkaXNzXGIKXGJ2d3MKYXN6cGRzCnpkcHMKbmV0d29yay4/Z2VuaXVzClxiY2V6XGIKYXNzYWsKbWlyZWNla1wub3Jn"
    "CmRldnBvbGljeQphcGlcLmFpXC5hd3MKdGVza2l0dHkKbG93YXNzCmdlbWVjaG8KaGVyZG9ncm9jbwpcYmtpdHRcYgptaXJkdm9y"
    "YWsKL2hvbWUvW2Etel0KREVWRUwvClxiWzAtOV17MTJ9XGIKdGVzbGEgbW9kZWwKYWxvanoKb3N0cmF2YQp3aWd5bQprb3RlbApj"
    "YWRkeQpAKD8hZXhhbXBsZVwuKVthLXowLTktXStcLihjb218Y3p8b3JnfG5ldHxpbylcYg=="
)

KEY_PATTERNS = [
    r"sk-[A-Za-z0-9_-]{16,}",
    r"AIza[0-9A-Za-z_-]{20,}",
    r"gsk_[A-Za-z0-9]{10,}",
    r"ghp_[A-Za-z0-9]{20,}",
    r"github_pat_[A-Za-z0-9_]{20,}",
    r"xox[baprs]-[A-Za-z0-9-]{10,}",
    r"AKIA[0-9A-Z]{16}",
    r"BEGIN [A-Z ]*PRIVATE KEY",
    r"(?i)(?:KEY|TOKEN|SECRET)\w*\s*[=:]\s*[\"']?[A-Za-z0-9+/_-]{32,}",
]

PRIVATE_PATH = re.compile(r"(^|/)(\.env|\.private-words)$|(^|/)(memory-bank|\.briefs|data)/|\.log$")
SKIP_CONTENT = re.compile(r"(^|/)package-lock\.json$")


def word_patterns() -> list[re.Pattern[str]]:
    words = base64.b64decode("".join(WORDS_B64)).decode().split("\n")
    extra = ROOT / ".private-words"
    if extra.exists():
        words += [w.strip() for w in extra.read_text(encoding="utf-8").splitlines() if w.strip()]
    return [re.compile(w, re.IGNORECASE) for w in words] + [re.compile(k) for k in KEY_PATTERNS]


def scan_lines(lines: list[str], patterns: list[re.Pattern[str]]) -> list[tuple[int, str]]:
    """(line number, category) for each line that matches; the matched text is never returned."""
    hits = []
    for number, line in enumerate(lines, 1):
        for index, pattern in enumerate(patterns):
            if pattern.search(line):
                hits.append((number, "key-like string" if index >= len(patterns) - len(KEY_PATTERNS) else "sensitive word"))
                break
    return hits


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True, cwd=ROOT).stdout


def scan_staged(patterns: list[re.Pattern[str]]) -> list[str]:
    problems = [f"{p}: private file is staged" for p in git("diff", "--cached", "--name-only").splitlines() if PRIVATE_PATH.search(p)]
    path = ""
    for line in git("diff", "--cached", "-U0", "--no-color").splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
        elif line.startswith("+") and not line.startswith("+++") and not SKIP_CONTENT.search(path):
            for _n, category in scan_lines([line[1:]], patterns):
                problems.append(f"{path}: {category} in an added line")
    return problems


def scan_tree(patterns: list[re.Pattern[str]]) -> list[str]:
    problems = []
    for path in git("ls-files").splitlines():
        if PRIVATE_PATH.search(path):
            problems.append(f"{path}: private file is tracked")
        if SKIP_CONTENT.search(path):
            continue
        try:
            text = (ROOT / path).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        for number, category in scan_lines(text.splitlines(), patterns):
            problems.append(f"{path}:{number}: {category}")
    return problems


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "--tree"
    patterns = word_patterns()
    problems = scan_staged(patterns) if mode == "--staged" else scan_tree(patterns)
    for problem in problems[:30]:
        print(f"privacy-scan: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
