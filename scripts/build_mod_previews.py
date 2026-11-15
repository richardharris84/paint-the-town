import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from build_toronto_wad import MAPS, _doom_palette
from toronto_materials import zone_for


from project_paths import ROOT
OUTPUT = ROOT / "mod_preview"
SIZE = (1920, 1080)
INK = "#101b29"
WHITE = "#f3f5ef"
MUTED = "#a9bbca"
TEAL = "#60dfcb"
ORANGE = "#ffb36b"


def font(size, bold=False):
    return ImageFont.truetype(
        str(Path(r"C:\Windows\Fonts") / ("bahnschrift.ttf" if bold else "segoeui.ttf")), size
    )


def read_lumps():
    data = (ROOT / "Toronto_Realms_three_map_backup.wad").read_bytes()
    _, count, offset = struct.unpack_from("<4sii", data)
    lumps = {}
    for index in range(count):
        start, size, name = struct.unpack_from("<ii8s", data, offset + index * 16)
        lumps[name.rstrip(b"\0").decode("ascii")] = data[start:start + size]
    return lumps


LUMPS = read_lumps()
PALETTE = _doom_palette()


def patch(name, lumps=None):
    data = (LUMPS if lumps is None else lumps)[name]
    width, height = struct.unpack_from("<2h", data)
    indexed = Image.new("P", (width, height))
    indexed.putpalette(PALETTE)
    alpha = Image.new("L", (width, height))
    for x in range(width):
        cursor = struct.unpack_from("<I", data, 8 + x * 4)[0]
        while data[cursor] != 255:
            top, length = data[cursor:cursor + 2]
            for dy in range(length):
                indexed.putpixel((x, top + dy), data[cursor + 3 + dy])
                alpha.putpixel((x, top + dy), 255)
            cursor += length + 4
    result = indexed.convert("RGBA")
    result.putalpha(alpha)
    return result


def flat(name):
    image = Image.frombytes("P", (64, 64), LUMPS[name])
    image.putpalette(PALETTE)
    return image.convert("RGBA")


def text(image, xy, value, size, color=WHITE, bold=False):
    ImageDraw.Draw(image).text(xy, value, font=font(size, bold), fill=color)


def base(kicker, title, subtitle):
    image = Image.new("RGB", SIZE, INK)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 18, 1079), fill=TEAL)
    text(image, (64, 36), kicker, 23, TEAL, True)
    text(image, (60, 78), title, 70, bold=True)
    text(image, (64, 172), subtitle, 26, MUTED)
    draw.line((64, 1018, 1856, 1018), fill="#314558", width=2)
    text(image, (64, 1033), "PAINT THE TOWN  /  TORONTO, CANADA", 20, TEAL, True)
    text(image, (1130, 1033), "ACTUAL WAD ASSETS  |  NOT A GAMEPLAY SCREENSHOT", 19, MUTED)
    return image


def paste_fit(image, subject, box, crop_alpha=True):
    if crop_alpha:
        bounds = subject.getbbox()
        if bounds is None:
            raise ValueError("Empty preview subject")
        subject = subject.crop(bounds)
    x, y, width, height = box
    subject = ImageOps.contain(subject, (width, height), Image.Resampling.NEAREST)
    image.paste(subject, (x + (width - subject.width) // 2, y + height - subject.height), subject)


def texture_card(image, name, title, box, floor=False):
    x, y, width, height = box
    texture = flat(name) if floor else patch(name)
    image.paste(texture.resize((width, height - 58), Image.Resampling.NEAREST), (x, y))
    ImageDraw.Draw(image).rectangle((x, y + height - 58, x + width, y + height), fill="#223244")
    text(image, (x + 18, y + height - 45), title, 24)


def cover(header=False):
    source = OUTPUT / "header_art_source.png"
    if header and source.is_file():
        with Image.open(source) as image:
            return ImageOps.fit(image.convert("RGB"), SIZE, method=Image.Resampling.LANCZOS)
    image = base(
        "THREE TORONTO-INSPIRED MAPS",
        "TORONTO REALMS",
        "Animal rivals. Paintball markers. An original industrial soundtrack.",
    )
    labels = ("UNION STATION", "ROYAL ONTARIO MUSEUM", "TORONTO ZOO")
    names = ("UWZUMBR", "RWLIMES", "ZWSTONE")
    sprites = ("DRONO0", "DINOO0", "BEARO0")
    for i, (name, label, sprite) in enumerate(zip(names, labels, sprites)):
        x = 64 + i * 602
        tile = patch(name).convert("RGB").resize((578, 490), Image.Resampling.NEAREST)
        tile = Image.blend(tile, Image.new("RGB", tile.size, INK), 0.55)
        image.paste(tile, (x, 262))
        ImageDraw.Draw(image).rectangle((x, 262, x + 578, 269), fill=TEAL if i != 1 else ORANGE)
        paste_fit(image, patch(sprite), (x + 90, 300, 398, 394))
        text(image, (x + 20, 708), label, 25, bold=True)
    text(image, (64, 804), "PAINTBALL EDITION", 58, TEAL, True)
    text(image, (68, 895), "Raccoon rivals  /  Location-specific enemies  /  Three marker tiers", 30)
    if header:
        # A separately composed, wider visual focus rather than a renamed cover.
        image = base("TORONTO REALMS", "PAINT THE CITY", "Union Station  /  Royal Ontario Museum  /  Toronto Zoo")
        for i, name in enumerate(("TSKYUNI", "TSKYROM", "TSKYZOO")):
            sky = patch(name).convert("RGB").resize((580, 280), Image.Resampling.LANCZOS)
            image.paste(sky, (64 + i * 602, 260))
        for i, name in enumerate(("DRONO0", "DINOO0", "BEARO0")):
            paste_fit(image, patch(name), (140 + i * 600, 440, 390, 438))
        text(image, (64, 920), "THREE MAPS. ORIGINAL BEATS. COLOURFUL ANIMAL RIVALS.", 37, TEAL, True)
    return image


def floorplan(image, spec, box):
    x, y, size = box
    step = size // max(spec["rows"], spec["cols"])
    reach = {spec["start"]}
    for _ in range(spec["rows"] * spec["cols"]):
        for a, b in spec["open"]:
            if a in reach or b in reach:
                reach.update((a, b))
    draw = ImageDraw.Draw(image)
    for row, col in sorted(reach):
        zone = zone_for(spec["name"], row, col)
        cell = flat(zone.floor).resize((step - 8, step - 8), Image.Resampling.NEAREST)
        xx, yy = x + col * step, y + (spec["rows"] - 1 - row) * step
        image.paste(cell, (xx + 4, yy + 4))
    for a, b in spec["open"]:
        r1, c1 = a
        r2, c2 = b
        p1 = (x + c1 * step + step // 2, y + (spec["rows"] - 1 - r1) * step + step // 2)
        p2 = (x + c2 * step + step // 2, y + (spec["rows"] - 1 - r2) * step + step // 2)
        draw.line((*p1, *p2), fill=TEAL, width=5)
    row, col = spec["start"]
    xx, yy = x + col * step + step // 2, y + (spec["rows"] - 1 - row) * step + step // 2
    draw.ellipse((xx - 12, yy - 12, xx + 12, yy + 12), fill=ORANGE)


def location(index):
    spec = MAPS[index]
    captions = (
        "Warm heritage stone, marble floors, modern concourses and platform corridors.",
        "Heritage limestone, contemporary metal, marble geometry and gold mosaic.",
        "Woodland trails, habitat-side materials and green-framed pavilion glazing.",
    )
    samples = (
        (("UWZUMBR", "Great Hall stone", False), ("UFMARBL", "Herringbone marble", True),
         ("UWCONCR", "Concourse panels", False), ("UFPLAZA", "Plaza paving", True)),
        (("RWLIMES", "Rotunda limestone", False), ("RFMARBL", "Marble floor", True),
         ("RWMETAL", "Crystal metalwork", False), ("RFGOLD", "Mosaic ceiling", True)),
        (("ZWSTONE", "Fieldstone", False), ("ZFASPH", "Visitor paths", True),
         ("ZWCEDAR", "Cedar surfaces", False), ("ZWGLASS", "Pavilion glazing", False)),
    )
    image = base(f"{spec['name']}  /  MAP & MATERIAL SHOWCASE", spec["title"].upper(), captions[index])
    floorplan(image, spec, (64, 278, 570))
    text(image, (64, 888), "PLAYABLE LAYOUT", 28, TEAL, True)
    text(image, (64, 932), "Inspired layout, not a scale survey", 23, MUTED)
    for i, (name, title, is_flat) in enumerate(samples[index]):
        texture_card(image, name, title, (690 + i % 2 * 330, 268 + i // 2 * 343, 304, 316), is_flat)
    paste_fit(image, patch(("DRONE0", "DINOE0", "BEARE0")[index]), (1400, 270, 420, 300))
    text(image, (1410, 580), ("TRANSIT DRONE", "DINOSAUR SKELETON", "POLAR BEAR")[index], 25, TEAL, True)
    paste_fit(image, patch(("PIGEE0", "ARMRE0", "WOLFE0")[index]), (1400, 635, 420, 260))
    text(image, (1410, 916), ("ARMOURED PIGEON", "MEDIEVAL ARMOUR", "ARCTIC WOLF")[index], 25, TEAL, True)
    return image


def cast():
    image = base("CHARACTER & EQUIPMENT SHOWCASE", "MEET THE PAINTBALL CREW", "Raccoon gunners on every map. Two exclusive enemy types at each location.")
    for i, (actor, label, weapon) in enumerate(zip(
        ("POSSV0", "DINOO0", "BEARO0"),
        ("BASIC RACCOON GUNNER", "DINOSAUR SKELETON", "POLAR BEAR"),
        ("PISGA0", "SHTGA0", "CHGGA0"),
    )):
        x = 64 + i * 602
        ImageDraw.Draw(image).rounded_rectangle((x, 260, x + 578, 976), radius=20, fill="#223244")
        paste_fit(image, patch(actor), (x + 110, 292, 358, 344))
        text(image, (x + 24, 663), label, 31, TEAL, True)
        # Show original gun bodies without stretching the continued sleeves.
        paste_fit(image, patch(weapon).crop((0, 0, 160, 112)), (x + 170, 730, 238, 170))
        text(image, (x + 24, 926), ("STARTER MARKER", "PUMP MARKER", "AUTOMATIC MARKER")[i], 26)
    return image


def main():
    from build_expansion_previews import build

    build(OUTPUT)
    build(OUTPUT / "expansion")
    for name in ("03_union_station.png", "04_royal_ontario_museum.png",
                 "05_toronto_zoo.png", "06_characters_and_markers.png"):
        obsolete = OUTPUT / name
        if obsolete.is_file():
            obsolete.unlink()


if __name__ == "__main__":
    main()
