"""Grounded noncombat shuttles initialized against fixed world-space anchors."""

from PIL import Image

BEAR_OUTBOUND = 850
BEAR_RETURN = 750
GIRL_OUTBOUND = 200
GIRL_RETURN = 180

BEAR_CONTROLLER = 354
BEAR_RELAY = 355
BEAR_ACTOR = 356
GIRL_GREEN_CONTROLLER = 375
GIRL_GREEN_RELAY = 376
GIRL_GREEN_ACTOR = 377
GIRL_PURPLE_CONTROLLER = 378
GIRL_PURPLE_RELAY = 379
GIRL_PURPLE_ACTOR = 380


def _actor_states(start, sprite, outbound, returning):
    lines = []
    for index in range(32):
        state = start + index * 2
        pose = index // 8
        lines.extend((
            f"Frame {state}", f"Sprite number = {sprite}",
            f"Sprite subnumber = {pose}", "Duration = 0",
            f"Next frame = {start + 100}",
            f"Args1 = {state + 1}", f"Args2 = {outbound * 65536}",
            "", "[CODEPTR]", f"FRAME {state} = JumpIfTracerCloser", "",
            f"Frame {state + 1}", f"Sprite number = {sprite}",
            f"Sprite subnumber = {pose}", "Duration = 1",
            f"Next frame = {start + ((index + 1) % 32) * 2}",
            "Args1 = 1", "Args2 = 1", "", "[CODEPTR]",
            f"FRAME {state + 1} = SeekTracer", "",
        ))
    turn = start + 100
    lines.extend((
        f"Frame {turn}", f"Sprite number = {sprite}", "Sprite subnumber = 0",
        "Duration = 8", f"Next frame = {turn + 1}", "",
        f"Frame {turn + 1}", f"Sprite number = {sprite}", "Sprite subnumber = 0",
        "Duration = 0", f"Next frame = {turn + 2}",
        "Args1 = 11796480", "Args2 = 11796480", "",
        f"Frame {turn + 2}", f"Sprite number = {sprite}", "Sprite subnumber = 0",
        "Duration = 0", f"Next frame = {turn + 3}",
        f"Args1 = {start}", f"Args2 = {returning * 65536}", "",
        f"Frame {turn + 3}", f"Sprite number = {sprite}", "Sprite subnumber = 0",
        "Duration = 1", f"Next frame = {turn + 2}", "Args1 = 1", "Args2 = 1",
        "", "[CODEPTR]", f"FRAME {turn} = NULL",
        f"FRAME {turn + 1} = SeekTracer",
        f"FRAME {turn + 2} = JumpIfTracerCloser",
        f"FRAME {turn + 3} = SeekTracer", "",
    ))
    return lines


def _bootstrap_states(base, anchor, actor, sprite):
    lines = []
    for state, image, duration, successor, action, args in (
        (base, 231, 1, base + 1, "NULL", ()),
        (base + 1, 231, -1, base + 1, "SpawnObject", (anchor,)),
        (base + 10, 231, 1, base + 11, "NULL", ()),
        (base + 11, 231, 1, base + 12, "AddFlags", (4194304,)),
        (base + 12, 231, 8, base + 13, "SpawnObject", (actor,)),
        (base + 13, 231, 0, base + 14, "RemoveFlags", (4194304,)),
        (base + 14, 231, -1, base + 14, "AddFlags", (16,)),
        (base + 20, sprite, 1, base + 21, "NULL", ()),
        (base + 21, sprite, 1, base + 100, "FindTracer", (0, 1)),
    ):
        lines.extend((f"Frame {state}", f"Sprite number = {image}",
                      "Sprite subnumber = 0", f"Duration = {duration}",
                      f"Next frame = {successor}"))
        lines.extend(f"Args{index} = {value}" for index, value in enumerate(args, 1))
        lines.extend(("", "[CODEPTR]", f"FRAME {state} = {action}", ""))
    return lines


def gameplay_patch():
    lines = ["", "[SPRITES]", "281 = ABWR", "285 = GRLG", "286 = GRLP", ""]
    for thing, doomednum, state, bits, width, height in (
        (BEAR_CONTROLLER, 15402, 7600, 528, 0, 0),
        (GIRL_GREEN_CONTROLLER, 15403, 9000, 528, 0, 0),
        (GIRL_PURPLE_CONTROLLER, 15404, 9200, 528, 0, 0),
        # KEX FindTracer needs COUNTKILL briefly, but not during anchor spawning.
        # Clear it and leave the blockmap after the one-time acquisition.
        (BEAR_RELAY, -1, 7610, 516, 0, 0),
        (GIRL_GREEN_RELAY, -1, 9010, 516, 0, 0),
        (GIRL_PURPLE_RELAY, -1, 9210, 516, 0, 0),
        (BEAR_ACTOR, -1, 7620, 2, 28, 72),
        (GIRL_GREEN_ACTOR, -1, 9020, 2, 12, 48),
        (GIRL_PURPLE_ACTOR, -1, 9220, 2, 12, 48),
    ):
        lines.extend((f"Thing {thing}", f"ID # = {doomednum}", f"Initial frame = {state}",
                      "Hit points = 1", f"Width = {width * 65536}",
                      f"Height = {height * 65536}", f"Bits = {bits}",
                      "Speed = 65536", "Missile damage = 0", ""))
    lines.extend(_bootstrap_states(7600, BEAR_RELAY, BEAR_ACTOR, 281))
    lines.extend(_bootstrap_states(9000, GIRL_GREEN_RELAY, GIRL_GREEN_ACTOR, 285))
    lines.extend(_bootstrap_states(9200, GIRL_PURPLE_RELAY, GIRL_PURPLE_ACTOR, 286))
    lines.extend(_actor_states(7700, 281, BEAR_OUTBOUND, BEAR_RETURN))
    lines.extend(_actor_states(9050, 285, GIRL_OUTBOUND, GIRL_RETURN))
    lines.extend(_actor_states(9250, 286, GIRL_OUTBOUND, GIRL_RETURN))
    return "\n".join(lines)


def sprite_lumps():
    from build_toronto_wad import _doom_palette, _indexed_canvas, _sprite_patch
    from venue_art import sprite

    palette = Image.new("P", (1, 1))
    palette.putpalette(_doom_palette())
    lumps = []
    for prefix, family in (("ABWR", "polar_bear_walk-r"), ("GRLG", "girl_green_walk-r")):
        for phase in range(4):
            for rotation in range(1, 9):
                image = sprite(f"{family}{rotation}", phase)
                name = f"{prefix}{chr(65 + phase)}{rotation}"
                lumps.append((name, _sprite_patch(
                    _indexed_canvas(image, palette), (image.width // 2, image.height))))
    # The purple girl keeps her supplied side-view art as a camera-facing
    # billboard: one walk cycle, rotation 0, bottom-centre anchored.
    for phase in range(4):
        image = sprite("girl_purple", phase)
        lumps.append((f"GRLP{chr(65 + phase)}0", _sprite_patch(
            _indexed_canvas(image, palette), (image.width // 2, image.height))))
    return tuple(lumps)
