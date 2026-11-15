import numpy as np
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from toronto_materials import material_images
from campaign_order import STOPS
from project_paths import ART_SOURCES


CAMPAIGN_SKIES = tuple(stop.sky for stop in STOPS)


def _page_patch(image, palette, offsets=(0, 0)):
    """High-quality fullscreen page: supersampled, then palette-matched clean.

    Zero offsets: KEX and Woof auto-centre fullscreen patches wider than 320,
    and a nonzero left offset double-shifts the page in KEX.
    """
    from build_toronto_wad import _sprite_patch

    indexed = image.convert("RGB").quantize(palette=palette,
                                            dither=Image.Dither.NONE)
    pixels = indexed.tobytes()
    canvas = [list(pixels[row * image.width:(row + 1) * image.width])
              for row in range(image.height)]
    return _sprite_patch(canvas, offsets)


def finale_lumps():
    from build_toronto_wad import _doom_palette

    # Compose every page at double size and widescreen (1120x400 -> 560x200),
    # then downsample and dither, so engines show crisp art edge to edge.
    palette = Image.new("P", (1, 1))
    palette.putpalette(_doom_palette())
    source_path = ART_SOURCES / "expansion_header_source.png"
    teal, gold, cream, lime = ((90, 220, 190), (250, 210, 80),
                               (236, 222, 181), (150, 245, 120))

    def shrink(image):
        return image.resize((560, 200), Image.Resampling.LANCZOS)

    def centered(draw, y, text, size, color, stroke=2):
        font = ImageFont.truetype(str(Path(r"C:\Windows\Fonts\bahnschrift.ttf")), size)
        width = draw.textlength(text, font=font)
        draw.text(((1120 - width) / 2, y), text, font=font, fill=color,
                  stroke_width=stroke, stroke_fill=(10, 18, 24))

    with Image.open(source_path) as source:
        key_art = source.convert("RGB")
    title = shrink(ImageOps.fit(key_art, (1120, 400), Image.Resampling.LANCZOS,
                                centering=(0.5, 0.2)))
    victory = ImageOps.fit(key_art, (1120, 400), Image.Resampling.LANCZOS,
                           centering=(0.5, 0.25))
    draw = ImageDraw.Draw(victory)
    draw.rectangle((0, 320, 1119, 399), fill=(13, 26, 36))
    draw.line((0, 320, 1119, 320), fill=teal, width=2)
    centered(draw, 324, "CAMPAIGN COMPLETE!", 28, gold)
    centered(draw, 354, "THANKS FOR PLAYING", 17, teal)
    centered(draw, 376, "BUILT BY RICHARD HARRIS", 17, cream)
    victory = shrink(victory)
    backdrop = ImageOps.fit(key_art, (1120, 400), Image.Resampling.LANCZOS,
                            centering=(0.5, 0.25))
    backdrop = Image.blend(backdrop, Image.new("RGB", (1120, 400), (10, 22, 32)), 0.74)
    story = backdrop.copy()
    ImageDraw.Draw(story).line((40, 370, 1080, 370), fill=(57, 91, 87), width=2)
    story = shrink(story)
    ready = backdrop.copy()
    draw = ImageDraw.Draw(ready)
    centered(draw, 30, "PAINT THE TOWN", 54, gold)
    centered(draw, 104, "NINE LANDMARKS. ONE COLOURFUL CITY.", 22, teal)
    for y, line in ((162, "CONTROLS:  W A S D  +  MOUSE"),
                    (198, "GRAB THE PORTAL KEY AND HEAD TO THE EXIT!"),
                    (234, "PRESS SPACEBAR TO RESPAWN AFTER DYING"),
                    (270, "PRESS TAB TO VIEW THE MAP")):
        centered(draw, y, line, 21, cream)
    centered(draw, 330, "START A NEW GAME TO OPEN THE FIRST PORTAL", 22, lime)
    ready = shrink(ready)
    pages = [(name, _page_patch(picture, palette))
            for name, picture in (("TRVICTRY", victory), ("TITLEPIC", title),
                                  ("TRSTORY", story), ("PTTREADY", ready))]
    loop = {
        "type": "demoloop", "version": "1.0.0", "metadata": None,
        "data": {"entries": [
            {"primarylump": "TITLEPIC", "secondarylump": "D_E1M1",
             "duration": 2, "type": 0, "outrowipe": 0},
            {"primarylump": "PTTREADY", "secondarylump": None,
             "duration": 30, "type": 0, "outrowipe": 0},
        ]},
    }
    return [*pages, *menu_lumps(), ("DEMOLOOP", json.dumps(loop).encode("ascii"))]


def menu_lumps():
    """Original menu graphics: no stock red Doom text survives in our menus."""
    from build_toronto_wad import _doom_palette, _indexed_canvas, _sprite_patch

    palette = Image.new("P", (1, 1))
    palette.putpalette(_doom_palette())
    cream, dark = (236, 222, 181), (14, 35, 38)
    with Image.open(ART_SOURCES / "expansion_header_source.png") as source:
        logo = source.convert("RGBA").crop((470, 10, 1190, 340))
    logo = ImageOps.contain(logo, (220, 72), Image.Resampling.LANCZOS)
    images = {"M_DOOM": logo}
    labels = {
        "M_NEWG": "NEW GAME", "M_OPTION": "OPTIONS", "M_LOADG": "LOAD GAME",
        "M_SAVEG": "SAVE GAME", "M_RDTHIS": "HOW TO PLAY", "M_QUITG": "QUIT",
        "M_EPISOD": "PAINT THE TOWN", "M_EPI1": "TORONTO CAMPAIGN",
        "M_SKILL": "CHOOSE YOUR INTENSITY",
        "M_JKILL": "JUST SPLASHING.", "M_ROUGH": "EASY DOES IT.",
        "M_HURT": "PAINT ME PLENTY.", "M_ULTRA": "SERIOUS SPLATTER!",
        "M_NMARE": "TOTAL CHAOS!", "M_PAUSE": "PAUSED",
    }
    for name, text in labels.items():
        font = ImageFont.truetype(r"C:\Windows\Fonts\bahnschrift.ttf", 15)
        image = Image.new("RGBA", (round(font.getlength(text)) + 5, 19))
        ImageDraw.Draw(image).text((2, -1), text, font=font, fill=cream,
                                   stroke_width=1, stroke_fill=dark)
        images[name] = image
    for name, color in (("M_SKULL1", (90, 220, 190)), ("M_SKULL2", (255, 150, 60))):
        pointer = Image.new("RGBA", (16, 18))
        draw = ImageDraw.Draw(pointer)
        draw.ellipse((2, 4, 13, 15), fill=color)
        for dx, dy in ((7, 0), (14, 8), (7, 16), (0, 9), (12, 2), (2, 2)):
            draw.ellipse((dx, dy, dx + 3, dy + 3), fill=color)
        images[name] = pointer
    return [(name, _sprite_patch(_indexed_canvas(image, palette), (0, 0)))
            for name, image in images.items()]


SKY_STRIPS = (
    ("skies_squares.png", (("TSKYSAN", 345), ("TSKYNAT", 690), ("TSKYROG", 1024))),
    ("skies_waterfront.png", (("TSKYSCO", 337), ("TSKYQPK", 679), ("TSKYISL", 1024))),
)


def venue_skies(palette):
    """Original AI panorama strips; not photographic venue surveys."""
    from project_paths import ASSETS
    from toronto_materials import _tile_edges

    skies = {}
    for filename, strips in SKY_STRIPS:
        with Image.open(ASSETS / filename) as source:
            image = source.convert("RGB")
        if image.size != (1536, 1024):
            raise ValueError(f"{filename}: dimensions changed; review the strip crop bounds")
        for name, bottom in strips:
            # Each reviewed 8:1 window ends at its strip's skyline base, above any divider,
            # so the 1024x128 native sky keeps correct building proportions.
            strip = image.crop((0, bottom - 192, image.width, bottom))
            pixels = np.array(strip, dtype=np.float64)
            blue = (pixels[:, :, 2] > pixels[:, :, 0] + 10) & (pixels[:, :, 2] > pixels[:, :, 1] + 8)
            grey = pixels @ np.array([0.299, 0.587, 0.114])
            # PLAYPAL's lavender ramp cannot represent daylight blue. Grade only the
            # open sky toward natural overcast grey, retaining dusk and foliage colour.
            pixels[blue] = pixels[blue] * 0.15 + grey[blue, None] * 0.85
            strip = Image.fromarray(np.rint(pixels).astype(np.uint8))
            strip = strip.resize((1024, 128), Image.Resampling.LANCZOS)
            if name == "TSKYNAT":
                # Yaw the panorama 45 degrees so the curved city-hall towers sit
                # directly behind the circular tower lobby on the map.
                strip = Image.fromarray(np.roll(np.asarray(strip), 128, axis=1))
            # A wrap blend prevents an obvious panorama seam at the camera yaw boundary.
            skies[name] = _tile_edges(strip, False).quantize(palette=palette, dither=Image.Dither.NONE)
    return skies


def candidate_material_images(palette_bytes):
    walls, flats = material_images(palette_bytes)
    palette = Image.new("P", (1, 1))
    palette.putpalette(palette_bytes)
    walls.update(venue_skies(palette))

    def indexed(image):
        result = image.convert("RGB").quantize(palette=palette, dither=Image.Dither.NONE)
        if image.mode == "RGBA":
            alpha = image.getchannel("A").tobytes()
            used = {pixel for pixel, opacity in zip(result.tobytes(), alpha) if opacity}
            free = next((index for index in range(256) if index not in used), None)
            if free is None:
                raise ValueError("Masked material needs one unused transparent palette index")
            result.frombytes(bytes(pixel if opacity else free
                                   for pixel, opacity in zip(result.tobytes(), alpha)))
            result.info["transparency"] = free
        return result

    from venue_scenery import material_images as scenery_material_images
    scenery_walls, scenery_flats = scenery_material_images()
    walls.update({name: indexed(image) for name, image in scenery_walls.items()})
    flats.update({name: indexed(image) for name, image in scenery_flats.items()})
    from venue_art import material, site_material
    lake = material(10, (64, 64))
    flats["ISLLAKE"] = indexed(lake)

    def fabric(color):
        rng = np.random.default_rng(814)
        pixels = np.clip(np.array(color)[None, None, :] + rng.integers(-10, 11, (128, 128, 1)), 0, 255)
        image = Image.fromarray(pixels.astype(np.uint8))
        draw = ImageDraw.Draw(image)
        draw.line((5, 0, 5, 128), fill=tuple(round(c * 0.6) for c in color), width=2)
        draw.line((122, 0, 122, 128), fill=tuple(round(c * 1.12) for c in color), width=2)
        for y in range(0, 128, 8):
            draw.line((6, y, 7, y + 3), fill=(170, 170, 150))
        return indexed(image)

    walls["PBTEAL"], walls["PBORANGE"] = fabric((25, 115, 115)), fabric((180, 95, 25))
    door = site_material("materials_arena.png", 7)
    draw = ImageDraw.Draw(door)
    walls["PBKEYIN"] = indexed(door.copy())
    bold = ImageFont.truetype(str(Path(r"C:\Windows\Fonts\bahnschrift.ttf")), 25)
    small = ImageFont.truetype(str(Path(r"C:\Windows\Fonts\bahnschrift.ttf")), 11)
    draw.rectangle((4, 8, 123, 116), fill=(25, 40, 91), outline=(225, 195, 40), width=3)
    draw.text((35, 13), "EXIT", font=bold, fill=(239, 239, 214))
    draw.text((16, 43), "BLUE KEY ACCESS", font=small, fill=(171, 201, 231))
    draw.rectangle((14, 62, 54, 102), fill=(16, 24, 30), outline=(132, 149, 160), width=2)
    draw.rectangle((20, 67, 48, 74), fill=(57, 174, 122))
    for y in (80, 87, 94):
        for x in (22, 32, 42):
            draw.rectangle((x, y, x + 4, y + 3), fill=(204, 211, 202))
    draw.rectangle((77, 63, 91, 103), fill=(10, 16, 23), outline=(125, 146, 162), width=2)
    draw.rounded_rectangle((81, 69, 96, 95), radius=3, fill=(209, 211, 191))
    draw.text((62, 105), "USE", font=small, fill=(242, 222, 85))
    walls["PBKEYDR"] = indexed(door)
    flats["PBTEALF"] = walls["PBTEAL"].resize((64, 64), Image.Resampling.NEAREST)
    flats["PBORNGF"] = walls["PBORANGE"].resize((64, 64), Image.Resampling.NEAREST)
    flats["PBFILL"] = indexed(Image.new("RGB", (64, 64), (21, 33, 39)))
    walls["STADWALL"] = indexed(site_material("materials_arena.png", 0))
    flats["STADGRAS"], flats["STADDIRT"] = flats["ZFGRASS"].copy(), flats["ZFEARTH"].copy()
    rng = np.random.default_rng(719)
    flats["RINKICE"] = indexed(site_material("materials_arena.png", 3, (64, 64)))
    walls["RINKBRDS"] = indexed(site_material("materials_arena.png", 2, vertical=False))
    seats = site_material("materials_arena.png", 1)
    walls["RINKSEAT"] = indexed(seats)
    flats["RINKSEAF"] = indexed(seats.resize((64, 64), Image.Resampling.LANCZOS))
    flats["RINKROOF"] = indexed(site_material("materials_arena.png", 4, (64, 64)))
    flats["NFTFOUNT"] = flats["UFPLAZA"].copy()
    flats["NFPOOL"] = indexed(Image.new("RGB", (64, 64), (89, 113, 120)))
    sand = np.clip(np.array((166, 147, 104))[None, None, :]
                   + rng.integers(-14, 15, (64, 64, 1)), 0, 255).astype(np.uint8)
    flats["BEACHSND"] = indexed(Image.fromarray(sand))
    for name, color in (("SPORTWH", (220, 220, 205)), ("SPORTRED", (157, 35, 31)),
                        ("SPORTBLU", (38, 42, 119))):
        pixels = np.clip(np.array(color)[None, None, :]
                         + rng.integers(-5, 6, (64, 64, 1)), 0, 255).astype(np.uint8)
        flats[name] = indexed(Image.fromarray(pixels))
    return walls, flats
