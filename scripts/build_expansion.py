import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

from shapely.geometry import LineString, Point

from build_toronto_wad import (
    NPC_ANIMATIONS, NPC_ATTACK_SHEETS, NPC_SIZES,
    _animation_patch, _doom_iwad, _sprite_lumps, _sprite_patch, _validate_wad,
)
from doom_geometry import build_nodes, replace_validated
from expansion_audio import NEW_SOUND_SPECS, expansion_sound_lumps
from expansion_cast import CAMPAIGN_ENEMIES, NEW_ANIMATIONS, NEW_ATTACK_SHEETS, map_enemies
from expansion_presentation import CAMPAIGN_SKIES, candidate_material_images, finale_lumps
from expansion_music import CAMPAIGN_TRACKS, campaign_music_lumps
from campaign_feedback import (FIND_TIP_DOOMEDNUM, INTRO_DOOMEDNUM, NAME_TIP_DOOMEDNUM,
                               SPACEBAR_TIP_DOOMEDNUM, TAB_TIP_DOOMEDNUM,
                               feedback_sprites, gameplay_patch, hud_lumps)
from paintball_audio import SOUND_SPECS, sound_lumps
from toronto_materials import material_lumps, texture_records
from toronto_venues import venue_specs
from campaign_order import remap_resource
from campaign_overworld import overworld_lumps
from npc_weapons import NPC_SOUND_SPECS, weapon_sounds
from venue_scenery import BY_ID, BY_KIND, FAN_KINDS, sprite_lumps as scenery_sprites
from venue_walkers import gameplay_patch as walkers_patch, sprite_lumps as walker_sprites
from portal_gates import gameplay_patch as portals_patch, sprite_lumps as portal_sprites, place_gate
from portal_gates import EMITTER_ID, PANEL_ID


from project_paths import ROOT, CANDIDATE, RELEASE, LEGACY_RELEASE, ORIGINAL_BACKUP
ANIMATIONS = NPC_ANIMATIONS + NEW_ANIMATIONS
ATTACK_SHEETS = NPC_ATTACK_SHEETS + NEW_ATTACK_SHEETS
SIZES = {**NPC_SIZES, **{e.prefix: (e.thing, e.height, e.radius) for e in CAMPAIGN_ENEMIES}}


def campaign_dehacked(specs):
    base = gameplay_patch(ANIMATIONS, CAMPAIGN_ENEMIES, SIZES, specs).decode("ascii")
    return (base + "\n" + walkers_patch() + "\n" + portals_patch()).encode("ascii")


def populate(spec, venue):
    geometry = venue.geometry
    occupied = [(x, y, min(BY_KIND[kind].width // 4, 64)) for x, y, kind in spec.scenery]
    actor_heights = {1: 56, 3004: 56, **{e.doomednum: e.height for e in CAMPAIGN_ENEMIES}}

    def place(center, kind, radius=16, angle=0, skills=7, sheltered=False):
        cx, cy = center
        candidates = [(round(cx), round(cy))]
        for distance in ((80, 140, 220, 320, 440, 600, 800, 1000) if sheltered
                         else (80, 140, 220, 320, 440)):
            candidates.extend((round(cx + distance * math.cos(a * math.pi / 4)),
                               round(cy + distance * math.sin(a * math.pi / 4))) for a in range(8))
        for x, y in candidates:
            if not venue.clear_at(x, y, radius + 8):
                continue
            sector = geometry.sectors[venue.sector_at(x, y)]
            if sector.ceiling - sector.floor < actor_heights.get(kind, 16) + 4:
                continue
            if sheltered and not LineString((spec.start, (x, y))).intersects(venue.solids.buffer(-4)):
                continue
            if any(math.hypot(x - ox, y - oy) < radius + other + 16 for ox, oy, other in occupied):
                continue
            geometry.thing(x, y, kind, angle=angle, skills=skills)
            occupied.append((x, y, radius))
            return x, y
        raise ValueError(f"{spec.name}: cannot safely place thing {kind} near {center}")

    a, b = spec.routes[0][:2]
    facing = round(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))) % 360
    place(spec.start, 1, angle=facing)
    # Union pedestrians were replaced by waiting platform commuters; only the
    # arena mascot and the two wandering girls remain patrol walkers.
    if spec.title == "Scotiabank Arena":
        place((350, -700), 15402, radius=28, angle=270)
    elif spec.title == "Queen's Park":
        place((0, 300), 15403, angle=90)
    elif spec.title == "Sankofa Square":
        place((-1300, -1100), 15404, angle=0)
    geometry.thing(*spec.start, INTRO_DOOMEDNUM + int(spec.name[-1]) - 1)
    from level_inset import place_markers
    place_markers(geometry, int(spec.name[-1]), spec.start)
    for x, y, kind in spec.scenery:
        geometry.thing(x, y, BY_KIND[kind].doomednum,
                       angle=spec.scenery_angles.get((x, y, kind), 0))
    place_gate(geometry, spec)
    primary, secondary = map_enemies(spec.name)
    roles = {"gunner": (3004, 20), "primary": (primary.doomednum, primary.radius),
             "secondary": (secondary.doomednum, secondary.radius)}
    for i, encounter in enumerate(spec.encounters):
        for j, role in enumerate(encounter.roles):
            kind, radius = roles[role]
            x, y = encounter.center
            skills = 7 if i < 2 or j == 0 else (6 if i % 2 == 0 else 4)
            place((x + (j - 1) * 120, y), kind, radius, encounter.facing, skills | 8, sheltered=True)

    main = LineString(spec.routes[0])
    # Pistol starts get early pump access and generous reserve ammunition.
    key_position = None
    for fraction, kind in ((0.015, 2001), (0.03, 2048), (0.045, 2007),
                           (0.06, 2018), (0.35, 2002), (0.62, 5)):
        placed = place(main.interpolate(fraction, normalized=True).coords[0], kind)
        if kind == 5:
            key_position = placed
    # Ambient route tips: the Tab-map reminder sits roughly a minute of play in,
    # the objective and venue name repeat intermittently, and spacebar advice
    # accompanies the Portal Key itself.
    level = int(spec.name[-1])
    for route in spec.routes:
        line = LineString(route)
        for fraction, tip in ((0.25, FIND_TIP_DOOMEDNUM), (0.45, TAB_TIP_DOOMEDNUM),
                              (0.58, NAME_TIP_DOOMEDNUM + level - 1),
                              (0.72, FIND_TIP_DOOMEDNUM)):
            place(line.interpolate(fraction, normalized=True).coords[0], tip)
    place((key_position[0] + 48, key_position[1]), SPACEBAR_TIP_DOOMEDNUM)
    for fraction in (0.18, 0.42, 0.62, 0.82):
        point = main.interpolate(fraction, normalized=True)
        place(point.coords[0], 2048)
        place((point.x + 95, point.y), 2048 if fraction in (0.18, 0.62) else 2007)
        place((point.x - 95, point.y), 2012)
    for region in spec.regions:
        if region.title == "Optional supply cache":
            center = region.polygon.representative_point()
            place(center.coords[0], 2013)
            place((center.x + 80, center.y), 2048)
    return geometry


def campaign_mapinfo(specs):
    blocks = []
    if len(specs) != len(CAMPAIGN_SKIES) or len(specs) != len(CAMPAIGN_TRACKS):
        raise ValueError("Every campaign map needs its own sky and soundtrack")
    for i, (spec, sky) in enumerate(zip(specs, CAMPAIGN_SKIES)):
        # One campaign episode replaces the IWAD's episode menu, so New Game
        # leads straight into Paint the Town instead of leftover vanilla maps.
        opening = ('    episode = clear\n'
                   '    episode = "M_EPI1", "Paint the Town", "p"\n') if i == 0 else ""
        if i == len(specs) - 1:
            # The campaign ends directly on the victory splash; no typewriter
            # story screen plays between the statistics and the end picture.
            ending = (
                '    endpic = "TRVICTRY"\n'
                '    intertext = clear\n'
                '    intertextsecret = clear\n'
                '    intermusic = "D_E1M9"\n'
            )
        else:
            next_map = specs[i + 1].name
            ending = (f'    next = "{next_map}"\n    nextsecret = "{next_map}"\n'
                      '    endgame = false\n'
                      '    intertext = clear\n    intertextsecret = clear\n')
            if i == 7:
                # KEX skips the ordinary entering screen after episode slot 8.
                ending = (f'    next = "{next_map}"\n    nextsecret = "{next_map}"\n'
                          '    endgame = false\n'
                          '    intertext = "NEXT STOP: TORONTO ZOO"\n'
                          '    interbackdrop = "TRZOO"\n'
                          '    intermusic = "D_E1M9"\n')
        music = f"D_{spec.name}"
        blocks.append(
            f'map {spec.name}\n{{\n{opening}    levelname = "{spec.title}"\n'
            f'    skytexture = "{sky}"\n    music = "{music}"\n'
            f'    bossaction = clear\n    nointermission = false\n'
            f'    exitpic = "TRX{i + 1:02}"\n    enterpic = "TRI{i + 1:02}"\n'
            f'    levelpic = "TRL{i + 1:02}"\n'
            f'{ending}}}\n'
        )
    return "\n".join(blocks).encode("ascii")


def validate_candidate(path):
    specs = venue_specs()
    result = _validate_wad(
        path, [{"name": s.name, "title": s.title, "exit_lines": 8} for s in specs], ANIMATIONS,
        CAMPAIGN_ENEMIES, SOUND_SPECS + NEW_SOUND_SPECS + NPC_SOUND_SPECS,
        dehacked=campaign_dehacked(specs),
        soundtrack=[(remap_resource(name), data) for name, data in campaign_music_lumps()],
    )
    from doom_geometry import read_wad
    lumps = read_wad(path)
    assets = dict(lumps)
    if assets.get("UMAPINFO") != campaign_mapinfo(specs):
        raise ValueError("Nine-map campaign routing is missing or incorrect")
    validate_resources(lumps, _doom_iwad(), specs)
    for i, (name, _) in enumerate(lumps):
        if name not in {s.name for s in specs}:
            continue
        things = list(struct.iter_unpack("<5h", lumps[i + 1][1]))
        spec = next(s for s in specs if s.name == name)
        venue = spec.compile()
        walker_ids = {15402, 15403, 15404}
        expected_walkers = {"Scotiabank Arena": 1,
                            "Queen's Park": 1, "Sankofa Square": 1}.get(spec.title, 0)
        if sum(t[3] in walker_ids for t in things) != expected_walkers:
            raise ValueError(f"{name}: expected {expected_walkers} venue walker controllers")
        if sum(t[3] == INTRO_DOOMEDNUM + int(name[-1]) - 1 for t in things) != 1:
            raise ValueError(f"{name}: expected exactly one level introduction")
        if sum(t[3] == 5 for t in things) != 1:
            raise ValueError(f"{name}: expected exactly one haloed blue key")
        if any(t[3] in (2008, 2049) for t in things):
            raise ValueError(f"{name}: shell-only pickups are not shared paintballs")
        radii = {1: 16, 3004: 20, **{e.doomednum: e.radius for e in CAMPAIGN_ENEMIES}}
        heights = {1: 56, 3004: 56, **{e.doomednum: e.height for e in CAMPAIGN_ENEMIES}}
        solids = []
        from level_inset import MARKER_DOOMEDNUM
        expected_markers = {MARKER_DOOMEDNUM + bit for bit in range(4)
                            if int(name[-1]) & (1 << bit)}
        actual_markers = [t for t in things if MARKER_DOOMEDNUM <= t[3] < MARKER_DOOMEDNUM + 4]
        if ({t[3] for t in actual_markers} != expected_markers
                or len(actual_markers) != len(expected_markers)
                or any((t[0], t[1]) != spec.start or t[4] != 7 for t in actual_markers)):
            raise ValueError(f"{name}: incorrect level-local map selection markers")
        for x, y, _, kind, flags in things:
            if kind in (EMITTER_ID, PANEL_ID):
                if not venue.walkable.covers(Point(x, y)):
                    raise ValueError(f"{name}: blocked portal control {kind}")
                continue
            if MARKER_DOOMEDNUM <= kind < MARKER_DOOMEDNUM + 4:
                continue
            if INTRO_DOOMEDNUM <= kind < INTRO_DOOMEDNUM + 9:
                if kind != INTRO_DOOMEDNUM + int(name[-1]) - 1 or (x, y) != spec.start:
                    raise ValueError(f"{name}: wrong level introduction trigger")
                continue
            if kind in BY_ID:
                decoration = BY_ID[kind]
                spectator = decoration.kind in FAN_KINDS
                if spectator and not any(p.covers(Point(x, y)) and r.solid
                                         and r.title.startswith("Ascending seating row")
                                         for p, _, r in venue.faces):
                    raise ValueError(f"{name}: spectator is not grounded on seating")
                if not spectator and not venue.clear_at(x, y, 4):
                    raise ValueError(f"{name}: decoration in solid cover: {decoration.title} at {(x, y)}")
                sector = venue.geometry.sectors[venue.sector_at(x, y)]
                if sector.ceiling - sector.floor < decoration.height:
                    raise ValueError(f"{name}: decoration lacks headroom: {decoration.title}")
                continue
            radius = radii.get(kind, 16)
            if not venue.clear_at(x, y, radius + 8):
                raise ValueError(f"{name}: blocked spawn {kind} at {(x, y)}")
            sector = venue.geometry.sectors[venue.sector_at(x, y)]
            if sector.ceiling - sector.floor < heights.get(kind, 16) + 4:
                raise ValueError(f"{name}: insufficient spawn headroom for {kind}")
            if kind in radii and kind != 1:
                if not LineString((spec.start, (x, y))).intersects(venue.solids.buffer(-4)):
                    raise ValueError(f"{name}: enemy can see the player start")
            for ox, oy, other, other_flags in solids:
                if flags & other_flags & 7 and math.hypot(x - ox, y - oy) < radius + other:
                    raise ValueError(f"{name}: overlapping spawns")
            solids.append((x, y, radius, flags))
        for skill in (1, 2, 4):
            kinds = {t[3] for t in things if t[4] & skill}
            if not {1, 5, 3004, 2001, 2002, 2012, *(e.doomednum for e in map_enemies(name))} <= kinds:
                raise ValueError(f"{name}: skill {skill} lacks a complete playable roster/loadout")
        checkpoint = next(r for r in spec.regions if r.title == "Blue-key exit checkpoint")
        approach = venue.walkable.difference(checkpoint.polygon).buffer(-16)
        if approach.geom_type != "Polygon" or not approach.covers(Point(spec.start)):
            raise ValueError(f"{name}: closed exit disconnects the public routes")
        for x, y, _, kind, _ in things:
            if kind == 5 and not approach.covers(Point(x, y)):
                raise ValueError(f"{name}: blue key is not reachable before opening the exit")
    return result


def validate_resources(lumps, iwad, specs=None):
    specs = venue_specs() if specs is None else specs
    assets = {name.upper(): data for name, data in (*iwad.items(), *lumps)}
    sprite_rotations = {}
    in_sprites = False
    for name, _ in lumps:
        if name == "S_START":
            in_sprites = True
        elif name == "S_END":
            in_sprites = False
        elif in_sprites and len(name) == 6 and name[-1].isdigit():
            sprite_rotations.setdefault(name[:5], set()).add(int(name[-1]))
    for frame, rotations in sprite_rotations.items():
        if 0 in rotations and len(rotations) > 1:
            raise ValueError(f"Sprite {frame} mixes billboard and directional artwork")
    for name, expected in (*feedback_sprites(), *hud_lumps(specs), *finale_lumps(), *overworld_lumps()):
        if assets.get(name) != expected:
            raise ValueError(f"Missing or incorrect campaign feedback resource: {name}")
    for name, expected in scenery_sprites():
        if assets.get(name) != expected:
            raise ValueError(f"Missing or incorrect venue scenery sprite: {name}")
    for name, expected in walker_sprites():
        if assets.get(name) != expected:
            raise ValueError(f"Missing or incorrect venue walker sprite: {name}")
    for name, expected in portal_sprites():
        if assets.get(name) != expected:
            raise ValueError(f"Missing or incorrect portal sprite: {name}")
    textures = set()
    pnames = assets["PNAMES"]
    patch_count = struct.unpack_from("<i", pnames)[0]
    patch_names = [pnames[4 + i * 8:12 + i * 8].rstrip(b"\0").decode("ascii").upper()
                   for i in range(patch_count)]
    for directory in ("TEXTURE1", "TEXTURE2"):
        if directory not in assets:
            continue
        for record in texture_records(assets[directory]):
            textures.add(record[:8].rstrip(b"\0").decode("ascii"))
            for _, _, patch, _, _ in struct.iter_unpack("<5h", record[22:]):
                if not 0 <= patch < patch_count or patch_names[patch] not in assets:
                    raise ValueError(f"Texture {record[:8]!r} references missing patch {patch}: "
                                     f"{patch_names[patch] if 0 <= patch < patch_count else 'out of range'}")
    for sky in CAMPAIGN_SKIES:
        if sky not in textures:
            raise ValueError(f"Missing campaign sky: {sky}")
    for name, *_ in CAMPAIGN_TRACKS:
        for mode in ("D", "O", "H"):
            resource = f"{mode}_{name}"
            if not assets.get(resource, b"").startswith(b"OggS"):
                raise ValueError(f"Missing campaign music: {resource}")
    for name, payload in lumps:
        if name == "SIDEDEFS":
            for _, _, upper, lower, middle, _ in struct.iter_unpack("<hh8s8s8sh", payload):
                for raw in (upper, lower, middle):
                    texture = raw.rstrip(b"\0").decode("ascii")
                    if texture != "-" and texture not in textures:
                        raise ValueError(f"Missing wall texture: {texture}")
        elif name == "SECTORS":
            for _, _, floor, ceiling, _, _, _ in struct.iter_unpack("<hh8s8shhh", payload):
                for raw in (floor, ceiling):
                    flat = raw.rstrip(b"\0").decode("ascii")
                    if flat != "F_SKY1" and len(assets.get(flat, b"")) != 4096:
                        raise ValueError(f"Missing or invalid flat: {flat}")


def publication_inputs(path):
    expected = "902be83dd2d04caebabbd309823ac90363216d2c362c8b4dffa7f428d9c766a9"
    backup = ORIGINAL_BACKUP
    if hashlib.sha256(backup.read_bytes()).hexdigest() != expected:
        raise ValueError("The verified three-map backup is missing or changed; release was not replaced")
    if Path(path).resolve() in {backup.resolve(), LEGACY_RELEASE.resolve(), CANDIDATE.resolve()}:
        raise ValueError("Never overwrite a historical release, original backup or candidate")
    digest = hashlib.sha256(CANDIDATE.read_bytes()).hexdigest()
    proof_path = ROOT / "runtime_validation" / "union-stability-results.json"
    if not proof_path.exists():
        raise ValueError("Publishing is blocked pending native Union freeze/stability acceptance")
    verify_union_stability_evidence(digest, json.loads(proof_path.read_text()))
    return digest


def verify_union_stability_evidence(digest, proof):
    required = {
        "commuters_present", "commuters_static", "commuter_animation",
        "nathan_to_union", "save_load", "extended_play",
    }
    samples = proof.get("simulation_tics", [])
    if (proof.get("wad_sha256") != digest
            or set(proof.get("checks", {})) != required
            or any(value is not True for value in proof["checks"].values())
            or not isinstance(proof.get("elapsed_seconds"), (int, float))
            or not math.isfinite(proof["elapsed_seconds"])
            or proof["elapsed_seconds"] < 120
            or not isinstance(samples, list)
            or len(samples) < 5
            or any(type(tic) is not int or tic < 0 for tic in samples)
            or any(b <= a for a, b in zip(samples, samples[1:]))
            or samples[-1] - samples[0] < 120 * 35):
        raise ValueError("Publishing requires checksum-matched native Union stability/progress proof")


def verify_kex_startup_evidence(digest, runtime, directory):
    maps = {f"E1M{i}" for i in range(1, 10)}
    if (len(runtime) != 9 or {row["map"] for row in runtime} != maps
            or any(row.get("wad_sha256") != digest
                   or row.get("startup_and_music") != "passed" for row in runtime)):
        raise ValueError("Publishing requires checksum-matched nine-map KEX startup proofs")
    logs = {}
    for row in runtime:
        name = f"{row['map']}-stdout.txt"
        payload = (directory / name).read_bytes()
        text = payload.decode("utf-8", errors="replace")
        required = (f"adding {CANDIDATE.name}", f"{row['map']}: {row['title']}",
                    f"Playing 'D_{row['map']}.ogg'",
                    "P_SetupLevel: Using limit-removing structures")
        failures = ("parse error", "exception caught", "game-specific exception",
                    "r_texturenumforname:", "r_initsprites:", "unknown thing type",
                    "invalid code pointer", "unknown code pointer", "bad sfx",
                    "i_error:", "segmentation")
        if (not all(marker in text for marker in required)
                or any(marker in text.lower() for marker in failures)):
            raise ValueError(f"{row['map']}: missing initialization or KEX error in native log")
        logs[name] = hashlib.sha256(payload).hexdigest()
    return logs


def publish_kex_candidate(path=RELEASE):
    """Explicit startup-verified release, without claiming interactive acceptance."""
    from doom_geometry import read_wad

    digest = publication_inputs(path)
    directory = ROOT / "runtime_validation"
    runtime = json.loads((directory / "runtime-results.json").read_text())
    logs = verify_kex_startup_evidence(digest, runtime, directory)
    evidence = {}
    for relative in (
        "union-stability-results.json",
        "portal-gates/portal-results.json",
        "candidate-walker-inmap/walker-results.json",
        "finale-results.json",
        "mallet-art-results.json",
        "npc-weapons-results.json",
        "candidate-revisions/street-and-museum/scene-results.json",
        "visual-fixes/scene-results.json",
    ):
        proof_path = directory / relative
        if not proof_path.exists():
            continue
        payload = proof_path.read_bytes()
        proof = json.loads(payload)
        if proof.get("wad_sha256", proof.get("candidate_sha256")) != digest:
            raise ValueError(f"Publication evidence does not match the candidate: {relative}")
        evidence[relative] = hashlib.sha256(payload).hexdigest()
    result = replace_validated(path, read_wad(CANDIDATE), validate_candidate)
    if hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest:
        raise ValueError("Published WAD differs from the KEX-verified candidate")
    report = {
        "wad_sha256": digest,
        "release": Path(path).name,
        "validation_scope": "Native KEX nine-map startup/music and structural/resource validation",
        "full_feature_acceptance": False,
        "native_logs_sha256": logs,
        "native_reports_sha256": evidence,
        "maps": runtime,
        "unverified": [
            "HUD-style native transition typography: KEX still renders stock-red labels/digits",
            "Full mallet-motion realism; native held poses and melee smoke only",
            "Full revised campaign combat/traversal and museum/street animation acceptance",
            "Title timing and native dugout hitscan protection",
        ],
        "reason": "User explicitly requested publication of the playable KEX build. "
                  "Checksum-bound supplemental native reports retain their individual scopes; "
                  "full interactive feature acceptance is not claimed.",
    }
    (directory / "kex-publication.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Published KEX startup-verified WAD: {path}; {result[0]} lumps, {result[1]:,} bytes")
    print("Interactive feature acceptance remains unverified; see runtime_validation/kex-publication.json")
    return path


def publish_candidate(path=RELEASE):
    from doom_geometry import read_wad
    digest = publication_inputs(path)
    runtime = json.loads((ROOT / "runtime_validation" / "runtime-results.json").read_text())
    maps = {f"E1M{i}" for i in range(1, 10)}
    checked = {r["map"] for r in runtime
               if r.get("wad_sha256") == digest and r.get("startup_and_music") == "passed"}
    proofs = [ROOT / "runtime_validation" / f"checkpoint-{mode}-results.json"
              for mode in ("live", "demo")]
    checkpoints = [json.loads(proof.read_text()) for proof in proofs if proof.exists()]
    verified = any(set(proof["maps_reached"]) == maps and proof.get("wad_sha256") == digest
                   for proof in checkpoints)
    if checked != maps or not verified:
        raise ValueError("Publishing requires checksum-matched nine-map KEX startup and checkpoint proofs")
    inset = json.loads((ROOT / "runtime_validation" / "static-inset-results.json").read_text())
    selections = inset.get("maps", [])
    if (inset.get("wad_sha256") != digest or inset.get("save_load_preserved") is not True
            or {item["level"] for item in selections} != set(range(1, 10))
            or any(item["selected"] != item["level"]
                   or not 0 <= item["mean_pixel_error"] < 6 for item in selections)):
        raise ValueError("Publishing requires checksum-matched native static-inset selection/save-load proof")
    feedback = json.loads((ROOT / "runtime_validation" / "feedback-results.json").read_text())
    expected_checks = {
        "starter": 149, "pump": 142, "automatic": 140,
        "paint_visible_stationary_and_removed": True, "empty": [0, 400],
        "pump_below_seven": [6, 400], "pump_exactly_seven": [0, 400],
        "pod_clamped": [400, 400], "backpack": [425, 800],
    }
    if feedback.get("wad_sha256") != digest or feedback.get("checks") != expected_checks:
        raise ValueError("Publishing requires checksum-matched native ammo/paint acceptance proof")
    finale = json.loads((ROOT / "runtime_validation" / "finale-results.json").read_text())
    if (finale.get("wad_sha256") != digest or finale.get("actual_keyed_exit") is not True
            or finale.get("victory_screen_matches") is not True
            or finale.get("stable_after_victory") is not True):
        raise ValueError("Publishing requires checksum-matched final-exit/victory-screen proof")
    overworld = json.loads((ROOT / "runtime_validation" / "overworld-results.json").read_text())
    stages = overworld.get("stages", [])
    if (overworld.get("wad_sha256") != digest
            or {stage["from"] for stage in stages} != {1, 4, 8}
            or any(stage["to"] != stage["from"] + 1
                   or stage["results_background_match"] < 0.85
                   or stage["entering_background_match"] < 0.85
                   or not 0 <= stage.get("progress_marker_error", 999) < 22
                   for stage in stages)):
        raise ValueError("Publishing requires checksum-matched native overworld results/entering proof")
    acceptance_path = ROOT / "runtime_validation" / "paint-town-acceptance.json"
    if not acceptance_path.exists():
        raise ValueError("Publishing requires completed Paint the Town native feature acceptance")
    acceptance = json.loads(acceptance_path.read_text())
    required_features = {
        "startup_presentation", "solid_walkers_and_save_load", "arena_life",
        "stage_band", "directional_baseball_and_save_load", "dugout_access_and_shot_protection",
        "fourteen_unique_zoo_species", "selected_marker_feedback", "keyed_portal_reveals",
        "ending_story_and_victory",
    }
    if (acceptance.get("wad_sha256") != digest
            or set(acceptance.get("checks", {})) != required_features
            or any(value is not True for value in acceptance["checks"].values())):
        raise ValueError("Publishing requires checksum-matched acceptance of every Paint the Town feature")
    result = replace_validated(path, read_wad(CANDIDATE), validate_candidate)
    print(f"Published nine-map WAD: {path}; {result[0]} lumps, {result[1]:,} bytes")
    return path


def build(path=CANDIDATE):
    if Path(path).resolve() in {RELEASE.resolve(), LEGACY_RELEASE.resolve(), ORIGINAL_BACKUP.resolve()}:
        raise ValueError("Build a candidate first, then use --publish after KEX validation")
    specs = venue_specs()
    lumps = []
    for spec in specs:
        venue = spec.compile()
        geometry = populate(spec, venue)
        lumps.extend(build_nodes(geometry.lumps()))
        print(f"{spec.name}: {spec.title}; {len(geometry.lines)} lines, {len(geometry.things)} spawns")
    iwad = _doom_iwad()
    materials = material_lumps(iwad, _sprite_patch, candidate_material_images(iwad["PLAYPAL"][:768]))
    lumps.extend((name, data) for name, data in materials if name != "UMAPINFO")
    lumps.append(("UMAPINFO", campaign_mapinfo(specs)))
    sprites = _sprite_lumps(ANIMATIONS, SIZES, ATTACK_SHEETS, campaign_weapons=True)
    lumps.extend(sprites[:-1] + feedback_sprites() + list(scenery_sprites())
                 + list(walker_sprites()) + portal_sprites() + sprites[-1:])
    lumps.extend(hud_lumps(specs))
    lumps.extend(finale_lumps())
    lumps.extend(overworld_lumps())
    lumps.append(("DEHACKED", campaign_dehacked(specs)))
    lumps.extend(sound_lumps())
    lumps.extend(expansion_sound_lumps())
    lumps.extend(weapon_sounds())
    lumps.extend((remap_resource(name), data) for name, data in campaign_music_lumps())
    count, size = replace_validated(path, lumps, validate_candidate)
    print(f"Validated experimental nine-map build: {path}; {count} lumps, {size:,} bytes")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build a nine-map candidate or publish a checksum-verified KEX build.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--output", type=Path, default=CANDIDATE)
    group.add_argument("--publish", action="store_true")
    group.add_argument("--publish-kex-verified", action="store_true",
                       help="Publish after nine native KEX starts; explicitly records incomplete feature acceptance")
    args = parser.parse_args()
    if args.publish_kex_verified:
        publish_kex_candidate()
    elif args.publish:
        publish_candidate()
    else:
        build(args.output)
