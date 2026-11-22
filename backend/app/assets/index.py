# backend/app/assets/index.py
"""The curated asset index (index.json, built by scripts/build_asset_index.py) and the on-disk cache of downloaded models."""

import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

INDEX_FILE = Path(__file__).with_name("index.json")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")


@dataclass(frozen=True)
class Asset:
    id: str
    name: str
    tags: tuple[str, ...]
    category: str
    pack: str
    url: str
    license: str
    author: str
    source_page: str
    bytes: int | None = None

    def credit(self) -> str:
        return f"{self.name} by {self.author} ({self.license}), {self.source_page}"

    def public(self) -> dict:
        return {"name": self.name, "author": self.author, "license": self.license, "source_page": self.source_page}


@lru_cache(maxsize=1)
def load_index() -> dict[str, Asset]:
    rows = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    return {r["id"]: Asset(**{**r, "tags": tuple(r["tags"])}) for r in rows}


def get(asset_id: object) -> Asset | None:
    """The index entry for an id; None for anything that is not a well-formed known id."""
    if not isinstance(asset_id, str) or not ID_RE.fullmatch(asset_id):
        return None
    return load_index().get(asset_id)


def allowed_hosts() -> frozenset[str]:
    """Only these hosts may be contacted, directly or through a redirect: the ones present in the index."""
    return frozenset(urlsplit(a.url).hostname or "" for a in load_index().values())


def assets_dir() -> Path:
    return Path(os.getenv("FRIDAY_DATA_DIR", "/srv/data")) / "assets"


def file_of(asset_id: str) -> Path:
    """Cache path of a known id. Callers pass only ids validated by `get`; the name never comes from request text."""
    return assets_dir() / f"{asset_id}.glb"
