# backend/app/files/textdecode.py
"""Encoding detection for text files: BOMs, utf-8, then cp1250 (Czech Windows files), then latin-1."""


def decode_text(raw: bytes) -> tuple[str, str]:
    """(text, encoding used)."""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16", errors="replace"), "utf-16"
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig", errors="replace"), "utf-8-sig"
    for enc in ("utf-8", "cp1250"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1"), "latin-1"
