"""Checksum-bound KEX Union commuter, transition and extended-play checks."""

import hashlib
import json
import math
import struct
import time

from build_expansion import CANDIDATE, verify_union_stability_evidence
from doom_geometry import read_wad, write_wad
from project_paths import ROOT
from toronto_venues import venue_specs
from venue_scenery import BY_KIND
from verify_campaign_feedback import LOGS, OwnedGame
from verify_venue_walkers import native_level_state, walker_records


OUTPUT = ROOT / "runtime_validation"
COMMUTERS = tuple(
    dict(kind=kind, position=position, item=BY_KIND[kind])
    for kind, position in (("commuter_teal", (-550, -1700)),
                           ("commuter_red", (550, -1700)),
                           ("commuter_gold", (1650, -1700))))


def snapshot(game, path):
    game.snapshot(path)
    state = native_level_state(path)
    if (state["episode"], state["map"]) != (1, 5):
        raise AssertionError(f"Expected native Union save, got {state}")
    actors = []
    for commuter in COMMUTERS:
        item = commuter["item"]
        records = walker_records(path, item.sprite, item.thing - 1,
                                 dimensions=(0, item.height))
        if len(records) != 1:
            raise AssertionError(f"Expected one {commuter['kind']}, got {len(records)}")
        actor = records[0]
        offset = math.hypot(actor["x"] - commuter["position"][0],
                            actor["y"] - commuter["position"][1])
        states = {item.state + index for index in range(len(item.frame_tics))}
        if offset > 1 or actor["z"] != 0 or actor["state"] not in states:
            raise AssertionError(f"{commuter['kind']} displaced or off-cycle: {actor}")
        actors.append(actor)
    return dict(save=path.name, **state, actors=actors)


def commuter_checks(samples):
    routes = list(zip(*(sample["actors"] for sample in samples)))
    return dict(
        commuters_present=all(len(sample["actors"]) == len(COMMUTERS) for sample in samples),
        commuters_static=all(
            math.hypot(a["x"] - b["x"], a["y"] - b["y"]) < 1 and a["momx"] == a["momy"] == 0
            for route in routes for a in route for b in route),
        # Waiting commuters idle-animate in place: the two-frame gait cycles.
        commuter_animation=all(len({actor["state"] for actor in route}) > 1
                               for route in routes),
    )


def extended_play(output, duration=130):
    started = time.monotonic()
    samples = []
    with OwnedGame(CANDIDATE, 5) as game:
        game.prepare_fire()
        while True:
            samples.append(snapshot(game, output / f"union-extended-{len(samples):02}.sav"))
            tics = samples[-1]["level_tics"] - samples[0]["level_tics"]
            if time.monotonic() - started >= duration and tics >= 4200 and len(samples) >= 5:
                break
            if time.monotonic() - started > duration + 120:
                raise AssertionError("Union simulation did not advance 4,200 tics within the watchdog")
            game.tap(0x57, .15)
            game.tap(0x53, .15)
            game.fire()
            time.sleep(7)
        game.capture(output / "union-extended-final.png")
    checks = commuter_checks(samples)
    ticks = [sample["level_tics"] for sample in samples]
    if not all(checks.values()) or any(b <= a for a, b in zip(ticks, ticks[1:])):
        raise AssertionError(f"Union extended progression failed: {checks}")
    return dict(elapsed_seconds=time.monotonic() - started, simulation_tics=ticks,
                samples=samples, checks=checks)


def save_load(output):
    import shutil
    from uuid import uuid4

    native_save = LOGS / "saves" / f"ptt_union_{uuid4().hex[:12]}.sav"
    try:
        with OwnedGame(CANDIDATE, 5) as game:
            time.sleep(4)
            first = snapshot(game, output / "union-saveload-first.sav")
            shutil.copyfile(output / "union-saveload-first.sav", native_save)
            setups = (LOGS / "stdout.txt").read_text(errors="replace").count(
                "P_SetupLevel: Using limit-removing structures")
            game.command(f"load {native_save.stem}")
            time.sleep(5)
            loaded = snapshot(game, output / "union-saveload-after.sav")
            reload_logged = (LOGS / "stdout.txt").read_text(errors="replace").count(
                "P_SetupLevel: Using limit-removing structures") == setups + 1
            if not reload_logged:
                raise AssertionError("Native Union reload was not observed in the engine log")
        return dict(first=first, loaded=loaded, reload_logged=reload_logged,
                    scope="Commuter decorations persist across a native save/load round trip")
    finally:
        native_save.unlink(missing_ok=True)


def reposition_fixture(path, map_number, x, y, angle, key=False):
    current = None
    result = []
    for name, payload in read_wad(CANDIDATE):
        if name.startswith("E1M") and len(name) == 4:
            current = int(name[-1])
        if name == "THINGS" and current == map_number:
            things = [thing for thing in struct.iter_unpack("<5h", payload) if thing[3] != 1]
            things.insert(0, (x, y, angle, 1, 7))
            if key:
                things.append((x, y, 0, 5, 7))
            payload = b"".join(struct.pack("<5h", *thing) for thing in things)
        result.append((name, payload))
    write_wad(path, result)


def incoming_transition(output):
    spec = venue_specs()[3]
    checkpoint = next(region for region in spec.regions if region.title == "Blue-key exit checkpoint")
    x = spec.exit_center[0]
    y = round(checkpoint.polygon.bounds[1]) - 40
    fixture = output / "nathan-union-stability-fixture.wad"
    reposition_fixture(fixture, 4, x, y, 90, key=True)
    try:
        with OwnedGame(fixture, 4) as game:
            game.tap(0x57, .04)
            game.tap(0x20)
            time.sleep(3)
            game.tap(0x57, 3)
            for attempt in range(10):
                text = (LOGS / "stdout.txt").read_text(errors="replace")
                if "E1M5: Union Station" in text and text.count(
                        "P_SetupLevel: Using limit-removing structures") >= 2:
                    break
                game.tap(0x20)
                time.sleep(2)
            else:
                raise AssertionError("Actual Nathan exit did not reach Union")
            first = snapshot(game, output / "union-incoming-first.sav")
            # Sample at irregular intervals (the 88-tic idle cycle is ~2.5s) so
            # animation-state comparisons cannot alias onto one gait phase.
            samples = [first]
            for index, pause in enumerate((1.3, 2.2, 3.4, 1.8)):
                time.sleep(pause)
                samples.append(snapshot(game, output / f"union-incoming-{index + 2:02}.sav"))
            checks = commuter_checks(samples)
            ticks = [sample["level_tics"] for sample in samples]
            if not all(checks.values()) or any(b <= a for a, b in zip(ticks, ticks[1:])):
                raise AssertionError(f"Union commuters failed after Nathan transition: {checks}")
        return dict(samples=samples, checks=checks,
                    scope="Actual Nathan keyed exit/intermission to unmodified Union; "
                          "Nathan start relocated and a key supplied; combat retained")
    finally:
        fixture.unlink(missing_ok=True)


def verify():
    output = OUTPUT / "union-stability"
    output.mkdir(parents=True, exist_ok=True)
    proof_path = OUTPUT / "union-stability-results.json"
    proof_path.unlink(missing_ok=True)
    digest = hashlib.sha256(CANDIDATE.read_bytes()).hexdigest()
    results = {}
    for name, run in (("save_load", save_load),
                      ("nathan_to_union", incoming_transition), ("extended_play", extended_play)):
        results[name] = run(output)
        (output / f"{name}-results.json").write_text(json.dumps(
            dict(wad_sha256=digest, **results[name]), indent=2) + "\n")
        print(f"Native Union {name}: passed", flush=True)
    if hashlib.sha256(CANDIDATE.read_bytes()).hexdigest() != digest:
        raise AssertionError("Candidate changed during native Union acceptance")
    extended = results["extended_play"]["checks"]
    proof = dict(
        wad_sha256=digest,
        scope="Direct candidate extended movement/fire plus actual-geometry Nathan transition fixture",
        elapsed_seconds=results["extended_play"]["elapsed_seconds"],
        simulation_tics=results["extended_play"]["simulation_tics"],
        checks=dict(commuters_present=extended["commuters_present"],
                    commuters_static=extended["commuters_static"],
                    commuter_animation=extended["commuter_animation"],
                    nathan_to_union=all(results["nathan_to_union"]["checks"].values()),
                    save_load=results["save_load"]["reload_logged"],
                    extended_play=True),
        evidence={name: f"union-stability/{name}-results.json" for name in results},
    )
    verify_union_stability_evidence(digest, proof)
    proof_path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    verify()
