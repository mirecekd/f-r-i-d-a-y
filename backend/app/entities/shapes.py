# backend/app/entities/shapes.py
"""Entity shape and accent colour by stored-item kind and file kind."""

FILE_SHAPES = {
    "pdf": "book", "epub": "book", "docx": "doc", "odt": "doc", "text": "doc", "markdown": "doc", "html": "doc",
    "rtf": "doc", "csv": "table", "xlsx": "table", "json": "code", "yaml": "code", "toml": "code", "xml": "code",
    "code": "code", "audio": "audio", "zip": "archive",
}
ACCENTS = {
    "image": "#4fd8ff", "doc": "#7aa8ff", "book": "#b48cff", "table": "#5cf0a8", "code": "#ffd24a",
    "audio": "#ff8ccf", "archive": "#ff9b5c", "tool": "#ff6b6b", "model": "#4fe0d0", "note": "#cfefff",
}


def shape_of_file(kind: str) -> str:
    return FILE_SHAPES.get(kind, "doc")


def accent_of(shape: str) -> str:
    return ACCENTS.get(shape, ACCENTS["note"])
