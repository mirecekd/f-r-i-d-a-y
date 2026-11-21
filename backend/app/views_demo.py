# backend/app/views_demo.py
"""One sample payload per view kind; sent on `{t:'demo', what:'views'}` when FRIDAY_DEMO=1."""

from app.views import view_msg

_SVG = (
    "data:image/svg+xml;utf8,"
    "<svg xmlns='http://www.w3.org/2000/svg' width='320' height='180'>"
    "<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>"
    "<stop offset='0' stop-color='%234fd8ff'/><stop offset='1' stop-color='%23b36bff'/>"
    "</linearGradient></defs><rect width='320' height='180' fill='url(%23g)'/>"
    "<circle cx='160' cy='90' r='50' fill='none' stroke='white' stroke-width='4'/></svg>"
)

_CODE = (
    "def fib(n: int) -> int:\n"
    "    # classic recursion\n"
    "    if n < 2:\n"
    "        return n\n"
    "    return fib(n - 1) + fib(n - 2)\n\n"
    "print([fib(i) for i in range(10)], 'done')\n"
)

_MD = (
    "# Friday notes\n\nSome **bold**, *italic* and `inline code`.\n\n"
    "- first item\n- second item with [a link](https://example.com)\n\n"
    "1. one\n2. two\n\n> quoted text\n\n"
    "<script>alert('not executed')</script>\n"
)


def sample_views() -> list[dict]:
    labels = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    ds = [{"label": "alpha", "data": [3, 7, 4, 9, 6]}, {"label": "beta", "data": [5, 2, 8, 4, 7]}]
    out = [
        view_msg("image", {"url": _SVG, "alt": "gradient"}, "Image", "demo-image"),
        view_msg("chart", {"type": "line", "labels": labels, "datasets": ds}, "Line chart", "demo-line"),
        view_msg("chart", {"type": "bar", "labels": labels, "datasets": ds}, "Bar chart", "demo-bar"),
        view_msg("chart", {"type": "pie", "labels": labels, "datasets": [ds[0]]}, "Pie chart", "demo-pie"),
        view_msg(
            "chart",
            {"type": "scatter", "datasets": [{"label": "pts", "data": [[1, 2], [2, 5], [3, 3], [4, 8], [5, 6]]}]},
            "Scatter chart",
            "demo-scatter",
        ),
        view_msg("chart", {"type": "radar", "labels": labels, "datasets": ds}, "Radar chart", "demo-radar"),
        view_msg(
            "table",
            {"columns": ["Planet", "Moons", "Radius km"], "rows": [["Earth", 1, 6371], ["Mars", 2, 3389], ["Jupiter", 95, 69911]]},
            "Table",
            "demo-table",
        ),
        view_msg("markdown", {"text": _MD}, "Markdown", "demo-md"),
        view_msg("code", {"lang": "python", "code": _CODE}, "Code", "demo-code"),
        view_msg("diagram", {"code": "graph LR\n  A[Mic] --> B(Friday)\n  B --> C{Model}\n  C --> D[Voice]\n  C --> E[3D]"}, "Diagram", "demo-diagram"),
        view_msg("map", {"center": [50.0755, 14.4378], "zoom": 12, "markers": [{"lat": 50.0755, "lon": 14.4378, "label": "Praha"}]}, "Map", "demo-map"),
        view_msg("json", {"value": {"name": "Friday", "ok": True, "n": 3, "tags": ["a", "b"], "nested": {"x": None}}}, "JSON", "demo-json"),
    ]
    return out
