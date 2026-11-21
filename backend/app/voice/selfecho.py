# backend/app/voice/selfecho.py
"""Self-echo detector: is the model "hearing" what it said a moment ago through the speaker and microphone?"""

import re
import unicodedata
from difflib import SequenceMatcher

THRESHOLD = 0.85  # similarity needed to call the heard text an echo of Friday's own output
WINDOW_S = 3.0  # an input transcript is only compared with output that ended at most this long ago
MIN_BLOCK_CHARS = 4  # in a partial match, only runs of at least this many equal characters count
MIN_PARTIAL_CHARS = 12  # shorter heard text must match the whole output, not just a part of it


def normalise(text: str) -> str:
    """Lower case, no diacritics, only letters and digits separated by single spaces."""
    stripped = "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", stripped).split())


def similarity(heard: str, own: str) -> float:
    """Fuzzy match 0..1 of normalised texts; a long heard fragment that lies inside `own` counts by coverage."""
    a, b = normalise(heard), normalise(own)
    if not a or not b:
        return 0.0
    whole = SequenceMatcher(None, a, b, autojunk=False).ratio()
    if len(a) < MIN_PARTIAL_CHARS or len(a) >= len(b):
        return whole
    blocks = SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks()
    return max(whole, sum(m.size for m in blocks if m.size >= MIN_BLOCK_CHARS) / len(a))


def is_self_echo(heard: str, own: str, age_s: float, threshold: float = THRESHOLD, window_s: float = WINDOW_S) -> bool:
    return 0.0 <= age_s <= window_s and similarity(heard, own) >= threshold


class EchoGuard:
    """Remembers the end of Friday's last output transcript and judges later input transcripts against it."""

    def __init__(self) -> None:
        self._own = ""
        self._at = 0.0
        self.notified = False  # the user was told "Ozvena potlacena" once

    def remember(self, own_text: str, now: float) -> None:
        if own_text.strip():
            self._own, self._at = own_text, now

    def is_echo(self, heard: str, now: float) -> bool:
        return bool(self._own) and is_self_echo(heard, self._own, now - self._at)
