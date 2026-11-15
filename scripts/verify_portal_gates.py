"""Verify integrated keyed sky columns in actual-geometry KEX fixtures."""

import argparse
import hashlib
import json
import shutil
import struct
import time
from uuid import uuid4

from build_expansion import CANDIDATE
from doom_geometry import read_wad, write_wad
from portal_gates import BEAM_SPRITE, BEAM_THING, DUST_SPRITE, EMITTER_THING, SEGMENT_HEIGHT, SEGMENTS
from project_paths import ROOT
from toronto_venues import venue_specs
from verify_campaign_feedback import LOGS, OwnedGame
from verify_venue_scenery import build_fixture
from verify_venue_walkers import native_level_state, walker_records


def build_portal_fixture(path, number, side="south"):
    spec = venue_specs()[number - 1]
    checkpoint = next(region for region in spec.regions
                      if region.title == "Blue-key exit checkpoint")
    x, y = spec.exit_center
    north = side == "north"
    start_y = round(checkpoint.polygon.bounds[3 if north else 1]) + (40 if north else -40)
    build_fixture(path, number, x, start_y, 270 if north else 90)
    lumps = read_wad(path)
    current = None
    result = []
    for name, data in lumps:
        if name.startswith("E1M") and len(name) == 4:
            current = int(name[-1])
        if name == "THINGS" and current == number:
            data += struct.pack("<5h", x + (-72 if north else 72), start_y, 0, 5, 7)
        result.append((name, data))
    write_wad(path, result)
    return spec, start_y


def beam_records(path):
    return walker_records(path, BEAM_SPRITE, BEAM_THING - 1, (0, 0))


def dust_records(path):
    return walker_records(path, DUST_SPRITE, EMITTER_THING - 1, (0, 0))


def verify_map(number, output, side="south"):
    prefix = f"{number}-{side}" if side != "south" else str(number)
    fixture = output / f"portal-{prefix}-fixture.wad"
    native_save = LOGS / "saves" / f"ptt_portal_{uuid4().hex[:12]}.sav"
    try:
        spec, start_y = build_portal_fixture(fixture, number, side)
        with OwnedGame(fixture, number) as game:
            game.tap(0x57, .04)
            game.tap(0x20)
            # Gunfire gives A_Look a sound target, masking its forward-only scan.
            if side == "south":
                game.fire()
            game.tap(0x57, .5)
            before = output / f"{prefix}-keyless.sav"
            game.snapshot(before)
            if beam_records(before) or native_level_state(before)["map"] != number:
                raise AssertionError(f"{spec.name}: keyless USE/fire bypassed gate")
            dust = dust_records(before)
            if (len(dust) != 1 or (dust[0]["x"], dust[0]["y"]) != spec.exit_center
                    or dust[0]["flags"] != 560):
                raise AssertionError(f"{spec.name}: missing or displaced inactive fairy dust")
            player = walker_records(before, 28, 0, (16, 56))
            direction = -1 if side == "north" else 1
            if len(player) != 1 or direction * (player[0]["y"] - start_y) >= 40:
                raise AssertionError(f"{spec.name}: keyless collision gate did not block entry")
            game.capture(output / f"{prefix}-keyless.png")
            shutil.copyfile(before, native_save)
            setups = (LOGS / "stdout.txt").read_text(errors="replace").count(
                "P_SetupLevel: Using limit-removing structures")
            game.command(f"load {native_save.stem}")
            time.sleep(1)
            inactive_loaded = output / f"{prefix}-inactive-loaded.sav"
            game.snapshot(inactive_loaded)
            if (len(dust_records(inactive_loaded)) != 1 or beam_records(inactive_loaded)
                    or (LOGS / "stdout.txt").read_text(errors="replace").count(
                        "P_SetupLevel: Using limit-removing structures") != setups + 1):
                raise AssertionError(f"{spec.name}: inactive dust/gating did not survive logged reload")
            game.tap(0x44, .6)
            game.tap(0x41, .6)
            # Back away from the checkpoint wall so its angled ring faces cannot
            # wedge the player in a corner pocket during lateral alignment.
            game.tap(0x53, .25)
            aligned = output / f"{prefix}-keyed-approach.sav"
            for attempt in range(16):
                # Let friction stop the player so the measured offset is settled.
                time.sleep(.3)
                game.snapshot(aligned)
                players = walker_records(aligned, 28, 0, (16, 56))
                if len(players) != 1:
                    raise AssertionError(f"{spec.name}: ambiguous keyed approach player")
                delta = spec.exit_center[0] - players[0]["x"]
                # The smallest native keypress impulse travels about 26 units after
                # friction, so the acceptance window must exceed that quantum. 15
                # units keeps the player centre well inside the 40-unit octagon.
                if abs(delta) <= 15:
                    break
                if attempt == 8:
                    game.tap(0x53, .2)
                right_increases_x = side == "south"
                key = 0x44 if (delta > 0) == right_increases_x else 0x41
                game.tap(key, min(.15, max(.02, abs(delta) / 320)))
            else:
                raise AssertionError(f"{spec.name}: could not align with beam using normal movement")
            game.tap(0x57, .4)
            game.tap(0x20)
            time.sleep(.2)
            game.capture(output / f"{prefix}-activation.png")
            time.sleep(3)
            after = output / f"{prefix}-active.sav"
            game.snapshot(after)
            actors = beam_records(after)
            if dust_records(after):
                raise AssertionError(f"{spec.name}: inactive dust survived beam activation")
            expected = {(spec.exit_center[0], spec.exit_center[1], index * SEGMENT_HEIGHT)
                        for index in range(SEGMENTS)}
            positions = lambda rows: {(row["x"], row["y"], row["z"]) for row in rows}
            if (len(actors) != SEGMENTS or positions(actors) != expected
                    or any(row["flags"] != 528 or row["health"] != 1 for row in actors)):
                raise AssertionError(f"{spec.name}: missing, displaced or unsafe beam pieces")
            game.capture(output / f"{prefix}-active.png")
            shutil.copyfile(after, native_save)
            setups = (LOGS / "stdout.txt").read_text(errors="replace").count(
                "P_SetupLevel: Using limit-removing structures")
            game.command(f"load {native_save.stem}")
            time.sleep(2)
            loaded = output / f"{prefix}-loaded.sav"
            game.snapshot(loaded)
            if (LOGS / "stdout.txt").read_text(errors="replace").count(
                    "P_SetupLevel: Using limit-removing structures") != setups + 1:
                raise AssertionError(f"{spec.name}: native reload was not logged")
            rows = beam_records(loaded)
            if (dust_records(loaded) or len(rows) != SEGMENTS or positions(rows) != expected
                    or any(row["flags"] != 528 or row["health"] != 1 for row in rows)):
                raise AssertionError(f"{spec.name}: beam did not persist safely after reload")
            game.tap(0x53, 1)
            game.capture(output / f"{prefix}-approach.png")
            intermissions = (LOGS / "stdout.txt").read_text(errors="replace").count("D_inter.ogg")
            game.tap(0x57, 1)
            game.tap(0x57, 2)
            if (LOGS / "stdout.txt").read_text(errors="replace").count(
                    "D_inter.ogg") != intermissions + 1:
                raise AssertionError(f"{spec.name}: walking into the beam did not start intermission")
            game.capture(output / f"{prefix}-exit.png")
            return dict(map=spec.name, approach_side=side, keyless_use_denied=True,
                        keyless_fire_denied=True if side == "south" else None,
                        silent_activation=True if side == "north" else None,
                        keyless_collision_blocked=True, real_key_pickup_activation=True,
                        segments=SEGMENTS, fixed_positions=True,
                        inactive_dust_fixed=True, inactive_reload_logged=True,
                        dust_replaced_on_activation=True,
                        native_reload_logged=True, safe_reload_persistence=True,
                        native_exit_logged=True,
                        exit_capture=f"{prefix}-exit.png",
                        visual_review="Required: inspect approach, activation and exit captures")
    finally:
        fixture.unlink(missing_ok=True)
        native_save.unlink(missing_ok=True)


def verify(numbers, sides=("south",)):
    output = ROOT / "runtime_validation" / "portal-gates"
    output.mkdir(parents=True, exist_ok=True)
    proof = output / "portal-results.json"
    proof.unlink(missing_ok=True)
    digest = hashlib.sha256(CANDIDATE.read_bytes()).hexdigest()
    rows = []
    for number in numbers:
        for side in sides:
            row = verify_map(number, output, side)
            rows.append(row)
            print(json.dumps(row), flush=True)
    if hashlib.sha256(CANDIDATE.read_bytes()).hexdigest() != digest:
        raise RuntimeError("Candidate changed during native portal verification")
    report = dict(wad_sha256=digest, maps=rows,
                  scope="Actual geometry and portal definitions; combat/pickups removed, "
                        "player repositioned and real blue key added beside checkpoint approach; "
                        "normal strafing is measured to align with the beam",
                  full_campaign_traversal=False, visual_review_required=True)
    proof.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--maps", nargs="+", type=int, choices=range(1, 10), default=list(range(1, 10)))
    parser.add_argument("--sides", nargs="+", choices=("south", "north"), default=["south", "north"])
    args = parser.parse_args()
    verify(args.maps, args.sides)
