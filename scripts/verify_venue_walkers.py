"""Verify integrated arena and wandering-girl walkers through native KEX saves."""

import hashlib
import json
import math
import shutil
import struct
import time
import zlib
from pathlib import Path
from uuid import uuid4

from build_expansion import CANDIDATE
from project_paths import ROOT
from verify_campaign_feedback import LOGS, OwnedGame
from venue_walkers import BEAR_OUTBOUND, GIRL_OUTBOUND


MAPS = (
    dict(title="Scotiabank Arena", number=6, sprite=281, record_type=355, expected_count=1,
         controllers=((350, -700),), radius=BEAR_OUTBOUND + 64),
    dict(title="Queen's Park", number=2, sprite=285, record_type=376, expected_count=1,
         controllers=((0, 300),), radius=GIRL_OUTBOUND + 64, dimensions=(12, 48)),
    dict(title="Sankofa Square", number=3, sprite=286, record_type=379, expected_count=1,
         controllers=((-1300, -1100),), radius=GIRL_OUTBOUND + 64, dimensions=(12, 48)),
)


def native_level_state(path):
    data = Path(path).read_bytes()
    body = zlib.decompress(data[data.index(0) + 9:])
    if len(body) < 201 or body[64:80].rstrip(b"\0") != b"version 260":
        raise ValueError("Unrecognized KEX native save header")
    cursor = 87
    expected_options = (
        b"d_pistolStart", b"d_soloNet", b"d_fastMonsters",
        b"d_noMonsters", b"d_respawnMonsters", b"d_modernCooperative",
    )
    for expected in expected_options:
        end = body.index(0, cursor)
        if body[cursor:end] != expected:
            raise ValueError("Unrecognized KEX simulation options in native save")
        cursor = end + 1
        end = body.index(0, cursor)
        if body[cursor:end] not in (b"0", b"1"):
            raise ValueError("Invalid KEX simulation option in native save")
        cursor = end + 1
    if body[cursor] != 0:
        raise ValueError("Unexpected KEX native save option terminator")
    # This KEX format places eight bytes before the legacy three-byte level clock.
    clock = cursor + 9
    if clock + 3 > len(body):
        raise ValueError("Truncated KEX native level clock")
    return dict(episode=body[81], map=body[82],
                level_tics=int.from_bytes(body[clock:clock + 3], "big"))


def walker_records(path, sprite, record_type, dimensions=None):
    data = Path(path).read_bytes()
    body = zlib.decompress(data[data.index(0) + 9:])
    records = []
    for offset in range(120, len(body) - 40):
        if body[offset:offset + 4] != struct.pack("<i", record_type):
            continue
        integer = lambda relative: struct.unpack_from("<i", body, offset + relative)[0]
        if integer(-84) != sprite:
            continue
        width, height = integer(-24) / 65536, integer(-20) / 65536
        expected = dimensions if dimensions is not None else (28, 72)
        if (width, height) != expected:
            continue
        records.append(dict(
            x=integer(-120) / 65536, y=integer(-116) / 65536,
            z=integer(-112) / 65536, state=integer(24),
            flags=integer(32), health=integer(36),
            momx=integer(-16) / 65536, momy=integer(-12) / 65536,
            angle_degrees=struct.unpack_from("<I", body, offset - 88)[0] * 360 / 2**32,
            sprite_frame=integer(-80),
        ))
    return records


def _distance(a, b):
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"])


def matched_walkers(actors, config):
    """Associate each native actor with its unique, bounded world-space route."""
    anchors = config["controllers"]
    if len(actors) != config["expected_count"] or len(actors) != len(anchors):
        raise AssertionError(f"{config['title']}: expected {len(anchors)} walkers, got {len(actors)}")
    matched = {}
    for actor in actors:
        distances = [math.hypot(actor["x"] - x, actor["y"] - y) for x, y in anchors]
        index = min(range(len(anchors)), key=distances.__getitem__)
        if distances[index] > config["radius"] or index in matched:
            raise AssertionError(f"{config['title']}: walker outside or duplicating a fixed route")
        matched[index] = actor
    return [matched[index] for index in range(len(anchors))]


def motion_checks(first, second, config, minimum_travel=32, intermediate=()):
    snapshots = [matched_walkers(actors, config) for actors in (first, *intermediate, second)]
    routes = list(zip(*snapshots))
    actors = [actor for snapshot in snapshots for actor in snapshot]
    return dict(
        expected_actor_count=True,
        grounded=all(abs(actor["z"]) < 1 / 65536 for actor in actors),
        solid_invulnerable_noncounting=all(
            actor["flags"] == 2 and actor["health"] == 1 for actor in actors),
        travel_observed=all(max(_distance(a, b) for a in route for b in route) >= minimum_travel
                            for route in routes),
        gait_state_advances=all(len({actor["state"] for actor in route}) > 1 for route in routes),
    )


def _snapshot(game, path):
    for attempt in range(3):
        try:
            return game.snapshot(path)
        except RuntimeError as error:
            if "Owned native save was not completed" not in str(error) or attempt == 2:
                raise
            time.sleep(1)


def verify_map(config, output):
    native_save = LOGS / "saves" / f"ptt_walk_{uuid4().hex[:12]}.sav"
    first_path = output / f"{config['number']}-walk-first.sav"
    middle_path = output / f"{config['number']}-walk-middle.sav"
    second_path = output / f"{config['number']}-walk-second.sav"
    loaded_path = output / f"{config['number']}-walk-after-load.sav"
    try:
        with OwnedGame(CANDIDATE, config["number"]) as game:
            time.sleep(4)
            ammo_before = _snapshot(game, first_path)
            first = walker_records(first_path, config["sprite"], config["record_type"], config.get("dimensions"))
            game.tap(0x27, .3)
            game.tap(0x44, .2)
            time.sleep(4)
            _snapshot(game, middle_path)
            middle = walker_records(middle_path, config["sprite"], config["record_type"], config.get("dimensions"))
            time.sleep(4)
            ammo_second = _snapshot(game, second_path)
            second = walker_records(second_path, config["sprite"], config["record_type"], config.get("dimensions"))

            checks = motion_checks(first, second, config, intermediate=(middle,))
            checks["player_turn_and_strafe_routes_independent"] = checks["travel_observed"]
            if not all(checks.values()):
                raise AssertionError(
                    f"{config['title']}: walker checks failed: "
                    f"{[name for name, value in checks.items() if not value]}"
                )

            shutil.copyfile(second_path, native_save)
            setups_before = (LOGS / "stdout.txt").read_text(errors="replace").count(
                "P_SetupLevel: Using limit-removing structures")
            game.command(f"load {native_save.stem}")
            time.sleep(4)
            ammo_loaded = _snapshot(game, loaded_path)
            after_load = walker_records(
                loaded_path, config["sprite"], config["record_type"], config.get("dimensions"))
            reload_checks = motion_checks(second, after_load, config, minimum_travel=1)
            checks["save_load_actor_preserved"] = reload_checks["expected_actor_count"]
            checks["native_reload_logged"] = (LOGS / "stdout.txt").read_text(
                errors="replace").count("P_SetupLevel: Using limit-removing structures") == setups_before + 1
            checks["save_load_motion_continues"] = reload_checks["travel_observed"]
            checks["save_load_solid_and_grounded"] = (
                reload_checks["grounded"] and reload_checks["solid_invulnerable_noncounting"])
            checks["save_load_ammo_unchanged"] = ammo_second == ammo_loaded
            if not all(checks.values()):
                raise AssertionError(
                    f"{config['title']}: save/load checks failed: "
                    f"{[name for name, value in checks.items() if not value]}"
                )
            return dict(
                title=config["title"], map=f"E1M{config['number']}",
                first=first, middle=middle, second=second, after_load=after_load, checks=checks,
                ammo_unchanged_before_load=ammo_before == ammo_second,
            )
    finally:
        native_save.unlink(missing_ok=True)


def verify():
    output = ROOT / "runtime_validation" / "candidate-walker-inmap"
    output.mkdir(parents=True, exist_ok=True)
    proof_path = output / "walker-results.json"
    proof_path.unlink(missing_ok=True)
    digest = hashlib.sha256(CANDIDATE.read_bytes()).hexdigest()
    results = [verify_map(config, output) for config in MAPS]
    proof = dict(
        wad_sha256=digest,
        scope="Integrated KEX campaign maps; save-state actor coordinates and inventory",
        maps=results,
        checks=dict(
            arena_polar_bear=all(row["title"] != "Scotiabank Arena"
                                 or row["checks"]["travel_observed"] for row in results),
            wandering_girls=all(row["title"] not in ("Queen's Park", "Sankofa Square")
                                or row["checks"]["travel_observed"] for row in results),
            all_walkers_solid_and_grounded=all(
                row["checks"]["solid_invulnerable_noncounting"]
                and row["checks"]["grounded"] for row in results),
            all_walkers_persist_after_save_load=all(
                row["checks"]["save_load_actor_preserved"]
                and row["checks"]["native_reload_logged"]
                and row["checks"]["save_load_motion_continues"]
                and row["checks"]["save_load_solid_and_grounded"]
                and row["checks"]["save_load_ammo_unchanged"] for row in results),
        ),
    )
    if not all(proof["checks"].values()):
        raise AssertionError("Integrated venue walker acceptance failed")
    proof_path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    verify()
