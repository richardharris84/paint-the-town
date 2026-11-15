import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from build_toronto_wad import _animation_patch, _doom_palette, _indexed_canvas, _sprite_patch


INTRO_DOOMEDNUM = 15100
INTRO_THING = 181
INTRO_STATE = 2500
TAB_TIP_DOOMEDNUM = 15110
FIND_TIP_DOOMEDNUM = 15111
SPACEBAR_TIP_DOOMEDNUM = 15112
NAME_TIP_DOOMEDNUM = 15120
TAB_TIP_THING = 190
FIND_TIP_THING = 191
SPACEBAR_TIP_THING = 192
NAME_TIP_THING = 366
PAINT_THING = 180
PAINT_STATE = 2400
PAINT_TICS = (5, 85, 10, 5)
TIP = "Move: W A S D   Aim: Mouse   Fire: Left Click"
PAINTBALL_CLIP = 25
PAINTBALL_CAP = 400


def gameplay_patch(animations, enemies, sizes, specs):
    original = _animation_patch(animations, enemies, sizes).decode("ascii")
    original = original.replace("Doom version = 19", "Doom version = 2024")
    lines = [
        original, "Weapon 1", "Ammo type = 0", "Ammo per shot = 1", "",
        "Weapon 2", "Ammo type = 0", "Ammo per shot = 7", "",
        "Weapon 3", "Ammo type = 0", "Ammo per shot = 1", "",
        "Ammo 0", f"Max ammo = {PAINTBALL_CAP}", f"Per ammo = {PAINTBALL_CLIP}", "",
        # Native puffs get upward velocity assigned AFTER their initial state.
        # Spawn a separate zero-velocity effect on the following tic.
        "Frame 93", "Duration = 1", "Next frame = 2410", "",
        "Frame 2410", "Duration = 0", "Next frame = 0",
        f"Args1 = {PAINT_THING}", "Args5 = -65536", "",
        "[CODEPTR]", "FRAME 2410 = SpawnObject", "",
        f"Thing {PAINT_THING}", "ID # = -1", f"Initial frame = {PAINT_STATE}",
        "Hit points = 1", "Width = 0", "Height = 0",
        "Bits = 528", "Speed = 0", "",
        "[SPRITES]", "230 = PBLT", "231 = TINT", "",
    ]
    for i, duration in enumerate(PAINT_TICS):
        lines.extend((f"Frame {PAINT_STATE + i}", "Sprite number = 230",
                      f"Sprite subnumber = {32768 + i}", f"Duration = {duration}",
                      f"Next frame = {PAINT_STATE + i + 1 if i < 3 else 0}", ""))
    lines.extend((f"Frame {INTRO_STATE}", "Sprite number = 231", "Sprite subnumber = 0",
                  "Duration = -1", f"Next frame = {INTRO_STATE}", ""))
    for i, spec in enumerate(specs):
        lines.extend((f"Thing {INTRO_THING + i}", f"ID # = {INTRO_DOOMEDNUM + i}",
                      f"Initial frame = {INTRO_STATE}", "Hit points = 1",
                      "Width = 1048576", "Height = 1048576", "Bits = 1",
                      "Pickup item type = 0", "Pickup bonus count = 0",
                      "Pickup sound = 0", f"Pickup message = USER_TRINTRO{i + 1}", ""))
    for thing, doomednum, message in (
            (TAB_TIP_THING, TAB_TIP_DOOMEDNUM, "USER_TRTAB"),
            (FIND_TIP_THING, FIND_TIP_DOOMEDNUM, "USER_TRFIND"),
            (SPACEBAR_TIP_THING, SPACEBAR_TIP_DOOMEDNUM, "USER_TRSPACE"),
            *((NAME_TIP_THING + i, NAME_TIP_DOOMEDNUM + i, f"USER_TRNAME{i + 1}")
              for i in range(len(specs)))):
        lines.extend((f"Thing {thing}", f"ID # = {doomednum}",
                      f"Initial frame = {INTRO_STATE}", "Hit points = 1",
                      "Width = 1048576", "Height = 1048576", "Bits = 1",
                      "Pickup item type = 0", "Pickup bonus count = 0",
                      "Pickup sound = 0", f"Pickup message = {message}", ""))
    lines.extend(("[STRINGS]", "GOTCLIP = Picked up a pod of paintballs.",
                  "GOTCLIPBOX = Picked up a case of paintballs.",
                  "GOTSHELLS = Picked up paintballs.",
                  "GOTSHELLBOX = Picked up a case of paintballs.",
                  "GOTSTIM = Picked up a splash of fresh paint.",
                  "GOTMEDIKIT = Picked up a bucket of fresh paint.",
                  "GOTMEDINEED = Picked up a bucket of paint that you REALLY need!",
                  "GOTHTHBONUS = Picked up a paint vial.",
                  "GOTARMBONUS = Picked up a splatter shard.",
                  "GOTARMOR = Picked up a padded paintball vest.",
                  "GOTMEGA = Picked up a pro paintball vest!",
                  "GOTBACKPACK = Picked up a paintball hopper pack!",
                  "GOTSUPER = Paint Surge! Fresh colour floods your health!",
                  "QUITMSG = Leaving so soon? Toronto still needs more colour!",
                  "GOTBLUECARD = Picked up the metal octagonal Portal Key.",
                  "PD_BLUEO = You need the Portal Key to open this gate.",
                  "PD_BLUEK = You need the Portal Key to activate this panel."))
    lines.extend(f"USER_TRINTRO{i + 1} = {spec.title} | {TIP}" for i, spec in enumerate(specs))
    lines.extend(("USER_TRTAB = Tip: Press Tab to view the map",
                  "USER_TRFIND = Find the Portal Key & Exit!",
                  "USER_TRSPACE = Portal Key found! Press Spacebar at the EXIT panel"))
    lines.extend(f"USER_TRNAME{i + 1} = {spec.title}" for i, spec in enumerate(specs))
    from npc_weapons import attack_lumps
    lines.extend(("", attack_lumps(enemies).decode("ascii")))
    from venue_scenery import gameplay_patch as scenery_patch
    lines.extend(("", scenery_patch()))
    from level_inset import gameplay_patch as inset_patch
    lines.extend(("", inset_patch()))
    return "\n".join(lines).encode("ascii")


def feedback_sprites():
    from venue_art import sprite

    palette = Image.new("P", (1, 1))
    palette.putpalette(_doom_palette())
    lumps = []
    for frame in range(2):
        image = sprite("portal_key", frame)
        lumps.append((f"BKEY{chr(65 + frame)}0",
                      _sprite_patch(_indexed_canvas(image, palette), (image.width // 2, image.height))))
    icon = sprite("portal_key").resize((7, 10), Image.Resampling.LANCZOS)
    icon.putalpha(icon.getchannel("A").point(lambda value: 255 if value >= 128 else 0))
    for name in ("STKEYS0", "STKEYS3"):
        lumps.append((name, _sprite_patch(_indexed_canvas(icon, palette), (0, 0))))
    for frame, radius in enumerate((14, 14, 10, 6)):
        image = Image.new("RGBA", (40, 40))
        draw = ImageDraw.Draw(image)
        color = ((15, 193, 184), (16, 173, 170), (26, 132, 130), (32, 102, 102))[frame]
        draw.ellipse((20 - radius, 20 - radius + 2, 20 + radius, 20 + radius - 2), fill=color)
        for dx, dy in ((-13, -9), (12, -8), (-13, 6), (11, 10), (2, -13), (-3, 12)):
            end = (20 + round(dx * radius / 12), 20 + round(dy * radius / 12))
            draw.line((20, 20, *end), fill=color, width=2)
            draw.ellipse((end[0] - 1, end[1] - 1, end[0] + 1, end[1] + 1), fill=color)
        draw.ellipse((16, 16, 22, 19), fill=(110, 229, 208))
        lumps.append((f"PBLT{chr(65 + frame)}0",
                      _sprite_patch(_indexed_canvas(image, palette), (20, 20))))
    lumps.append(("TINTA0", _sprite_patch([[None]], (0, 0))))
    lumps.extend(pickup_sprites(palette))
    return lumps


# Replace the stock IWAD health/armour pickups our maps place with original
# paint-kit art (ammo pickups already ship original art from the base build),
# so the mod reads consistently (and legally) on DOOM.WAD and Freedoom alike.
PICKUP_SPRITES = (
    ("STIM", "pickup_stim", 1), ("MEDI", "pickup_medi", 1),
    ("BON1", "pickup_vial", 4), ("BON2", "pickup_shard", 4),
    ("ARM1", "pickup_vest", 2), ("ARM2", "pickup_vest2", 2),
    ("BPAK", "pickup_pack", 1), ("SOUL", "paint_surge", 4),
)


def pickup_sprites(palette):
    from PIL import ImageEnhance
    from venue_art import sprite

    lumps = []
    for prefix, kind, frames in PICKUP_SPRITES:
        image = sprite(kind)
        for frame in range(frames):
            # Animated pickups pulse in brightness instead of swapping art.
            factor = (1.0, 1.12, 1.3, 1.2)[frame]
            glow = ImageEnhance.Brightness(image).enhance(factor)
            lumps.append((f"{prefix}{chr(65 + frame)}0",
                          _sprite_patch(_indexed_canvas(glow, palette),
                                        (image.width // 2, image.height))))
    return lumps


def hud_lumps(specs=None):
    """Consistent project-owned HUD typography with native face reactions."""
    image = Image.new("RGB", (320, 32), (21, 33, 39))
    draw = ImageDraw.Draw(image)
    draw.line((0, 0, 319, 0), fill=(89, 205, 182))
    for x in (64, 111, 145, 173, 220):
        draw.line((x, 2, x, 30), fill=(58, 83, 87))
    from hud_art import CREAM, hud_art_lumps, pixel_text
    for x, text in ((2, "PAINTBALLS"), (69, "HEALTH"), (113, "MARKERS"),
                    (177, "ARMOUR")):
        label = pixel_text(text, compact=True)
        image.paste(label, (x, 23), label)
    slash = pixel_text("/")
    image.paste(slash, (30, 5), slash)
    palette = Image.new("P", (1, 1))
    palette.putpalette(_doom_palette())
    bar = _sprite_patch(_indexed_canvas(image.convert("RGBA"), palette), (0, 0))

    def element(kind, x, y, **fields):
        return {kind: dict(x=x, y=y, alignment=0, tranmap=None, translation=None,
                           conditions=None, children=None, **fields)}

    children = [
        element("graphic", 0, 0, patch="PBHUD"),
        element("face", 146, 0),
    ]
    for kind, x, number_type in (("number", 27, 3), ("number", 58, 5),
                                  ("percent", 108, 0), ("percent", 216, 1)):
        child = element(kind, x, 6, font="Medium", type=number_type, param=0, maxlength=3)
        child[kind]["alignment"] = 2
        children.append(child)
    for slot, x in ((2, 115), (3, 125), (4, 135)):
        for stem, conditions in (
                ("TROFF", [{"condition": 7, "param": slot}]),
                ("TROWN", [{"condition": 6, "param": slot}, {"condition": 9, "param": slot}]),
                ("TRON", [{"condition": 8, "param": slot}])):
            child = element("graphic", x, 6, patch=f"{stem}{slot}")
            child["graphic"]["conditions"] = conditions
            children.append(child)
    from level_inset import selector
    for level in range(1, 10):
        child = element("graphic", 233, 1, patch=f"TRMAP{level}")
        child["graphic"]["conditions"] = selector(level)
        children.append(child)
    for key in (0, 3):
        child = element("graphic", 222, 1 + key % 3 * 10, patch=f"STKEYS{key}")
        conditions = [{"condition": 10, "param": key + 1}]
        if key < 3:
            conditions.append({"condition": 11, "param": key + 4})
        child["graphic"]["conditions"] = conditions
        children.append(child)
    fullscreen = element("canvas", 0, 168)
    fullscreen["canvas"]["children"] = children
    data = {
        "type": "statusbar", "version": "1.0.0", "metadata": None,
        "data": {
            "numberfonts": [{"name": "Medium", "type": 0, "stem": "TRN"}],
            "statusbars": [
                {"height": 32, "fullscreenrender": False, "fillflat": "PBFILL",
                 "children": children},
                {"height": 200, "fullscreenrender": True, "fillflat": "PBFILL",
                 "children": [fullscreen]},
                {"height": 200, "fullscreenrender": True, "fillflat": "PBFILL", "children": None},
            ],
        },
    }
    from level_inset import image as inset_image
    if specs is None:
        from toronto_venues import venue_specs
        specs = venue_specs()
    maps = [(f"TRMAP{level}", _sprite_patch(_indexed_canvas(inset_image(spec), palette), (0, 0)))
            for level, spec in enumerate(specs, 1)]
    return [("PBHUD", bar), ("SBARDEF", json.dumps(data).encode("ascii")),
            *maps, *hud_art_lumps()]
