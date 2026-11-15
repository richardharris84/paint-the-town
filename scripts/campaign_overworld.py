"""Original reproducible Toronto pixel-art intermission map, not a street atlas."""

import random
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from build_toronto_wad import _doom_palette, _indexed_canvas, _sprite_patch
from campaign_order import STOPS


from project_paths import ROOT, ART_SOURCES
INK = "#26364b"
CREAM = "#fff0c1"
GOLD = "#ffd45f"
TEAL = "#7bdf53"
NODES = ((75, 62), (128, 64), (219, 84), (150, 103), (171, 133),
         (225, 139), (74, 144), (150, 165), (292, 77))
LABELS = ((40, 65, "ROM"), (103, 70, "QUEENS PK"), (185, 89, "SANKOFA"),
          (110, 108, "CITY HALL"), (146, 139, "UNION"), (210, 146, "ARENA"),
          (39, 148, "ROGERS"), (173, 174, "ISLANDS"), (265, 87, "ZOO"))
GLYPHS = {
    "A": "010101111101101", "B": "110101110101110", "C": "011100100100011",
    "D": "110101101101110", "E": "111100110100111", "F": "111100110100100",
    "G": "011100101101011", "H": "101101111101101", "I": "111010010010111",
    "J": "001001001101010", "K": "101101110101101", "L": "100100100100111",
    "M": "101111111101101", "N": "101111111111101", "O": "010101101101010",
    "P": "110101110100100", "Q": "010101101111011", "R": "110101110101101",
    "S": "011100010001110", "T": "111010010010010", "U": "101101101101111",
    "V": "101101101101010", "W": "101101111111101", "X": "101101010101101",
    "Y": "101101010010010", "Z": "111001010100111",
    "1": "010110010010111", "2": "110001010100111", "3": "110001010001110",
    "4": "101101111001001", "5": "111100110001110", "6": "011100110101010",
    "7": "111001010010010", "8": "010101010101010", "9": "010101011001110",
    " ": "000000000000000", "/": "001001010100100", "-": "000000111000000",
}


def lettering(draw, x, y, text, colour=CREAM):
    for character in text:
        glyph = GLYPHS[character]
        for i, pixel in enumerate(glyph):
            if pixel == "1":
                draw.point((x + i % 3, y + i // 3), fill=colour)
        x += 4


def plaque(draw, x, y, text):
    draw.rectangle((x - 2, y - 2, x + len(text) * 4, y + 6), fill=INK)
    lettering(draw, x, y, text)


def tree(draw, x, y):
    draw.rectangle((x, y, x + 1, y + 7), fill="#785c43")
    draw.ellipse((x - 4, y - 4, x + 5, y + 3), fill=INK)
    draw.ellipse((x - 3, y - 5, x + 4, y + 1), fill="#438657")
    draw.rectangle((x - 2, y - 4, x, y - 2), fill="#9dc56b")


def building(draw, box, roof="#a2c6bd"):
    x, y, w, h = box
    draw.rectangle((x + 2, y + 3, x + w + 2, y + h + 2), fill="#668276")
    draw.rectangle((x, y, x + w, y + h), fill=INK)
    draw.rectangle((x + 1, y + 2, x + w - 1, y + h - 1), fill="#8c9fa1")
    draw.rectangle((x + 1, y + 1, x + w - 1, y + 4), fill=roof)
    for wx in range(x + 3, x + w - 1, 4):
        for wy in range(y + 7, y + h - 1, 4):
            draw.rectangle((wx, wy, wx + 1, wy + 1), fill="#f1d78f")


def landmarks(draw):
    # ROM: original faceted crystal beside its stone heritage wing.
    building(draw, (44, 44, 16, 17), "#e8c793")
    draw.polygon(((57, 57), (54, 46), (65, 38), (72, 43), (77, 59)), fill=INK)
    draw.polygon(((57, 47), (65, 41), (64, 58), (59, 57)), fill="#b9e8e4")
    draw.polygon(((66, 42), (71, 45), (74, 57), (65, 58)), fill="#69aebf")
    draw.line(((65, 41), (69, 54), (74, 57)), fill=CREAM)
    # Queen's Park: red sandstone legislature and green canopy.
    for x, y in ((103, 48), (133, 44), (136, 58), (102, 62)):
        tree(draw, x, y)
    building(draw, (108, 48, 23, 16), "#c68e65")
    draw.rectangle((117, 43, 122, 60), fill=INK)
    draw.polygon(((116, 44), (120, 39), (124, 44)), fill="#c27458")
    draw.rectangle((118, 45, 121, 55), fill="#dda16d")
    draw.rectangle((118, 58, 122, 64), fill="#594959")
    # Sankofa: colourful original billboards, stage and pedestrian plaza.
    draw.rectangle((186, 72, 216, 85), fill="#c9bca1", outline=INK)
    building(draw, (189, 57, 10, 22), "#6f7a94")
    building(draw, (202, 62, 16, 16), "#b0adb3")
    for box, fill in (((190, 62, 197, 70), "#e77bb1"),
                      ((203, 65, 216, 71), "#78d8ce"),
                      ((191, 73, 198, 76), "#ffd06a")):
        draw.rectangle(box, fill=fill)
        draw.line((box[0] + 1, box[1] + 1, box[2] - 1, box[1] + 1), fill=CREAM)
    draw.rectangle((199, 80, 212, 82), fill=INK)
    # City Hall: two curved towers and the reflecting pool.
    draw.ellipse((126, 87, 155, 105), fill="#bab8a5", outline=INK)
    for box in ((128, 79, 137, 98), (145, 77, 154, 97)):
        draw.ellipse(box, fill=INK)
        draw.arc((box[0] + 1, box[1] + 1, box[2] - 1, box[3] - 1),
                 70, 290, fill="#ecddba", width=3)
        for y in range(box[1] + 5, box[3] - 2, 3):
            draw.line((box[0] + 3, y, box[2] - 3, y), fill="#699da4")
    draw.rectangle((136, 100, 147, 103), fill="#5fbdce", outline=INK)
    # Union: long limestone frontage, arches, green copper roof.
    building(draw, (145, 117, 30, 15), "#5b9e8b")
    draw.polygon(((145, 118), (160, 111), (175, 118)), fill=INK)
    draw.line((148, 117, 160, 113, 172, 117), fill="#8dd1b2", width=2)
    for x in range(148, 173, 5):
        draw.rectangle((x, 122, x + 2, 130), fill="#ebd5a5")
        draw.point((x + 1, 125), fill=INK)
    # Arena: low blue glass bowl with ice-blue roof.
    draw.rounded_rectangle((202, 119, 231, 138), radius=5, fill=INK)
    draw.rounded_rectangle((204, 120, 229, 134), radius=4, fill="#7195b4")
    draw.rectangle((209, 123, 224, 129), fill="#c1e6e1", outline="#eaf3dc")
    draw.line((216, 123, 216, 129), fill="#ce8498")
    draw.line((207, 135, 227, 135), fill="#e1c98b")
    # Rogers Centre: open retractable roof and visible baseball diamond.
    draw.ellipse((40, 119, 75, 143), fill=INK)
    draw.ellipse((42, 120, 73, 140), fill="#d2d3bb")
    draw.ellipse((48, 123, 68, 137), fill="#5e9d69", outline=INK)
    draw.polygon(((53, 130), (58, 126), (63, 130), (58, 134)), fill="#d5aa78")
    draw.point((58, 134), fill=CREAM)
    for x in (45, 68):
        draw.arc((x - 2, 122, x + 5, 139), 70, 285, fill="#7998a4", width=2)
    # Contextual CN Tower, intentionally not a playable stop.
    draw.line((96, 142, 96, 108), fill=INK, width=3)
    draw.line((96, 141, 96, 110), fill="#dbd6bc")
    draw.ellipse((91, 116, 101, 121), fill=INK)
    draw.line((92, 117, 100, 117), fill="#cf96aa")
    draw.rectangle((94, 121, 98, 123), fill="#9eafbf")
    # Islands: parkland, boardwalk and a tiny ferry.
    for x, y in ((165, 165), (183, 162), (201, 168)):
        tree(draw, x, y)
    draw.line((155, 172, 197, 172), fill="#efcb90", width=2)
    draw.rectangle((148, 154, 157, 157), fill=CREAM, outline=INK)
    draw.rectangle((151, 152, 155, 153), fill="#e68375")
    # Zoo inset: park gate, polar bear and dinosaur silhouette.
    for x, y in ((257, 59), (301, 60), (260, 78), (303, 80)):
        tree(draw, x, y)
    draw.rectangle((266, 61, 269, 78), fill="#c2a371", outline=INK)
    draw.rectangle((290, 61, 293, 78), fill="#c2a371", outline=INK)
    draw.rectangle((267, 58, 292, 63), fill="#b2c883", outline=INK)
    draw.ellipse((272, 68, 283, 75), fill=CREAM, outline=INK)
    draw.rectangle((273, 74, 275, 78), fill=CREAM)
    draw.rectangle((280, 74, 282, 78), fill=CREAM)
    draw.rectangle((281, 66, 285, 71), fill=CREAM, outline=INK)
    draw.point((284, 68), fill=INK)


@lru_cache(maxsize=1)
def master_map():
    image = Image.new("RGB", (320, 200), "#373baf")
    draw = ImageDraw.Draw(image)
    rng = random.Random(2280)
    for _ in range(190):
        x, y = rng.randrange(320), rng.randrange(200)
        draw.line((x, y, x + 3, y), fill="#7777df")
    coast = ((0, 0), (319, 0), (319, 111), (280, 111), (280, 128),
             (247, 128), (247, 146), (236, 146), (236, 153), (216, 153),
             (216, 149), (180, 149), (180, 146), (135, 146), (135, 151),
             (106, 151), (106, 147), (78, 147), (78, 150), (27, 150),
             (27, 145), (0, 145))
    draw.polygon([(x, y + 4) for x, y in coast], fill=INK)
    draw.polygon([(x, y + 2) for x, y in coast], fill="#e7c696")
    draw.polygon(coast, fill="#81ab5b")
    draw.rectangle((0, 0, 319, 35), fill="#292953")
    # Distant skyline behind native entering/finished headings.
    for x in range(4, 319, 9):
        height = rng.randrange(8, 24)
        draw.rectangle((x, 35 - height, x + 6, 35), fill="#434377")
        draw.line((x + 1, 35 - height, x + 5, 35 - height), fill="#63638f")
    for y in (75, 100, 125):
        draw.line((0, y, 237, y), fill="#738a7b", width=7)
        draw.line((0, y - 1, 237, y - 1), fill="#e1d5b2", width=4)
        for x in range(4, 237, 12):
            draw.line((x, y, x + 3, y), fill="#fff0cc")
    for x in (29, 86, 121, 181, 238):
        draw.line((x, 37, x, 143), fill="#738a7b", width=6)
        draw.line((x - 1, 37, x - 1, 143), fill="#e1d5b2", width=3)
    for box in ((7, 45, 13, 19), (7, 82, 13, 14), (43, 81, 19, 13),
                (157, 45, 14, 23), (157, 81, 16, 14), (8, 109, 13, 22),
                (103, 113, 13, 18), (192, 43, 17, 12), (216, 44, 14, 12)):
        building(draw, box)
    for x, y in ((35, 44), (34, 91), (81, 53), (110, 43), (144, 47),
                 (74, 91), (99, 91), (180, 105), (188, 114), (25, 137),
                 (237, 61), (234, 103), (130, 131), (14, 70), (231, 114)):
        tree(draw, x, y)
    draw.rectangle((250, 42, 314, 101), fill=INK)
    draw.rectangle((252, 44, 312, 99), fill="#7fa474")
    lettering(draw, 258, 47, "NORTHEAST", CREAM)
    lettering(draw, 257, 94, "OFF MAP / NE", CREAM)
    draw.line((241, 53, 248, 53), fill=INK, width=3)
    draw.polygon(((245, 50), (249, 53), (245, 56)), fill=CREAM)
    draw.line((266, 111, 266, 118), fill=INK, width=3)
    draw.polygon(((263, 113), (266, 108), (269, 113)), fill=CREAM)
    lettering(draw, 265, 121, "N")
    draw.polygon(((132, 164), (158, 158), (173, 160), (189, 157),
                  (214, 162), (223, 170), (211, 176), (184, 176),
                  (173, 173), (150, 175), (131, 171)), fill=INK)
    draw.polygon(((135, 164), (158, 160), (174, 162), (190, 159),
                  (212, 164), (219, 170), (209, 173), (184, 174),
                  (173, 171), (150, 173), (134, 169)), fill="#a9c57e")
    for x in range(0, 235, 8):
        draw.line((x, 144, x + 4, 144), fill="#b5ac95")
    draw.rectangle((33, 72, 44, 75), fill="#ce616a", outline=INK)
    draw.line((35, 72, 42, 72), fill=CREAM)
    landmarks(draw)
    for x, y, label in LABELS:
        plaque(draw, x, y, label)
    plaque(draw, 14, 166, "LAKE ONTARIO")
    return image


ROUTES = (
    ((75, 62), (86, 62), (86, 64), (128, 64)),
    ((128, 64), (181, 64), (181, 84), (219, 84)),
    ((219, 84), (181, 84), (181, 103), (150, 103)),
    ((150, 103), (181, 103), (181, 133), (171, 133)),
    ((171, 133), (191, 133), (191, 139), (225, 139)),
    ((225, 139), (239, 151), (106, 151), (74, 144)),
    ((74, 144), (105, 159), (127, 165), (150, 165)),
)


def marker(draw, point, number, completed, next_stop):
    x, y = point
    if completed:
        draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=INK)
        draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=TEAL)
        draw.line((x - 2, y, x, y + 2, x + 3, y - 2), fill=INK, width=1)
    elif next_stop:
        draw.polygon(((x, y - 7), (x + 7, y), (x, y + 7), (x - 7, y)), fill=INK)
        draw.polygon(((x, y - 5), (x + 5, y), (x, y + 5), (x - 5, y)), fill=GOLD)
        lettering(draw, x - 1, y - 2, str(number), INK)
    else:
        draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=INK)
        draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill="#a1b0ae")
        lettering(draw, x - 1, y - 2, str(number), INK)


def stage_image(completed, results=False, handoff=False):
    if not 0 <= completed <= len(STOPS):
        raise ValueError("Completed campaign stages must be between zero and nine")
    image = master_map().copy()
    overlay = Image.new("RGBA", image.size)
    route_draw = ImageDraw.Draw(overlay)
    for i, route in enumerate(ROUTES):
        colour = TEAL if i + 1 < completed else GOLD if i + 1 == completed else "#536a6e"
        route_draw.line(route, fill=INK, width=3)
        route_draw.line(route, fill=colour, width=1)
    # A transport jump, not a geographic line across downtown to the Zoo.
    if completed >= 8:
        route_draw.line(((230, 163), (240, 163), (240, 57)), fill=GOLD, width=1)
        for y in range(59, 161, 6):
            route_draw.line((240, y, 240, y + 2), fill=INK)
    # Routes run below the icons/labels: restore those after compositing.
    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(image)
    landmarks(draw)
    for x, y, label in LABELS:
        plaque(draw, x, y, label)
    for i, point in enumerate(NODES):
        marker(draw, point, i + 1, i < completed, i == completed)
    if results:
        # Preserve readable stock results; keep the map visible underneath.
        image = Image.blend(image, Image.new("RGB", image.size, INK), 0.35)
    else:
        draw.rectangle((0, 182, 319, 199), fill=INK)
        if not handoff:
            marker(draw, (9, 190), 1, True, False)
            lettering(draw, 18, 188, "CLEARED")
            marker(draw, (64, 190), 2, False, True)
            lettering(draw, 74, 188, "NEXT")
            marker(draw, (105, 190), 3, False, False)
            lettering(draw, 114, 188, "AHEAD")
            lettering(draw, 159, 188, "PAINT THE TOWN", TEAL)
            lettering(draw, 235, 188, "NOT TO SCALE")
    palette = Image.new("P", (1, 1))
    palette.putpalette(_doom_palette())
    return _indexed_canvas(image.convert("RGBA"), palette)


@lru_cache(maxsize=1)
def overworld_lumps():
    lumps = []
    for stage in range(1, len(STOPS) + 1):
        lumps.append((f"TRI{stage:02}", _sprite_patch(stage_image(stage - 1), (0, 0))))
        lumps.append((f"TRX{stage:02}", _sprite_patch(stage_image(stage, results=True), (0, 0))))
        font = ImageFont.truetype(r"C:\Windows\Fonts\bahnschrift.ttf", 16)
        title = STOPS[stage - 1].title
        width = round(font.getlength(title)) + 4
        image = Image.new("RGBA", (width, 23))
        ImageDraw.Draw(image).text((2, 0), title, font=font, fill=CREAM,
                                  stroke_width=1, stroke_fill=INK)
        palette = Image.new("P", (1, 1))
        palette.putpalette(_doom_palette())
        lumps.append((f"TRL{stage:02}", _sprite_patch(_indexed_canvas(image, palette), (0, 0))))
    lumps.append(("TRZOO", _sprite_patch(stage_image(8, handoff=True), (0, 0))))
    return tuple(lumps)


def export():
    from build_mod_previews import patch

    output = ART_SOURCES / "overworld"
    output.mkdir(parents=True, exist_ok=True)
    master_map().save(output / "toronto_master.png")
    assets = dict(overworld_lumps())
    contact = Image.new("RGB", (320 * 3, 240 * 3))
    for stage in range(1, 10):
        image = patch(f"TRI{stage:02}", assets).convert("RGB")
        image.save(output / f"entering_{stage:02}.png")
        corrected = image.resize((320, 240), Image.Resampling.NEAREST)
        contact.paste(corrected, (((stage - 1) % 3) * 320, ((stage - 1) // 3) * 240))
    contact.save(output / "campaign_stages.png")
    print(output)


if __name__ == "__main__":
    export()
