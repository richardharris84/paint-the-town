"""Original landmark materials and noninteractive, campaign-only decorations."""

from dataclasses import asdict, dataclass
from functools import lru_cache
import json
import math
from pathlib import Path
import struct

from PIL import Image, ImageDraw, ImageFont, ImageOps


@dataclass(frozen=True)
class Decoration:
    title: str
    prefix: str
    width: int
    height: int
    kind: str
    frame_tics: tuple[int, ...] = (-1,)
    fullbright: bool = False

    @property
    def index(self):
        return DECORATIONS.index(self)

    @property
    def doomednum(self):
        return 15200 + self.index

    @property
    def thing(self):
        return 200 + self.index if self.index < 19 else 300 + self.index - 19

    @property
    def state(self):
        if self.index >= 35:
            return 8200 + (self.index - 35) * 64
        if self.index >= 19:
            return 6000 + (self.index - 19) * 64
        return 3000 + self.index if self.index < 9 else 3200 + (self.index - 9) * 32

    @property
    def sprite(self):
        return 240 + self.index if self.index < 19 else 300 + self.index - 19

    @property
    def directional(self):
        return self.kind in DIRECTIONAL_KINDS or self.kind.startswith("fans")


DECORATIONS = (
    Decoration("Ancient ceramic amphora", "VAMP", 32, 48, "vase"),
    Decoration("Carved historical figure", "VFIG", 40, 88, "figure"),
    Decoration("Mineral specimen on display pedestal", "VGEM", 48, 72, "mineral"),
    Decoration("Fossil exhibit", "VFOS", 128, 96, "fossil"),
    Decoration("Broad maple tree", "VTRE", 192, 240, "maple"),
    Decoration("Tall oak tree", "VOAK", 160, 248, "oak"),
    Decoration("Evergreen tree", "VPIN", 144, 240, "pine"),
    Decoration("Stage speaker stack", "VSPK", 48, 88, "speaker"),
    Decoration("Platform number sign", "VPLT", 64, 104, "platform"),
    Decoration("Puck-drop referee", "VREF", 80, 64, "referee", (18, 18, 18, 18)),
    Decoration("Pitcher set to throw", "VPIT", 80, 64, "pitcher"),
    Decoration("Elephant", "VELE", 128, 104, "elephant", (35, 35)),
    Decoration("Giraffe", "VGIR", 128, 176, "giraffe", (35, 35)),
    Decoration("White-tailed deer", "VDEE", 72, 64, "deer", (35, 35)),
    Decoration("Kangaroo", "VKAN", 64, 64, "kangaroo", (35, 35)),
    Decoration("Tiger", "VTIG", 96, 48, "tiger", (35, 35)),
    Decoration("Bison", "VBIS", 104, 72, "bison", (35, 35)),
    Decoration("Penguin", "VPEN", 20, 24, "penguin", (35, 35)),
    Decoration("Zoo wayfinding sign", "VZSN", 64, 96, "zoo_sign"),
    Decoration("Orangutan", "VORA", 64, 64, "orangutan", (35, 35)),
    Decoration("Malayan tapir", "VTAP", 96, 56, "tapir", (35, 35)),
    Decoration("Jaguar", "VJAG", 88, 48, "jaguar", (35, 35)),
    Decoration("Snow leopard", "VSNL", 96, 48, "snow_leopard", (35, 35)),
    Decoration("Moose", "VMOO", 112, 112, "moose", (35, 35)),
    Decoration("Peaceful polar bear", "VPBR", 120, 80, "polar_bear", (35, 35)),
    Decoration("Arctic wolf", "VAWF", 88, 48, "arctic_wolf", (35, 35)),
    Decoration("Blue faceoff player", "VHBL", 80, 64, "hockey_blue", (18, 18, 18, 18)),
    Decoration("Red faceoff player", "VHRD", 80, 64, "hockey_red", (18, 18)),
    Decoration("Cheering seated fans", "VFAN", 144, 72, "fans", (12, 12, 12, 12)),
    Decoration("Cheering seated fans alternate", "VFA2", 144, 72, "fans_alternate", (12, 12, 12, 12)),
    Decoration("Stage guitarist", "VGTR", 80, 64, "guitarist", (10, 10)),
    Decoration("Stage drummer", "VDRM", 96, 64, "drummer", (8, 8)),
    Decoration("Glowing exit portal", "VPRT", 144, 224, "portal", (8, 8, 8, 8), True),
    Decoration("Queen Street hotdog vendor", "VHOT", 112, 112, "hotdog_vendor", (24, 24)),
    Decoration("Queen Street ice-cream vendor", "VICE", 112, 112, "icecream_vendor", (24, 24)),
    *(Decoration(f"Cheering crowd group {index + 3}", f"VFC{index + 3}", 144, 72,
                 f"fans_{index + 3}", (16, 16)) for index in range(6)),
    Decoration("Ready infielder", "VBMN", 80, 64, "baseman"),
    Decoration("Batter at the plate", "VBAT", 80, 64, "batter"),
    Decoration("Catcher behind the plate", "VCAT", 80, 64, "catcher"),
    Decoration("Waiting commuter in teal", "VCM1", 80, 64, "commuter_teal", (18, 26, 18, 26)),
    Decoration("Waiting commuter in red", "VCM2", 80, 64, "commuter_red", (18, 26, 18, 26)),
    Decoration("Waiting commuter in gold", "VCM3", 80, 64, "commuter_gold", (18, 26, 18, 26)),
)
DIRECTIONAL_KINDS = {
    "referee", "hockey_blue", "hockey_red", "guitarist", "drummer",
    "hotdog_vendor", "icecream_vendor", "elephant", "giraffe", "deer",
    "kangaroo", "tiger", "bison", "penguin", "orangutan", "tapir", "jaguar",
    "snow_leopard", "moose", "polar_bear", "arctic_wolf",
    "pitcher", "catcher", "baseman", "batter",
}
FAN_KINDS = ("fans", "fans_alternate", *(f"fans_{index}" for index in range(3, 9)))
BY_KIND = {item.kind: item for item in DECORATIONS}
BY_ID = {item.doomednum: item for item in DECORATIONS}


def catalog():
    result = [dict(asdict(item), doomednum=item.doomednum, thing=item.thing,
                 state=item.state, sprite_number=item.sprite, frame="A",
                 sprite=f"{item.prefix}A{1 if item.directional else 0}", solid=False, shootable=False,
                 counts_as_kill=False, counts_as_item=False,
                 radius=0, duration_tics=item.frame_tics[0],
                 next_state=item.state if len(item.frame_tics) == 1 else item.state + 1,
                 action="NULL", grounded=True,
                 world_anchor="World coordinates and facing; eight native views" if item.directional else None,
                 frames=[dict(sprite=f"{item.prefix}{chr(65 + index)}{1 if item.directional else 0}",
                              **({"rotations": {str(r): f"{item.prefix}{chr(65 + index)}{r}"
                                                for r in range(1, 9)}} if item.directional else {}),
                              state=item.state + index, duration_tics=tics,
                              next_state=item.state + (index + 1) % len(item.frame_tics))
                         for index, tics in enumerate(item.frame_tics)])
            for item in DECORATIONS]
    for item in result:
        item["frame_tics"] = list(item["frame_tics"])
    return result


def gameplay_patch():
    lines = ["[SPRITES]"]
    lines.extend(f"{item.sprite} = {item.prefix}" for item in DECORATIONS)
    for item in DECORATIONS:
        lines.extend(("", f"Thing {item.thing}", f"ID # = {item.doomednum}",
                      f"Initial frame = {item.state}", "Hit points = 1",
                      "Width = 0", f"Height = {item.height * 65536}",
                      "Bits = 16", "Speed = 0"))
        for index, tics in enumerate(item.frame_tics):
            state = item.state + index
            lines.extend(("", f"Frame {state}", f"Sprite number = {item.sprite}",
                          f"Sprite subnumber = {index | (32768 if item.fullbright else 0)}", f"Duration = {tics}",
                          f"Next frame = {item.state + (index + 1) % len(item.frame_tics)}",
                          "", "[CODEPTR]", f"FRAME {state} = NULL"))
    return "\n".join(lines) + "\n"


def font(size):
    return ImageFont.truetype(str(Path(r"C:\Windows\Fonts\bahnschrift.ttf")), size)


def decoration_image(item, frame=0, rotation=1):
    from venue_art import sprite
    image = sprite(f"{item.kind}-r{rotation}" if item.directional else item.kind, frame)
    if image.size != (item.width, item.height):
        raise ValueError(f"{item.kind}: polished sprite has incorrect native dimensions")
    return image


@lru_cache(maxsize=1)
def sprite_lumps():
    from build_toronto_wad import _doom_palette, _indexed_canvas, _sprite_patch
    palette = Image.new("P", (1, 1))
    palette.putpalette(_doom_palette())
    result = [(f"{item.prefix}{chr(65 + frame)}{rotation}", _sprite_patch(
        _indexed_canvas(decoration_image(item, frame, rotation or 1), palette),
        (item.width // 2, item.height)))
              for item in DECORATIONS for frame in range(len(item.frame_tics))
              for rotation in (range(1, 9) if item.directional else (0,))]
    return tuple(result)


@lru_cache(maxsize=1)
def material_images():
    from venue_art import material, site_material, sprite
    walls, flats = {}, {}
    asphalt = site_material("materials_city.png", 0, (64, 64))
    walls["ROADBED"], flats["ASPHALT"] = asphalt, asphalt
    cobbles = site_material("materials_city.png", 1, (64, 64))
    walls["COBBLE"], flats["COBBLEF"] = cobbles, cobbles
    crossing = asphalt.copy()
    crossing_draw = ImageDraw.Draw(crossing)
    for x in (4, 36):
        crossing_draw.rectangle((x, 0, x + 12, 63), fill="#d9d3be")
    flats["CROSSWLK"] = crossing
    shop = material(1, (256, 256))
    shop_draw = ImageDraw.Draw(shop)
    shop_draw.rectangle((0, 62, 255, 104), fill="#e5ddd0")
    for x in range(12, 256, 48):
        shop_draw.rectangle((x, 126, x + 30, 204), fill="#35464c", outline="#d9cfb6", width=3)
    walls["EATONHM"] = shop
    sandstone = material(0)
    windows = material(1, (256, 256))
    walls["QSTONE"], walls["QWINDOW"] = sandstone, windows
    entry = Image.new("RGB", (512, 1024))
    for y in range(0, 1024, 256):
        for x in (0, 256):
            entry.paste(windows, (x, y))
    draw = ImageDraw.Draw(entry)
    for x in (45, 205, 365):
        for y in (70, 300):
            draw.rounded_rectangle((x, y, x + 90, y + 170), radius=42,
                                   fill="#344347", outline="#c1a68b", width=8)
    draw.rounded_rectangle((155, 560, 357, 810), radius=100, fill="#302b28",
                           outline="#ceb196", width=16)
    draw.rectangle((175, 690, 337, 815), fill="#302b28")
    draw.line((256, 665, 256, 815), fill="#a08257", width=5)
    draw.text((167, 520), "ONTARIO", font=font(36), fill="#e0c3a0")
    walls["QENTRY"] = entry
    roof = material(12)
    walls["QROOF"] = roof
    civic = material(2)
    walls["CITYRIB"] = civic
    walls["CITYBASE"] = site_material("materials_city.png", 2)
    walls["RYWINDOW"] = site_material("materials_city.png", 3, (256, 256))
    for index in range(12):
        panel = material(0, (2048, 512))
        draw = ImageDraw.Draw(panel)
        draw.rectangle((905, 104, 1142, 283), fill="#372b22", outline="#c1a367", width=8)
        from venue_art import DIRECTORY
        filename = "museum-paintings-source.png" if index < 6 else "museum-paintings-second-source.png"
        with Image.open(DIRECTORY / filename) as source:
            cell = index % 6
            x0, y0 = (cell % 3) * source.width / 3, (cell // 3) * source.height / 2
            artwork = source.crop((round(x0), round(y0),
                                   round(x0 + source.width / 3), round(y0 + source.height / 2)))
            artwork = ImageOps.contain(artwork.convert("RGB"), (218, 160), Image.Resampling.LANCZOS)
        panel.paste(artwork, (915 + (218 - artwork.width) // 2,
                             114 + (160 - artwork.height) // 2))
        draw.rectangle((1000, 295, 1047, 307), fill="#d1c5a5")
        walls[f"RMART{index + 1:X}"] = panel
    # Featured large painting: the supplied gold-framed royal portrait,
    # cropped to the frame so none of the red brick backdrop ships. All art
    # stays inside texture rows 66..322, the band gallery walls display.
    featured = material(0, (2048, 512))
    with Image.open(DIRECTORY / "king-richard-source.png") as source:
        king = source.convert("RGB").crop((110, 86, 924, 963))
    king = ImageOps.contain(king, (320, 220), Image.Resampling.LANCZOS)
    featured.paste(king, (1024 - king.width // 2, 78 + (220 - king.height) // 2))
    draw = ImageDraw.Draw(featured)
    draw.rectangle((1024 - king.width // 2 - 10, 70,
                    1024 + king.width // 2 + 10, 306), outline="#c1a367", width=6)
    draw.rectangle((976, 310, 1071, 321), fill="#d1c5a5")
    walls["RMKING"] = featured
    # Union Great Hall: high-definition arched-window limestone interior wall.
    from project_paths import ASSETS
    from toronto_materials import _tile_edges
    with Image.open(ASSETS / "materials_greathall.png") as source:
        walls["UGREATH"] = _tile_edges(
            source.convert("RGB").resize((768, 512), Image.Resampling.LANCZOS), False)
    # Arena scoreboard: four identical screen faces on a hanging housing.
    scoreboard = Image.new("RGB", (256, 96), (24, 28, 33))
    draw = ImageDraw.Draw(scoreboard)
    draw.rectangle((0, 0, 255, 8), fill="#454c54")
    draw.rectangle((10, 16, 245, 62), fill="#0c1a20", outline="#59cdb6", width=3)
    from hud_art import pixel_text
    for text, x, y, color in (("HOME", 24, 24, (236, 222, 181)),
                              ("0", 58, 40, (110, 229, 208)),
                              ("20:00", 104, 32, (255, 183, 107)),
                              ("GUEST", 176, 24, (236, 222, 181)),
                              ("0", 196, 40, (110, 229, 208))):
        label = pixel_text(text, color)
        label = label.resize((label.width * 2, label.height * 2), Image.Resampling.NEAREST)
        scoreboard.paste(label, (x, y), label)
    for x in range(14, 256, 24):
        draw.rectangle((x, 72, x + 12, 88), fill="#153a43", outline="#3f565d")
    walls["VSCOR"] = scoreboard
    for index, (text, color) in enumerate((
        ("TORONTO\nAFTER DARK", "#20485d"), ("PAINTBALL\nOPEN", "#653d59"),
        ("LIVE AT\nTHE SQUARE", "#365747"), ("BUILT BY\nRICHARD HARRIS", "#754836"),
    ), 1):
        billboard = Image.new("RGB", (256, 128), "#1a222e")
        draw = ImageDraw.Draw(billboard)
        draw.rectangle((6, 6, 249, 121), fill=color, outline="#deb96a", width=3)
        draw.multiline_text((20, 20), text, font=font(25), fill="#f0dcad", spacing=4)
        for x in range(12, 248, 15):
            draw.rectangle((x, 112, x + 3, 115), fill="#84c9c4")
        facade = Image.new("RGB", (512, 2048))
        window_tile = material(14, (256, 256))
        for y in range(0, 2048, 256):
            for x in (0, 256):
                facade.paste(window_tile, (x, y))
        facade.paste(billboard.resize((512, 256), Image.Resampling.NEAREST), (0, 96))
        walls[f"SBILL{index}"] = facade
    stage = Image.new("RGB", (1024, 512))
    stage_panel = site_material("materials_city.png", 4, (256, 256))
    for x in range(0, 1024, 256):
        for y in (0, 256):
            stage.paste(stage_panel, (x, y))
    draw = ImageDraw.Draw(stage)
    draw.rectangle((70, 50, 953, 180), fill="#193e43", outline="#83ada4", width=6)
    draw.text((195, 72), "SANKOFA LIVE", font=font(80), fill="#e3c88e")
    walls["STAGEBK"] = stage
    rental = site_material("materials_city.png", 5, (256, 256))
    draw = ImageDraw.Draw(rental)
    draw.rectangle((4, 22, 251, 72), fill="#264653", outline="#bdc9bc", width=3)
    draw.text((18, 30), "SKATES / SNACKS", font=font(27), fill="#e9ddbd")
    draw.rectangle((18, 100, 237, 233), fill="#30404a", outline="#a3a99b", width=5)
    for x in (72, 128, 184):
        draw.line((x, 103, x, 229), fill="#8f9b9e", width=4)
    walls["SKATERNT"] = rental
    flats["STAGEFL"] = site_material("materials_arena.png", 6, (64, 64))
    flats["NPSICE"] = material(9, (64, 64))
    walls["ZWSTONE"], walls["ZWCEDAR"] = material(4), material(5)
    flats.update(ZFGRASS=material(6, (64, 64)), ZFEARTH=material(7, (64, 64)),
                 ZFASPH=material(13, (64, 64)))
    flats["NPSSNOW"] = Image.new("RGB", (64, 64), "#d8dcd4")
    flats["TRACKBED"] = site_material("materials_arena.png", 5, (64, 64))
    flats["PLATSAFE"] = Image.new("RGB", (64, 64), "#d4b852")
    draw = ImageDraw.Draw(flats["TRACKBED"])
    for y in range(0, 64, 16):
        draw.rectangle((0, y + 3, 63, y + 7), fill="#4a3b2e")
    for x in (13, 48):
        draw.rectangle((x, 0, x + 3, 63), fill="#adb3b2")
        draw.line((x, 0, x, 63), fill="#e1ded1")
    walls["RAILEDGE"] = site_material("materials_city.png", 6)
    walls["PLATNUM"] = Image.new("RGB", (128, 128), "#36484b")
    draw = ImageDraw.Draw(walls["PLATNUM"])
    draw.rectangle((8, 9, 119, 90), fill="#16383e", outline="#bfc6b6", width=3)
    draw.text((17, 18), "PLATFORM", font=font(16), fill="#d1d9cb")
    draw.text((49, 39), "4", font=font(39), fill="#e8c776")
    for name in ("QROOF", "CITYBASE", "RYWINDOW"):
        flats[name[:7] + "F"] = walls[name].resize((64, 64), Image.Resampling.NEAREST)
    labels = (("INDO", "MALAYA"), ("AFRICA", "SAVANNA"), ("AMERICAS", "PAVILION"),
              ("AUSTRAL", "ASIA"), ("EURASIA", "WILDS"), ("CANADIAN", "DOMAIN"),
              ("TUNDRA", "TREK"))
    for index, lines in enumerate(labels, 1):
        sign = Image.new("RGB", (512, 256))
        for x in range(0, 512, 128):
            for y in (0, 128):
                sign.paste(material(4), (x, y))
        draw = ImageDraw.Draw(sign)
        draw.rectangle((192, 10, 319, 111), fill="#274d43", outline="#e5d6a5", width=3)
        for y, line in zip((34, 61), lines):
            size = 17 if len(line) > 7 else 20
            text_font = font(size)
            bounds = draw.textbbox((0, 0), line, font=text_font)
            draw.text((192 + (128 - bounds[2]) // 2, y), line, font=text_font, fill="#ecdfb4")
        walls[f"ZSIGN{index}"] = sign
    panel = Image.new("RGB", (512, 288), (43, 48, 52))
    panel_image = Image.new("RGBA", (96, 96))
    panel_draw = ImageDraw.Draw(panel_image)
    octagon = [(28, 4), (68, 4), (92, 28), (92, 68),
               (68, 92), (28, 92), (4, 68), (4, 28)]
    panel_draw.polygon(octagon, fill="#7b8588", outline="#e6e9d8", width=4)
    inner = [(32, 16), (64, 16), (80, 32), (80, 64),
             (64, 80), (32, 80), (16, 64), (16, 32)]
    panel_draw.polygon(inner, fill="#16292f", outline="#f2d876", width=3)
    panel_draw.text((48, 48), "EXIT", font=font(20), fill="#eaf4c5", anchor="mm")
    panel.paste(panel_image, (208, 144), panel_image)
    walls["PTPANEL"] = panel
    walls["PTFRAME"] = site_material("materials_city.png", 7)
    fence = Image.new("RGBA", (128, 128))
    mesh = ImageDraw.Draw(fence)
    for offset in range(-128, 256, 16):
        mesh.line((offset, 0, offset + 128, 128), fill=(129, 141, 146), width=1)
        mesh.line((offset, 0, offset - 128, 128), fill=(81, 96, 104), width=1)
    mesh.line((0, 0, 127, 0), fill=(160, 168, 172), width=3)
    walls["PTFENCE"] = fence
    return walls, flats


def export_sources():
    from project_paths import ART_SOURCES
    directory = ART_SOURCES / "venues"
    directory.mkdir(parents=True, exist_ok=True)
    inventory = []
    for item in DECORATIONS:
        for frame in range(len(item.frame_tics)):
            for rotation in (range(1, 9) if item.directional else (0,)):
                name = f"{item.prefix}{chr(65 + frame)}{rotation}.png"
                decoration_image(item, frame, rotation or 1).save(directory / name)
                inventory.append(dict(path=name, role="nonblocking_scenery_sprite",
                                      width=item.width, height=item.height,
                                      ground_anchor=[item.width // 2, item.height]))
    walls, flats = material_images()
    for role, images in (("wall", walls), ("flat", flats)):
        for name, image in images.items():
            path = f"{name}.png"
            image.save(directory / path)
            inventory.append(dict(path=path, role=role, width=image.width, height=image.height))
    (directory / "inventory.json").write_text(json.dumps(inventory, indent=2) + "\n")


def apply_gallery_panels(venue):
    """Assign framed art to exposed gallery walls, never checkpoint controls."""
    from shapely.geometry import LineString

    geometry = venue.geometry
    panels = 0
    featured = 0
    for a, b, _, special, _, front, back in geometry.lines:
        if special or back < 0:
            continue
        ax, ay = geometry.vertices[a]
        bx, by = geometry.vertices[b]
        if min(ay, by) < -650 or math.hypot(ax - bx, ay - by) < 128:
            continue
        fsector = struct.unpack_from("<h", geometry.sides[front], 28)[0]
        bsector = struct.unpack_from("<h", geometry.sides[back], 28)[0]
        fs, bs = geometry.sectors[fsector], geometry.sectors[bsector]
        side = front if bs.floor >= 256 and fs.floor == 0 else back if fs.floor >= 256 and bs.floor == 0 else None
        if side is None:
            continue
        length = math.hypot(ax - bx, ay - by)
        mx, my = (ax + bx) / 2, (ay + by) / 2
        sign = 1 if side == front else -1
        nx, ny = sign * (by - ay) / length, sign * (ax - bx) / length
        if not any(
            venue.clear_at(round(mx + nx * distance), round(my + ny * distance), 24)
            and venue.walkable.covers(LineString(((mx + nx * 4, my + ny * 4),
                                                  (mx + nx * distance, my + ny * distance))).buffer(3))
            for distance in (240, 320, 400)
        ):
            continue
        if panels == 12 and featured:
            continue
        x, y, upper, _, middle, sector = struct.unpack("<hh8s8s8sh", geometry.sides[side])
        if length > 2048:
            raise ValueError("Gallery wall exceeds unique painting canvas")
        # The first roomy wall hosts the featured royal portrait; the rest
        # receive the twelve rotating gallery panels.
        if not featured and length >= 420:
            name = b"RMKING"
            featured = 1
        elif panels < 12:
            name = f"RMART{panels + 1:X}".encode("ascii")
            panels += 1
        else:
            continue
        geometry.sides[side] = struct.pack("<hh8s8s8sh", round((2048 - length) / 2),
                                         round(194 - max(fs.floor, bs.floor) / 2),
                                         upper, name, middle, sector)
    if panels < 12 or not featured:
        raise ValueError(f"ROM needs the royal portrait and twelve panels, found {featured}+{panels}")
