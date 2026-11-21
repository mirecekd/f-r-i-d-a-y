# backend/app/files/ziputil.py
"""Zip bomb guards and bounded member reads for every zip based format (docx, xlsx, epub, odt, zip)."""

import io
import zipfile

from app.files.common import MAX_MEMBER, MAX_ZIP_ENTRIES, MAX_ZIP_UNPACKED, ExtractError

MAX_RATIO = 200


def open_zip(raw: bytes) -> zipfile.ZipFile:
    """Open the archive and reject it when the central directory already looks like a bomb."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except (zipfile.BadZipFile, OSError, ValueError, NotImplementedError) as e:
        raise ExtractError("the archive is damaged or not a zip file") from e
    infos = zf.infolist()
    if len(infos) > MAX_ZIP_ENTRIES:
        raise ExtractError(f"archive has more than {MAX_ZIP_ENTRIES} entries")
    total = sum(i.file_size for i in infos)
    if total > MAX_ZIP_UNPACKED:
        raise ExtractError("archive would unpack to more than 200 MB")
    if any(i.file_size > 1_000_000 and i.file_size > MAX_RATIO * max(i.compress_size, 1) for i in infos):
        raise ExtractError("archive looks like a zip bomb (extreme compression ratio)")
    return zf


def read_member(zf: zipfile.ZipFile, name: str, limit: int = MAX_MEMBER) -> bytes:
    """Read one member, never more than `limit` bytes regardless of what the header claims."""
    try:
        with zf.open(name) as f:
            data = f.read(limit + 1)
    except (KeyError, zipfile.BadZipFile, RuntimeError, OSError, NotImplementedError) as e:
        raise ExtractError(f"cannot read {name} in the archive") from e
    if len(data) > limit:
        raise ExtractError(f"{name} in the archive is too large")
    return data
