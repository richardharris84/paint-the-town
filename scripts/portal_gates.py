"""KEX-native invisible keyed gates with activation-only fullbright sky columns."""

import math
import struct
from dataclasses import replace

from PIL import Image, ImageDraw

from doom_geometry import Sector
from venue_geometry import add_exit


EMITTER_ID = 15410
PANEL_ID = 15411
EMITTER_THING = 358
BEAM_THING = 359
PANEL_THING = 360
BEAM_SPRITE = 282
PANEL_SPRITE = 283
DUST_SPRITE = 284
DUST_PHASES = 8
SEGMENT_HEIGHT = 224
SEGMENTS = 7
SKY_HEIGHT = SEGMENT_HEIGHT * SEGMENTS


def install_gate(venue, spec, checkpoint):
    geometry = venue.geometry
    door = next(sector for _, sector, region in venue.faces
                if region.title == "Blue-key exit checkpoint")
    geometry.sectors[door] = replace(geometry.sectors[door], tag=901, ceiling_texture="F_SKY1")
    for _, sector, region in venue.faces:
        if region.title in ("Low sky checkpoint approach", "Exit checkpoint interior"):
            geometry.sectors[sector] = replace(
                geometry.sectors[sector], ceiling=SKY_HEIGHT, ceiling_texture="F_SKY1")
    for index, line in enumerate(geometry.lines):
        a, b, flags, special, tag, front, back = line
        if back < 0:
            continue
        front_sector = struct.unpack_from("<h", geometry.sides[front], 28)[0]
        back_sector = struct.unpack_from("<h", geometry.sides[back], 28)[0]
        if (front_sector == door) == (back_sector == door):
            continue
        if front_sector == door:
            a, b, front, back = b, a, back, front
        for side in (front, back):
            xo, yo, _, lower, _, sector = struct.unpack("<hh8s8s8sh", geometry.sides[side])
            geometry.sides[side] = struct.pack("<hh8s8s8sh", xo, yo, b"-", lower, b"-", sector)
        geometry.lines[index] = (a, b, flags, 32, tag, front, back)
    # Transfer heights hide the physical key gate without opening a sky cutout.
    control = geometry.sector(Sector(0, SKY_HEIGHT, spec.base.floor, "F_SKY1", 255))
    geometry.loop([(10000, 10000), (10000, 10128), (10128, 10128), (10128, 10000)],
                  control, spec.base.wall)
    line = geometry.lines[-1]
    geometry.lines[-1] = (*line[:3], 242, 901, *line[5:])
    x, y = spec.exit_center
    corners = [(x - 24, y - 40), (x + 24, y - 40), (x + 40, y - 24),
               (x + 40, y + 24), (x + 24, y + 40), (x - 24, y + 40),
               (x - 40, y + 24), (x - 40, y - 24)]
    for a, b in zip(corners, corners[1:] + corners[:1]):
        add_exit(venue, a, b)


def place_gate(geometry, spec):
    checkpoint = next(region for region in spec.regions
                      if region.title == "Blue-key exit checkpoint")
    x, y = spec.exit_center
    geometry.thing(x, y, EMITTER_ID, angle=270)
    geometry.thing(x - 64, round(checkpoint.polygon.bounds[1]) - 4, PANEL_ID)


def gameplay_patch():
    lines = ["", "[SPRITES]", "282 = VBEA", "283 = VPAN", "284 = VDUS"]
    for thing, doomednum, state, moving, flags in (
        (EMITTER_THING, EMITTER_ID, 7900, 7902, 560),
        (BEAM_THING, -1, 7920, 0, 528),
        (PANEL_THING, PANEL_ID, 7930, 0, 16),
    ):
        lines.extend(("", f"Thing {thing}", f"ID # = {doomednum}",
                      f"Initial frame = {state}", f"First moving frame = {moving}",
                      "Hit points = 1", "Width = 0", "Height = 0",
                      f"Bits = {flags}"))
    states = [(7900, DUST_SPRITE, 32768, 1, 7940, "NULL", ()),
              (7930, PANEL_SPRITE, 32768, -1, 7930, "NULL", ())]
    for phase in range(DUST_PHASES):
        state = 7940 + phase * 2
        states.extend(((state, DUST_SPRITE, 32768 | phase, 7, state + 1, "Look", ()),
                       (state + 1, DUST_SPRITE, 32768 | phase, 1,
                        7940 + ((phase + 1) % DUST_PHASES) * 2, "Turn", ())))
    for index in range(SEGMENTS):
        state = 7902 + index
        states.append((state, 231, 0, 1 if index < SEGMENTS - 1 else -1,
                       state + 1 if index < SEGMENTS - 1 else state, "SpawnObject",
                       (BEAM_THING, 0, 0, 0, index * SEGMENT_HEIGHT * 65536)))
    for frame in range(4):
        states.append((7920 + frame, BEAM_SPRITE, 32768 | frame, 8,
                       7920 + (frame + 1) % 4, "NULL", ()))
    for state, sprite, frame, tics, successor, action, args in states:
        lines.extend(("", f"Frame {state}", f"Sprite number = {sprite}",
                      f"Sprite subnumber = {frame}", f"Duration = {tics}",
                      f"Next frame = {successor}"))
        lines.extend(f"Args{index} = {value}" for index, value in enumerate(args, 1))
        if action == "Turn":
            # Native KEX A_Turn consumes binary angles, not integer degrees.
            lines.append("Unknown 1 = 1073741824")
        lines.extend(("", "[CODEPTR]", f"FRAME {state} = {action}"))
    return "\n".join(lines) + "\n"


def beam_image(frame):
    image = Image.new("RGBA", (144, SEGMENT_HEIGHT))
    for y in range(SEGMENT_HEIGHT):
        for x in range(144):
            radius = abs(x - 71.5) / 72
            ripple = math.sin(x * .22 + frame * math.pi / 2)
            if radius < .6 or (radius < .85 and (x + y + frame) % 4 != 0):
                image.putpixel((x, y), (round(165 + 90 * (1 - radius)),
                                       round(115 + 130 * (1 - radius) * (.9 + .1 * ripple)),
                                       round(30 + 210 * (1 - radius) ** 2), 255))
    return image


def panel_image():
    image = Image.new("RGBA", (80, 104))
    draw = ImageDraw.Draw(image)
    draw.rectangle((7, 25, 72, 103), fill="#384752", outline="#e5c46b", width=3)
    for x in (13, 66):
        for y in (31, 97):
            draw.ellipse((x - 1, y - 1, x + 1, y + 1), fill="#141f2b")
    socket = ((29, 50), (50, 50), (61, 61), (61, 80),
              (50, 91), (29, 91), (18, 80), (18, 61))
    draw.polygon(socket, fill="#070d12", outline="#e5c46b", width=3)
    draw.line((28, 55, 49, 55, 56, 62), fill="#6a7981", width=2)
    from hud_art import pixel_text
    image.alpha_composite(pixel_text("EXIT", (236, 222, 181)), (28, 37))
    draw.rectangle((35, 67, 44, 74), fill="#17232b", outline="#535d64")
    return image


def dust_image(phase):
    image = Image.new("RGBA", (144, SEGMENT_HEIGHT))
    draw = ImageDraw.Draw(image)
    for index in range(10):
        x = 26 + (index * 37) % 92
        y = (index * 71 + phase * 28) % SEGMENT_HEIGHT
        color = ("#fff1b0", "#f4ce54", "#c5e0bb")[index % 3]
        draw.rectangle((x, y, x + 1, min(SEGMENT_HEIGHT - 1, y + 2)), fill=color)
    return image


def sprite_lumps():
    from build_toronto_wad import _doom_palette, _indexed_canvas, _sprite_patch
    palette = Image.new("P", (1, 1))
    palette.putpalette(_doom_palette())
    return [(f"VBEA{chr(65 + frame)}0", _sprite_patch(
        _indexed_canvas(beam_image(frame), palette), (72, SEGMENT_HEIGHT))) for frame in range(4)] + [
        ("VPANA0", _sprite_patch(_indexed_canvas(panel_image(), palette), (40, 104)))] + [
        (f"VDUS{chr(65 + phase)}0", _sprite_patch(
            _indexed_canvas(dust_image(phase), palette), (72, SEGMENT_HEIGHT)))
        for phase in range(DUST_PHASES)]


def metadata():
    return dict(emitter_id=EMITTER_ID, panel_id=PANEL_ID, beam_thing=BEAM_THING,
                segment_height=SEGMENT_HEIGHT, segments=SEGMENTS, height=SKY_HEIGHT,
                scan_cycle_tics=32, kex_turn_binary_angle=1073741824,
                inactive_effect="Sparse falling fairy dust on the fixed emitter; replaced on activation",
                dust_phases=DUST_PHASES, dust_cycle_tics=DUST_PHASES * 8,
                activation="Blue open-stay gate; transfer heights hide moving geometry; "
                           "fixed ambush emitter surveys all directions with timed Look/Turn "
                           "states and spawns beam after line of sight opens",
                rendering="Fullbright opaque core and patterned edges; no native translucency",
                collision="Hidden gate blocks until keyed USE; column and ground-mounted gold-edged panel are nonblocking",
                exit="Eight walk-over exit lines inside the beam footprint",
                sprites=["VBEAA0", "VBEAB0", "VBEAC0", "VBEAD0", "VPANA0",
                         *(f"VDUS{chr(65 + phase)}0" for phase in range(DUST_PHASES))])
