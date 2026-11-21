# backend/tests/vision_helpers.py
"""Generated test pictures for the vision tests (Pillow, in memory)."""

import io

from PIL import Image, ImageDraw


def png_bytes(size: tuple[int, int] = (320, 200), color: str = "#3366cc") -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, "PNG")
    return out.getvalue()


def jpeg_with_gps() -> bytes:
    """JPEG with EXIF: Prague-ish GPS, capture time, camera make/model and orientation 6."""
    im = Image.new("RGB", (400, 300), "#aa5522")
    exif = Image.Exif()
    exif[271], exif[272], exif[274] = "FriCam", "X100", 6
    exif[306] = "2024:05:01 10:20:30"
    sub = exif.get_ifd(0x8769)
    sub[36867] = "2024:05:01 10:20:30"
    gps = exif.get_ifd(0x8825)
    gps[1], gps[2], gps[3], gps[4] = "N", (50.0, 5.0, 24.0), "E", (14.0, 25.0, 12.0)
    out = io.BytesIO()
    im.save(out, "JPEG", exif=exif)
    return out.getvalue()


def floorplan_png() -> bytes:
    """A simple floor plan: two labelled rooms."""
    im = Image.new("RGB", (900, 600), "white")
    d = ImageDraw.Draw(im)
    d.rectangle((40, 40, 500, 560), outline="black", width=6)
    d.rectangle((500, 40, 860, 560), outline="black", width=6)
    d.rectangle((490, 250, 510, 340), fill="white")
    d.text((220, 280), "Kuchyn 4.6 x 5.2 m", fill="black")
    d.text((620, 280), "Obyvak 3.6 x 5.2 m", fill="black")
    out = io.BytesIO()
    im.save(out, "PNG")
    return out.getvalue()
