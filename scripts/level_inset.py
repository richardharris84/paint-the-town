"""Static level plans selected by silent, level-local unused key markers."""

from PIL import Image, ImageDraw


MARKER_ITEMS = (2, 3, 5, 6)
MARKER_DOOMEDNUM = 15300
MARKER_THING = 230
WIDTH, HEIGHT = 86, 30


def selector(level):
    if level not in range(1, 10):
        raise ValueError(f"Invalid campaign level: {level}")
    return [{"condition": 10 if level & (1 << bit) else 11, "param": item}
            for bit, item in enumerate(MARKER_ITEMS)]


def place_markers(geometry, level, position):
    for bit in range(4):
        if level & (1 << bit):
            geometry.thing(*position, MARKER_DOOMEDNUM + bit)


def gameplay_patch():
    lines = []
    for bit, item in enumerate(MARKER_ITEMS):
        lines.extend((f"Thing {MARKER_THING + bit}", f"ID # = {MARKER_DOOMEDNUM + bit}",
                      "Initial frame = 2500", "Hit points = 1", "Width = 1048576",
                      "Height = 1048576", "Bits = 1", f"Pickup item type = {item}",
                      "Pickup bonus count = 0", "Pickup sound = 0",
                      "Pickup message = USER_TRMAPMARK", ""))
    lines.extend(("[STRINGS]", "USER_TRMAPMARK = ", ""))
    return "\n".join(lines)


def image(spec):
    venue = spec.compile()
    result = Image.new("RGBA", (WIDTH, HEIGHT), (21, 33, 39, 255))
    draw = ImageDraw.Draw(result)
    xmin, ymin, xmax, ymax = spec.footprint.bounds
    scale = min((WIDTH - 8) / (xmax - xmin), (HEIGHT - 6) / (ymax - ymin))
    ox = (WIDTH - (xmax - xmin) * scale) / 2
    oy = (HEIGHT - (ymax - ymin) * scale) / 2

    def point(x, y):
        return round(ox + (x - xmin) * scale), round(oy + (ymax - y) * scale)

    vertices = venue.geometry.vertices
    for a, b, _, _, _, front, back in venue.geometry.lines:
        draw.line((*point(*vertices[a]), *point(*vertices[b])),
                  fill=(222, 209, 171) if back < 0 else (85, 121, 104))
    x, y = point(*spec.start)
    draw.point((x, y), fill=(240, 185, 70))
    # North is fixed, not a claim of live heading or player tracking.
    draw.rectangle((WIDTH - 10, 0, WIDTH - 1, 10), fill=(21, 33, 39))
    draw.polygon(((WIDTH - 6, 1), (WIDTH - 2, 5), (WIDTH - 5, 5),
                  (WIDTH - 5, 9), (WIDTH - 7, 9), (WIDTH - 7, 5),
                  (WIDTH - 10, 5)), fill=(255, 239, 183))
    return result
