"""Export project-owned campaign content for an engine-neutral C++ game."""

import argparse
import ast
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import struct
import wave

from PIL import Image, ImageDraw

from build_expansion import ANIMATIONS, ATTACK_SHEETS, CANDIDATE
from build_toronto_wad import _doom_palette
from campaign_order import STOPS, SOURCE_TO_SLOT, remap_resource
from doom_geometry import read_wad
from expansion_cast import CAMPAIGN_ENEMIES
from expansion_music import (
    CAMPAIGN_TRACKS, MUSIC_DIR, STYLES, PRESENTATION_MUSIC, beats_per_bar,
    programs_for, campaign_music_lumps,
)
from expansion_presentation import candidate_material_images
from project_paths import ASSETS, ROOT, RELEASE
from npc_weapons import ATTACK_TIERS, attack_start, weapon_slot
from venue_scenery import catalog as decoration_catalog, export_sources as export_scenery_sources
from venue_walkers import BEAR_OUTBOUND, BEAR_RETURN, GIRL_OUTBOUND, GIRL_RETURN


OUTPUT = ASSETS / "Game"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def patch_image(payload, palette):
    width, height, left, top = struct.unpack_from("<4h", payload)
    if width <= 0 or height <= 0:
        raise ValueError("Invalid patch dimensions")
    image = Image.new("RGBA", (width, height))
    for x in range(width):
        cursor = struct.unpack_from("<I", payload, 8 + x * 4)[0]
        while payload[cursor] != 255:
            y, length = payload[cursor:cursor + 2]
            if y + length > height:
                raise ValueError("Patch post exceeds image")
            for offset, pixel in enumerate(payload[cursor + 3:cursor + 3 + length]):
                color = palette[pixel * 3:pixel * 3 + 3]
                image.putpixel((x, y + offset), (*color, 255))
            cursor += length + 4
    return image, {"width": width, "height": height, "left_offset": left, "top_offset": top}


def map_data(name, block):
    def text(raw):
        return raw.rstrip(b"\0").decode("ascii")

    vertices = list(struct.iter_unpack("<2h", block["VERTEXES"]))
    sides = [
        dict(x_offset=x, y_offset=y, upper=text(upper), lower=text(lower),
             middle=text(middle), sector=sector)
        for x, y, upper, lower, middle, sector in struct.iter_unpack("<hh8s8s8sh", block["SIDEDEFS"])
    ]
    sectors = [
        dict(floor=floor, ceiling=ceiling, floor_texture=text(ft), ceiling_texture=text(ct),
             light=light, special=special, tag=tag)
        for floor, ceiling, ft, ct, light, special, tag
        in struct.iter_unpack("<hh8s8shhh", block["SECTORS"])
    ]
    return {
        "id": name, "vertices": vertices, "sides": sides, "sectors": sectors,
        "lines": [dict(zip(("a", "b", "flags", "special", "tag", "front", "back"), line))
                  for line in struct.iter_unpack("<7h", block["LINEDEFS"])],
        "things": [dict(zip(("x", "y", "angle", "type", "flags"), thing))
                   for thing in struct.iter_unpack("<5h", block["THINGS"])],
    }


def level_map(level):
    image = Image.new("RGB", (1024, 768), (12, 21, 28))
    draw = ImageDraw.Draw(image)
    vertices = level["vertices"]
    min_x, max_x = min(x for x, _ in vertices), max(x for x, _ in vertices)
    min_y, max_y = min(y for _, y in vertices), max(y for _, y in vertices)
    scale = min(960 / max(1, max_x - min_x), 704 / max(1, max_y - min_y))
    ox = (1024 - (max_x - min_x) * scale) / 2
    oy = (768 - (max_y - min_y) * scale) / 2

    def point(x, y):
        return (round(ox + (x - min_x) * scale), round(768 - oy - (y - min_y) * scale))

    for line in level["lines"]:
        color = (246, 198, 83) if line["special"] == 52 else (99, 164, 164)
        draw.line((*point(*vertices[line["a"]]), *point(*vertices[line["b"]])), fill=color, width=2)
    for thing in level["things"]:
        if thing["type"] in (1, 5):
            x, y = point(thing["x"], thing["y"])
            color = (235, 82, 91) if thing["type"] == 1 else (80, 145, 255)
            draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=color)
    draw.text((12, 12), f'{level["id"]}  NORTH UP | RED START | BLUE ACCESS CARD', fill="white")
    level["map_transform"] = {
        "width": 1024, "height": 768, "scale": scale,
        "min_x": min_x, "min_y": min_y, "offset_x": ox, "offset_y": oy,
        "pixel_x": "offset_x + (world_x - min_x) * scale",
        "pixel_y": "height - offset_y - (world_y - min_y) * scale",
    }
    return image


def npc_catalog(patch):
    actors = []
    for enemy in CAMPAIGN_ENEMIES:
        record = asdict(enemy)
        record["animations"] = {
            "walk": list("ABCD"), "aim_fire_recover": list("EFG"),
            "pain": ["H"], "defeat": list("IJKLMN"), "idle": list("OP"),
        }
        record["states"] = [
            dict(id=enemy.state + i, frame=frame, tics=tics,
                 next=None if tics == -1 else enemy.state + next_index, action=action)
            for i, (frame, tics, next_index, action) in enumerate((
                ("O", 10, 1, "Look"), ("P", 10, 0, "Look"),
                ("A", 6, 3, "Chase"), ("B", 6, 4, "Chase"),
                ("C", 6, 5, "Chase"), ("D", 6, 2, "Chase"),
                ("E", enemy.attack_tics[0], 7, "FaceTarget"),
                ("F", enemy.attack_tics[1], 8, enemy.attack),
                ("G", enemy.attack_tics[2], 2, "FaceTarget"), ("H", 6, 2, "Pain"),
                ("I", 5, 11, "NULL"), ("J", 5, 12, "Scream"),
                ("K", 5, 13, "Fall"), ("L", 5, 14, "NULL"),
                ("M", 5, 15, "NULL"), ("N", -1, 0, "NULL"),
            ))
        ]
        if enemy.prefix in {"BVER", "RFOX", "GOOS", "CHIP", "BJAY", "GHOG",
                            "SOWL", "WOLV", "BLSQ", "STAG", "SWAN", "OTTR"}:
            record["sound_resources"] = [f"DSFRE{slot - 500:03}" for slot in enemy.sounds]
        else:
            record["sound_resources"] = {
                "DRON": ["DSCACSIT", "DSVIPAIN", "DSCACDTH", "DSBGACT"],
                "DINO": ["DSCYBSIT", "DSDMPAIN", "DSBRSDTH", "DSBSPACT"],
                "BEAR": ["DSSPISIT", "DSPEPAIN", "DSCYBDTH", "DSBSPWLK"],
                "PIGE": ["DSBSPSIT", "DSPOPAIN", "DSSPIDTH", "DSVILACT"],
                "ARMR": ["DSKNTSIT", "DSSKEPCH", "DSBSPDTH", "DSHOOF"],
                "WOLF": ["DSVILSIT", "DSVILATK", "DSVILDTH", "DSMETAL"],
            }[enemy.prefix]
        actors.append(record)
    actors.append({
        "title": "Raccoon gunner", "prefix": "POSS", "thing": 2, "doomednum": 3004,
        "height": 56, "radius": 20, "health": 20, "speed": 8, "map_name": "all",
        "attack": "PosAttack", "attack_tics": [10, 8, 8],
        "animations": {"walk": list("ABCD"), "aim_fire_recover": ["E", "F", "E"],
                       "pain": ["G"], "defeat": list("HIJKL"),
                       "extreme_defeat": list("MNOPQRS"), "raise": ["T", "U"],
                       "idle": ["V", "W"]},
        "sound_resources": ["DSBRSSIT", "DSMNPAIN", "DSSKLDTH", "DSDMACT"],
        "native_behavior": "Former Human; walk AABBCCDD at 4 tics; pain G 3+3 tics; "
                           "defeat H/I/J/K 5 tics then L terminal; idle V/W 10 tics.",
    })
    frame_fields = {int(number): {key: int(value) for key, value in
                                 re.findall(r"^(.+) = (-?\d+)$", body, re.M)}
                    for number, body in re.findall(r"Frame (\d+)\n(.*?)(?:\n\n)", patch, re.S)}
    actions = {int(number): action for number, action in
               re.findall(r"^FRAME (\d+) = (\w+)$", patch, re.M)}
    for index, record in enumerate([actors[-1], *actors[:-1]]):
        start = attack_start(index)
        slot = weapon_slot(record["height"])
        tier = ATTACK_TIERS[slot]
        states = {}
        for state in range(start, start + tier.rounds * 2 + 2):
            fields = frame_fields[state]
            frame = fields["Sprite subnumber"]
            states[str(state)] = dict(
                id=state, frame=chr(ord("A") + (frame & 32767)),
                fullbright=bool(frame & 32768), sprite_number=fields["Sprite number"],
                tics=fields["Duration"], next=fields["Next frame"], action=actions[state],
                args=[fields.get(f"Args{i}", 0) for i in range(1, 6)],
                misc1=fields.get("Unknown 1", 0), misc2=fields.get("Unknown 2", 0),
            )
        record.update(weapon_slot=slot, weapon_name={2: "Starter", 3: "Pump", 4: "Automatic"}[slot],
                      legacy_attack=record["attack"], attack="MonsterBulletAttack",
                      legacy_attack_tics=record["attack_tics"],
                      attack_tics=[tier.aim_tics, tier.shot_tics * tier.rounds, tier.recovery_tics],
                      round_cadence_tics=tier.shot_tics,
                      far_attack_state=start, pellets_per_shot=tier.pellets,
                      rounds_per_burst=tier.rounds, attack_chain_tics=tier.chain_tics,
                      programmed_expected_damage_per_minute=tier.expected_damage_per_minute,
                      damage_rate_scope="Attack-chain ceiling; AI, pain, sight and misses lower actual damage",
                      firing_sound={2: "DSPLASMA", 3: "DSSHOTGN", 4: "DSFRE048"}[slot],
                      damage_per_pellet="5 * random_integer(1,3)",
                      attack_states=states)
    return actors


def supplemental_pickup(kind):
    """Original portable icons for supplies whose WAD appearance is inherited."""
    image = Image.new("RGBA", (32, 32))
    draw = ImageDraw.Draw(image)
    dark, teal, gold = (21, 33, 39), (89, 205, 182), (246, 198, 83)
    if kind == "armour":
        draw.polygon(((8, 3), (12, 6), (19, 6), (23, 3), (28, 12),
                      (24, 16), (24, 28), (7, 28), (7, 16), (3, 12)),
                     fill=teal, outline=dark)
        draw.line((15, 8, 15, 26), fill=dark, width=2)
    else:
        draw.rounded_rectangle((4, 7, 27, 28), radius=3, fill=dark, outline=teal, width=2)
        draw.rectangle((11, 3, 20, 7), outline=gold, width=2)
        if kind == "backpack":
            draw.rectangle((9, 15, 22, 23), outline=gold, width=2)
        else:
            draw.rectangle((13, 11, 18, 24), fill=teal)
            draw.rectangle((9, 15, 22, 20), fill=teal)
    return image


def export(output=OUTPUT, wad=CANDIDATE):
    output, wad = Path(output).resolve(), Path(wad).resolve()
    lumps = read_wad(wad)
    assets = dict(lumps)
    for source, payload in campaign_music_lumps():
        name = remap_resource(source)
        if assets.get(name) != payload:
            raise ValueError(f"{wad.name}: {name} differs from the current soundtrack; "
                             "rebuild the matching campaign before exporting")
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "manifest.json"
    previous_files = set()
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(previous, dict) or not isinstance(previous.get("files"), list):
            raise ValueError(f"{manifest_path}: invalid generated export manifest")
        for entry in previous["files"]:
            relative = entry.get("path") if isinstance(entry, dict) else None
            if not isinstance(relative, str) or Path(relative).is_absolute():
                raise ValueError(f"{manifest_path}: invalid generated file path")
            path = (output / relative).resolve()
            if not path.is_relative_to(output):
                raise ValueError(f"{manifest_path}: generated path escapes export directory")
            previous_files.add(relative)
    palette = _doom_palette()
    files = []

    def target(relative):
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        files.append(relative)
        return path

    def save_json(relative, data):
        target(relative).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    sprites = {}
    inside = False
    for name, payload in lumps:
        if name == "S_START":
            inside = True
        elif name == "S_END":
            inside = False
        elif inside:
            image, metadata = patch_image(payload, palette)
            relative = f"Sprites/{name}.png"
            image.save(target(relative))
            sprites[name] = {**metadata, "path": relative}
    presentation = {}
    for name, payload in lumps:
        if name in {"PBHUD", "PBMAPTIP", "PBCNTRL", "TRVICTRY", "TRZOO", "TITLEPIC", "TRSTORY", "PTTREADY"} or name.startswith(("TRMAP", "TRI", "TRX", "TRL", "TRN", "TRON", "TROWN", "TROFF", "STF")):
            image, metadata = patch_image(payload, palette)
            relative = f"UI/{name}.png"
            image.save(target(relative))
            presentation[name] = {**metadata, "path": relative}

    walls, flats = candidate_material_images(palette)
    materials = {}
    for kind, images in (("Walls", walls), ("Flats", flats)):
        for name, image in images.items():
            relative = f"Materials/{kind}/{name}.png"
            image.convert("RGBA").save(target(relative))
            materials[name] = dict(path=relative, width=image.width, height=image.height, kind=kind)

    sounds = {}
    for name, payload in lumps:
        if name.startswith("DS"):
            format_id, rate, count = struct.unpack_from("<HHI", payload)
            if format_id != 3 or len(payload) != count + 8 or count <= 32:
                raise ValueError(f"{name}: invalid project DMX sound")
            relative = f"Audio/{name}.wav"
            with wave.open(str(target(relative)), "wb") as stream:
                stream.setparams((1, 1, rate, 0, "NONE", "not compressed"))
                stream.writeframes(payload[24:-16])
            sounds[name] = dict(path=relative, sample_rate=rate, channels=1, bits=8)

    music = []
    tracks = {track[0]: track for track in CAMPAIGN_TRACKS}
    for index, stop in enumerate(STOPS, 1):
        track = tracks[stop.source]
        map_id = f"E1M{index}"
        source_id = track[0]
        record = dict(map=map_id, title=track[1], bpm=track[2], style=STYLES[source_id],
                      beats_per_bar=beats_per_bar(source_id), midi_programs=programs_for(source_id),
                      commercial_samples=False, third_party_compositions=False,
                      third_party_music_license_required=False,
                      third_party_music_royalties_required=False)
        for extension in ("ogg", "mid"):
            relative = f"Music/{map_id}.{extension}"
            target(relative).write_bytes((MUSIC_DIR / f"{source_id}.{extension}").read_bytes())
            record[extension] = relative
        music.append(record)
    target("Music/provenance.json").write_bytes((MUSIC_DIR / "provenance.json").read_bytes())
    save_json("Music/presentation.json", {
        cue: dict(map=SOURCE_TO_SLOT[source],
                  ogg=f"Music/{SOURCE_TO_SLOT[source]}.ogg",
                  mid=f"Music/{SOURCE_TO_SLOT[source]}.mid")
        for cue, source in PRESENTATION_MUSIC.items()
    })

    levels = []
    for index, (name, _) in enumerate(lumps):
        if name not in {f"E1M{i}" for i in range(1, len(STOPS) + 1)}:
            continue
        level = map_data(name, dict(lumps[index + 1:index + 11]))
        stop = STOPS[int(name[-1]) - 1]
        level.update(title=stop.title, sky=stop.sky, next=f"E1M{int(name[-1]) + 1}"
                     if name != "E1M9" else None, units_per_metre=32)
        relative = f"Levels/{name}.png"
        level_map(level).save(target(relative))
        level["map_image"] = relative
        required = {sector[field] for sector in level["sectors"]
                    for field in ("floor_texture", "ceiling_texture")}
        required.update(side[field] for side in level["sides"] for field in ("upper", "lower", "middle"))
        missing = required - set(materials) - {"-", "F_SKY1"}
        if missing:
            raise ValueError(f"{name}: unexported materials {sorted(missing)}")
        save_json(f"Levels/{name}.json", level)
        levels.append(dict(id=name, title=stop.title, path=f"Levels/{name}.json", map_image=relative))

    actors = npc_catalog(assets["DEHACKED"].decode("ascii"))
    decorations = decoration_catalog()
    for item in decorations:
        for frame in item["frames"]:
            if frame["sprite"] not in sprites:
                raise ValueError(f"Unexported decoration sprite: {frame['sprite']}")
    save_json("decorations.json", decorations)
    from portal_gates import metadata as portal_metadata
    save_json("portal_gates.json", portal_metadata())
    export_scenery_sources()
    save_json("venue_walkers.json", {
        "simulation_hz": 35,
        "controllers": [
            dict(doomednum=15402, map="E1M6", role="polar_bear", sprite="ABWR",
                 height=72, radius=28, directions=8, walk_phases=4,
                 outbound_distance=BEAR_OUTBOUND, return_distance=BEAR_RETURN),
            dict(doomednum=15403, map="E1M2", role="wandering_girl_green", sprite="GRLG",
                 height=48, radius=12, directions=1, walk_phases=4,
                 outbound_distance=GIRL_OUTBOUND, return_distance=GIRL_RETURN),
            dict(doomednum=15404, map="E1M3", role="wandering_girl_purple", sprite="GRLP",
                 height=48, radius=12, directions=1, walk_phases=4,
                 outbound_distance=GIRL_OUTBOUND, return_distance=GIRL_RETURN),
        ],
        "native_behavior": "Each map thing is an invisible patrol controller, not a visible actor. "
                           "It spawns a fixed anchor, which spawns a grounded, solid, noncombat actor. "
                           "The actor acquires the nearby anchor once with FindTracer (one-block range); "
                           "the anchor then loses its temporary COUNTKILL flag and leaves the blockmap. "
                           "Neither map controllers nor walkers count as kills, and the anchor is "
                           "spawned without COUNTKILL before gaining it briefly for acquisition. "
                           "No Look, player target acquisition or MonsterProjectile chain is used. "
                           "Use the listed dimensions and directional walk animation; reverse at "
                           "the configured distances from the fixed anchor. "
                           "Native KEX actor and tracer definitions are in DEHACKED.txt.",
    })
    pickup_definitions = {
        1: dict(role="player_start"),
        5: dict(role="blue_access_card", sprite="BKEYA0", effect="unlock blue checkpoint"),
        8: dict(role="backpack", icon="backpack", effect="capacity 800; add 25 shared paint"),
        2001: dict(role="pump", sprite="SHOTA0", effect="own slot 3; native shared-ammo refill"),
        2002: dict(role="automatic", sprite="MGUNA0", effect="own slot 4; native shared-ammo refill"),
        2007: dict(role="paint_pod", sprite="CLIPA0", effect="add 25 paint, clamp to capacity"),
        2048: dict(role="paint_case", sprite="AMMOA0", effect="add 125 paint, clamp to capacity"),
        2012: dict(role="health_pack", icon="health", effect="add 25 health, clamp to 100"),
        2013: dict(role="bonus_health", icon="health", effect="add 100 health, clamp to 200"),
        2018: dict(role="armour", icon="armour", effect="set standard armour to 100 if lower"),
    }
    for kind in ("health", "armour", "backpack"):
        relative = f"Pickups/{kind}.png"
        supplemental_pickup(kind).save(target(relative))
    for record in pickup_definitions.values():
        if "icon" in record:
            record["path"] = f'Pickups/{record["icon"]}.png'
            record["provenance"] = "New original portable icon; not extracted stock WAD artwork"
    save_json("pickups.json", pickup_definitions)
    save_json("npcs.json", actors)
    save_json("weapons.json", {
        "simulation_hz": 35, "shared_ammo": dict(initial=50, capacity=400, backpack_capacity=800,
                                                pod=25, case=125),
        "weapons": [
            dict(slot=1, name="Harlequin mallet", prefix="PUNG", frames=list("ABCD"), ammo_per_shot=0,
                 attack="Punch", damage="2 * random_integer(1,10); berserk multiplies by 10"),
            dict(slot=2, name="Starter", prefix="PISG", frames=list("ABCDE"), ammo_per_shot=1,
                 attack="FirePistol", pellets=1, damage_per_pellet="5 * random_integer(1,3)"),
            dict(slot=3, name="Pump", prefix="SHTG", frames=list("ABCDE"), ammo_per_shot=7,
                 attack="FireShotgun", pellets=7, damage_per_pellet="5 * random_integer(1,3)"),
            dict(slot=4, name="Automatic", prefix="CHGG", frames=list("AB"), ammo_per_shot=1,
                 attack="FireCGun", rounds_per_cycle=2, damage_per_pellet="5 * random_integer(1,3)"),
        ],
        "note": "Artwork is exported exactly. Native player action timing/spread and unmodified "
                "inherited rules must be implemented in C++; DEHACKED.txt contains overrides, not a full engine.",
    })
    target("DEHACKED.txt").write_bytes(assets["DEHACKED"])
    target("UMAPINFO.txt").write_bytes(assets["UMAPINFO"])
    save_json("gameplay.json", {
        "simulation_hz": 35, "units_per_metre": 32, "initial_health": 100,
        "initial_armour": 0, "initial_weapons": [1, 2],
        "coordinate_system": "XY horizontal; +X east, +Y north, +Z up; angle degrees counterclockwise from +X",
        "sound_resource_order": ["alert", "pain", "death", "idle"],
        "native_enemy_attacks": {
            "MonsterBulletAttack": dict(horizontal_spread_degrees=5.625, vertical_spread_degrees=0,
                                       damage_per_pellet="5 * random_integer(1,3)",
                                       pellets="Per actor attack_states Args3",
                                       sound="Preceding PlaySound state; per-actor firing_sound"),
            "PosAttack": dict(pellets=1, damage_per_pellet="3 * random_integer(1,5)",
                              sound="DSPISTOL", legacy=True),
            "SPosAttack": dict(pellets=3, damage_per_pellet="3 * random_integer(1,5)",
                               sound="DSSHOTGN", legacy=True),
        },
        "native_inheritance": "This exports game content, not the Doom engine. Implement AI visibility, "
                              "movement, collision, RNG/spread, skill rules and native player action timing.",
        "map_rules": {"line_flag_1": "blocking", "line_flag_4": "two sided",
                      "thing_flags_1_2_4": "easy / medium / hard skill masks",
                      "thing_flag_8": "ambush behavior, not an extra skill",
                      "line_special_52": "normal exit",
                      "line_special_32": "blue-key door; consult level line specials and UMAPINFO",
                      "sector_special_9": "secret", "F_SKY1": "outdoor sky sentinel, not a texture file"},
        "introduction_things": "Types 15100..15108: once-only venue/TAB text trigger, not a solid enemy",
        "static_level_inset": {
            "images": {f"E1M{n}": f"UI/TRMAP{n}.png" for n in range(1, 10)},
            "native_marker_types": list(range(15300, 15304)),
            "native_key_items": [2, 3, 5, 6],
            "encoding": "Level number 1..9 in four bits; reset on each map; collected on first movement",
            "portable_behavior": "Select by current level ID directly; ignore native marker things. "
                                 "Internal noncombat state, not collectible progression keys.",
            "display": "Static north-up geometry, fixed spawn dot and north arrow; no live position or heading",
            "cheats": "All-keys cheat suppresses the inset until the next level",
        },
        "decoration_things": "Types 15200..15246: nonblocking scenery and cosmetic animation controllers; "
                             "resolve decorations.json, not NPC AI or pickup rules. "
                             "Sector geometry supplies intentional collision/occlusion.",
        "paint_effect": {"prefix": "PBLT", "durations_tics": [5, 85, 10, 5],
                         "nonblocking": True, "stationary": True},
        "unfinished_features": ["Live level radar", "Live compass", "Binding-aware input hints",
                                "Tab press/fill feedback", "Input-dismissed introductory HUD"],
    })
    save_json("sprites.json", sprites)
    save_json("materials.json", materials)
    save_json("audio.json", dict(sounds=sounds, music=music))
    save_json("levels.json", levels)
    save_json("presentation.json", presentation)
    image_inventory = []
    npc_sources = {animation[1] for animation in ANIMATIONS}
    attack_sources = {filename for filename, _ in ATTACK_SHEETS}
    for path in sorted(ASSETS.glob("*.png")):
        with Image.open(path) as image:
            role = ("active_npc_sheet" if path.name in npc_sources else
                    "active_attack_sheet" if path.name in attack_sources else
                    "materials" if path.name.startswith("materials_") else
                    "weapons" if path.name.startswith("paintball_") else
                    "skies" if path.name == "skies_toronto.png" else "legacy_reference_not_active")
            image_inventory.append(dict(path=path.name, width=image.width, height=image.height,
                                        role=role, mode=image.mode, sha256=digest(path)))
    save_json("source_images.json", image_inventory)
    script_inventory = []
    for path in sorted((ROOT / "scripts").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        script_inventory.append({
            "path": path.name, "description": ast.get_docstring(tree),
            "category": "tests" if path.name.startswith("test_") else
                        "native_validation" if path.name.startswith("verify_") else
                        "build_and_export" if path.name.startswith(("build_", "export_", "prepare_")) else
                        "content_and_helpers",
            "definitions": [node.name for node in tree.body
                            if isinstance(node, (ast.FunctionDef, ast.ClassDef))],
        })
    save_json("scripts.json", script_inventory)
    retired_files = ["UI/PBMAPTIP.png", "UI/PBCNTRL.png", "Sprites/VHRDB0.png"]
    retired_files.extend(f"Sprites/{prefix}{frame}0.png"
                         for prefix in ("VPIT", "VCAT") for frame in "ABCDE")
    for retired in retired_files:
        if retired not in files:
            (output / retired).unlink(missing_ok=True)
    for retired in previous_files - set(files):
        (output / retired).unlink(missing_ok=True)
    source_is_published = RELEASE.exists() and wad.read_bytes() == RELEASE.read_bytes()
    manifest = {
        "schema_version": 1, "source_wad": wad.name, "source_sha256": digest(wad),
        "published_wad_sha256": digest(RELEASE) if RELEASE.exists() else None,
        "source_is_published": source_is_published,
        "release_status": "published" if source_is_published else
                          "candidate only; not yet published",
        "sprite_count": len(sprites), "npc_count": len(actors),
        "decoration_count": len(decorations), "level_count": len(levels),
        "excluded": ["Commercial IWAD files, stock textures, stock HUD face/font/key artwork",
                     "Game executable, third-party reference imagery, runtime save files"],
        "pending_not_implemented": [
            "KEX-native HUD-style transition typography; embedded patches still render stock-red text",
            "Full native mallet-motion and revised museum/street traversal acceptance",
            "Optional live compass; approved KEX fallback is a static current-level inset",
            "Live enemy radar and input-reactive HUD",
        ],
        "files": [dict(path=relative, sha256=digest(output / relative)) for relative in sorted(files)],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Exported {len(files)} files: {len(actors)} NPCs, {len(sprites)} sprites, "
          f"{len(levels)} levels to {output}")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--wad", type=Path, default=CANDIDATE)
    args = parser.parse_args()
    export(args.output, args.wad)
