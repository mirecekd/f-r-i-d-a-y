# backend/app/imaging/colors.py
"""Turn the colour words a vision model reports into #rrggbb values for the building pack."""

import re

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
NAMED = {
    "red": "#b5442e", "brown": "#7a5638", "grey": "#9a9a9a", "gray": "#9a9a9a", "white": "#f1ede4", "cream": "#efe6cf",
    "beige": "#d8c8a8", "yellow": "#e3c75a", "orange": "#d98a3d", "green": "#6f9a62", "blue": "#6b8fbf", "black": "#33343a",
    "terracotta": "#c0623f", "anthracite": "#464a52", "wood": "#b98d5e", "oak": "#c4a06a", "brick": "#a5503a",
    "stone": "#b3ab9c", "tile": "#c7c2b8", "parquet": "#b98d5e", "concrete": "#a8a8a4", "pink": "#d9a3a3",
}


def to_hex(value: object) -> str | None:
    """`#rrggbb` as is, a known colour word (first match inside the text) as its hex, else None."""
    text = str(value or "").strip()
    if _HEX.match(text):
        return text.lower()
    lowered = text.lower()
    return next((hex_ for word, hex_ in NAMED.items() if word in lowered), None)
