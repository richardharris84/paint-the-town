"""Project-owned status digits and portraits adapted from the supplied sheet."""

from collections import deque
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from project_paths import ART_SOURCES


# Doom has no cyan/teal ramp; this blue-green target resolves to its light green.
TEAL = (70, 170, 145)
CREAM = (236, 222, 181)
# In-game messages/tips use the HUD's vibrant lime so they pop on any scene.
LIME = (128, 255, 96)
DIGITS = {
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"),
    "7": ("111", "001", "010", "010", "010"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "111"),
    "%": ("101", "001", "010", "100", "101"),
    "-": ("000", "000", "111", "000", "000"),
}
PIXEL_LETTERS = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("111", "010", "010", "010", "010", "010", "111"),
    "J": ("00111", "00010", "00010", "00010", "10010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
}
COMPACT_LETTERS = {
    "B": ("110", "101", "110", "101", "110"),
    "H": ("101", "101", "111", "101", "101"),
    "I": ("111", "010", "010", "010", "111"),
    "L": ("100", "100", "100", "100", "111"),
    "N": ("101", "111", "111", "111", "101"),
    "O": ("010", "101", "101", "101", "010"),
    "P": ("110", "101", "110", "100", "100"),
    "T": ("111", "010", "010", "010", "010"),
    "U": ("101", "101", "101", "101", "111"),
    "M": ("101", "111", "111", "101", "101"),
    "A": ("010", "101", "111", "101", "101"),
    "R": ("110", "101", "110", "101", "101"),
    "K": ("101", "101", "110", "101", "101"),
    "E": ("111", "100", "110", "100", "111"),
    "S": ("011", "100", "010", "001", "110"),
}


def pixel_text(text, color=CREAM, *, compact=False):
    """Draw binary-alpha glyphs at native resolution, without dropping thin strokes."""
    images = []
    for character in text:
        if character == " ":
            images.append(Image.new("RGBA", (3, 7)))
            continue
        rows = COMPACT_LETTERS[character] if compact else PIXEL_LETTERS.get(character)
        if rows is None and character in DIGITS:
            rows = DIGITS[character]
        if rows is None:
            punctuation = {
                "!": ("1", "1", "1", "1", "1", "0", "1"),
                ":": ("0", "1", "0", "0", "1", "0", "0"),
                ".": ("0", "0", "0", "0", "0", "0", "1"),
                ",": ("00", "00", "00", "00", "00", "01", "10"),
                "'": ("1", "1", "0", "0", "0", "0", "0"),
                "/": ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
                "(": ("01", "10", "10", "10", "10", "10", "01"),
                ")": ("10", "01", "01", "01", "01", "01", "10"),
                "?": ("111", "001", "001", "010", "010", "000", "010"),
                "\"": ("101", "101", "000", "000", "000", "000", "000"),
                "#": ("01010", "11111", "01010", "01010", "11111", "01010", "00000"),
                "$": ("00100", "01111", "10100", "01110", "00101", "11110", "00100"),
                "&": ("01100", "10010", "10100", "01000", "10101", "10010", "01101"),
                "*": ("00000", "10101", "01110", "11111", "01110", "10101", "00000"),
                "+": ("000", "010", "010", "111", "010", "010", "000"),
                ";": ("00", "01", "00", "00", "01", "01", "10"),
                "<": ("001", "010", "100", "100", "100", "010", "001"),
                "=": ("000", "000", "111", "000", "111", "000", "000"),
                ">": ("100", "010", "001", "001", "001", "010", "100"),
                "@": ("01110", "10001", "10111", "10101", "10111", "10000", "01110"),
                "[": ("11", "10", "10", "10", "10", "10", "11"),
                "\\": ("10000", "01000", "01000", "00100", "00010", "00010", "00001"),
                "]": ("11", "01", "01", "01", "01", "01", "11"),
                "^": ("010", "101", "000", "000", "000", "000", "000"),
                "_": ("00000", "00000", "00000", "00000", "00000", "00000", "11111"),
            }
            rows = punctuation[character]
        image = Image.new("RGBA", (len(rows[0]), 7))
        draw = ImageDraw.Draw(image)
        for y, row in enumerate(rows):
            for x, bit in enumerate(row):
                if bit == "1":
                    draw.point((x, y), fill=color)
        images.append(image)
    result = Image.new("RGBA", (max(1, sum(im.width + 1 for im in images)), 8))
    x = 0
    for image in images:
        result.alpha_composite(image, (x, 0))
        x += image.width + 1
    return result
FACE_BOUNDS = (
    (66, 32, 438, 508), (526, 32, 910, 508), (1000, 32, 1382, 508),
    (66, 540, 438, 1024), (526, 540, 910, 1024), (1000, 540, 1382, 1024),
)


def digit_image(character, color=TEAL):
    image = Image.new("RGBA", (7, 11))
    draw = ImageDraw.Draw(image)
    for y, row in enumerate(DIGITS[character]):
        for x, bit in enumerate(row):
            if bit == "1":
                draw.rectangle((x * 2 + 1, y * 2 + 1, x * 2 + 2, y * 2 + 2),
                               fill=(14, 35, 38))
                draw.rectangle((x * 2, y * 2, x * 2 + 1, y * 2 + 1), fill=color)
    return image


@lru_cache(maxsize=1)
def portraits():
    with Image.open(ART_SOURCES / "player-face-sharp-source.png") as source:
        crops = [source.convert("RGBA").crop(bounds) for bounds in FACE_BOUNDS]
    result = []
    for image in crops:
        pixels = image.load()
        width, height = image.size
        pending = deque([(x, 0) for x in range(width)] +
                        [(0, y) for y in range(height)] +
                        [(width - 1, y) for y in range(height)])
        seen = set()
        while pending:
            x, y = pending.popleft()
            if (x, y) in seen or not (0 <= x < width and 0 <= y < height):
                continue
            seen.add((x, y))
            r, g, b, _ = pixels[x, y]
            if max(r, g, b) - min(r, g, b) > 27 or max(r, g, b) > 110:
                continue
            pixels[x, y] = (0, 0, 0, 0)
            pending.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))
        image = image.resize((24, 30), Image.Resampling.LANCZOS)
        alpha = image.getchannel("A")
        image = ImageEnhance.Contrast(image.convert("RGB")).enhance(1.15).convert("RGBA")
        image = image.filter(ImageFilter.UnsharpMask(radius=.55, percent=125, threshold=2))
        image.putalpha(alpha)
        alpha = image.getchannel("A").point(lambda value: 255 if value >= 128 else 0)
        outline = alpha.filter(ImageFilter.MaxFilter(3))
        canvas = Image.new("RGBA", (26, 32))
        canvas.paste((10, 17, 22, 255), (1, 1, 25, 31), outline)
        image.putalpha(alpha)
        canvas.alpha_composite(image, (1, 1))
        result.append(canvas)
    return tuple(result)


@lru_cache(maxsize=1)
def face_images():
    neutral, glance, angry, wink, hurt, critical = portraits()
    result = {}
    for tier, base in enumerate((neutral, glance, angry, hurt, critical)):
        # Native face selection has eight expressions per pain tier.
        left = ImageChops.offset(base, -1, 0)
        right = ImageChops.offset(base, 1, 0)
        for expression, image in (
            ("ST0", base), ("ST1", left), ("ST2", right),
            ("TL0", ImageOps.mirror(glance if tier < 2 else base)),
            ("TR0", glance if tier < 2 else base),
            ("OUCH", hurt if tier < 4 else critical),
            ("EVL", wink if tier < 3 else base),
            ("KILL", angry if tier < 3 else base),
        ):
            suffix = f"ST{tier}{expression[-1]}" if expression.startswith("ST") else (
                f"{expression[:2]}{tier}0" if expression in ("TL0", "TR0") else f"{expression}{tier}")
            result[f"STF{suffix}"] = image.copy()
    god = neutral.copy()
    draw = ImageDraw.Draw(god)
    draw.line((2, 1, 23, 1), fill=CREAM, width=1)
    result["STFGOD0"] = god
    result["STFDEAD0"] = Image.blend(critical, ImageOps.grayscale(critical).convert("RGBA"), .65)
    result["STFDEAD0"].putalpha(critical.getchannel("A"))
    return result


def hud_art_lumps():
    from build_toronto_wad import _doom_palette, _indexed_canvas, _sprite_patch

    palette = Image.new("P", (1, 1))
    palette.putpalette(_doom_palette())
    images = {f"TRNNUM{character}": digit_image(character) for character in "0123456789"}
    images.update(TRNPRCNT=digit_image("%"), TRNMINUS=digit_image("-"))
    images.update(face_images())
    images.update(transition_images())
    for slot in (2, 3, 4):
        images[f"TRON{slot}"] = digit_image(str(slot))
        images[f"TROWN{slot}"] = digit_image(str(slot), CREAM)
        images[f"TROFF{slot}"] = digit_image(str(slot), (45, 54, 57))
    return [(name, _sprite_patch(_indexed_canvas(image, palette), (0, 0)))
            for name, image in images.items()]


def transition_images():
    images = {f"WINUM{character}": digit_image(character) for character in "0123456789"}
    images.update(WIPCNT=digit_image("%"), WIMINUS=digit_image("-"))
    labels = {
        "WIF": "FINISHED!", "WIENTER": "ENTERING", "WIOSTK": "HITS",
        "WIOSTI": "ITEMS", "WIOSTS": "SECRETS", "WISCRT2": "SECRETS",
        "WITIME": "TIME", "WIPAR": "PAR", "WIMSTT": "TOTAL",
        "WIFRGS": "FRAGS", "WIKILRS": "HITS", "WIVCTMS": "PLAYERS",
        "WISUCKS": "KEEP PAINTING",
    }
    for name, text in labels.items():
        font = ImageFont.truetype(r"C:\Windows\Fonts\bahnschrift.ttf",
                                 12 if name in {"WIF", "WIENTER"} else 10)
        image = Image.new("RGBA", (round(font.getlength(text)) + 3, 16))
        ImageDraw.Draw(image).text((1, -1), text, font=font, fill=CREAM,
                                  stroke_width=1, stroke_fill=(14, 35, 38))
        images[name] = image
    colon = Image.new("RGBA", (4, 11))
    draw = ImageDraw.Draw(colon)
    for y in (3, 7):
        draw.rectangle((1, y, 2, y + 1), fill=TEAL)
    images["WICOLON"] = colon
    for code in range(33, 96):
        # Tips and pickup messages render in vibrant lime, matching the HUD.
        images[f"STCFN{code:03}"] = pixel_text(chr(code), LIME)
    return images
