"""Isolated native probes; never publish or patch the installed engine."""

import argparse
import json
import hashlib
import shutil
import struct
import time
from uuid import uuid4
import zlib

from build_expansion import CANDIDATE
from doom_geometry import read_wad, write_wad
from project_paths import ROOT
from verify_campaign_feedback import LOGS, OwnedGame


def walker_fixture(path, debug_bootstrap=False, face_diagnostic=False, relay_diagnostic=False):
    source = read_wad(CANDIDATE)
    patch = [
        "Thing 352", "ID # = -1", "Initial frame = 7020",
        "Hit points = 1", "Width = 1048576", "Height = 4194304",
        "Bits = 65538", "Speed = 65536", "Missile damage = 0", "",
        "Thing 351", "ID # = 15400", "Initial frame = 7000",
        "First moving frame = 7002",
        "Hit points = 1", "Width = 0", "Height = 0", "Bits = 532", "",
        "Frame 7000", "Sprite number = 231", "Sprite subnumber = 0",
        "Duration = 1", "Next frame = 7001", "",
        "Frame 7001", "Sprite number = 231", "Sprite subnumber = 0",
        "Duration = 10", "Next frame = 7001", "",
        "Frame 7002", "Sprite number = 231", "Sprite subnumber = 0",
        "Duration = -1", "Next frame = 7002", "Args1 = 353",
        "Args5 = -2031616", "",
        "Thing 353", "ID # = -1", "Initial frame = 7010",
        "Hit points = 1", "Width = 0", "Height = 0",
        "Bits = 66068", "Speed = 65536", "Missile damage = 0", "",
        "Frame 7010", "Sprite number = 231", "Sprite subnumber = 0",
        "Duration = 1", "Next frame = 7011", "",
        "Frame 7011", "Sprite number = 231", "Sprite subnumber = 0",
        "Duration = 0", "Next frame = 7012", "",
        "Frame 7012", "Sprite number = 231", "Sprite subnumber = 0",
        "Duration = 0", "Next frame = 7013", "Args1 = 65536", "",
        "Frame 7013", "Sprite number = 231", "Sprite subnumber = 0",
        "Duration = -1", "Next frame = 7013", "Args1 = 352",
        "Args5 = -1572864", "",
        "Frame 7020", "Sprite number = 249", "Sprite subnumber = 0",
        "Duration = 1", "Next frame = 7021", "",
        "Frame 7021", "Sprite number = 249", "Sprite subnumber = 0",
        "Duration = 0", "Next frame = 7100", "Args1 = 65536", "",
        "[CODEPTR]", "FRAME 7000 = NULL", "FRAME 7001 = Look",
        "FRAME 7002 = MonsterProjectile",
        "FRAME 7010 = NULL", "FRAME 7011 = Stop",
        "FRAME 7012 = RemoveFlags", "FRAME 7013 = MonsterProjectile",
        "FRAME 7020 = NULL", "FRAME 7021 = RemoveFlags", "",
    ]
    def frame(state, action, duration, next_state, args=(), pose=0):
        patch.extend((f"Frame {state}", "Sprite number = 249",
                      f"Sprite subnumber = {pose}", f"Duration = {duration}",
                      f"Next frame = {next_state}"))
        patch.extend(f"Args{index} = {value}" for index, value in enumerate(args, 1))
        patch.extend(("", "[CODEPTR]", f"FRAME {state} = {action}", ""))
    for index in range(32):
        state = 7100 + index * 2
        pose = index // 8
        frame(state, "JumpIfTargetCloser", 0, 7500,
              (state + 1, 245 * 65536), pose)
        frame(state + 1, "SeekTracer", 1,
              7100 + ((index + 1) % 32) * 2, (1, 1), pose)
    frame(7500, "Stop", 8, 7501)
    frame(7501, "FaceTarget", 0, 7502)
    frame(7502, "JumpIfTargetCloser", 0, 7503, (7100, 225 * 65536))
    frame(7503, "SeekTracer", 1, 7502, (1, 1))
    current = None
    result = []
    patch_text = "\n".join(patch)
    if debug_bootstrap or face_diagnostic:
        for index, distance in enumerate((100, 1000, 100 * 65536, 1000 * 65536)):
            base = 7600 + index * 10
            patch.extend((
                f"Thing {351 + index}", f"ID # = {15400 + index}",
                f"Initial frame = {base}", f"First moving frame = {base + 2}",
                "Hit points = 1", "Width = 0", "Height = 0", "Bits = 532", "",
            ))
            frame(base, "NULL", 1, base + 1)
            frame(base + 1, "Look", 10, base + 1)
            if face_diagnostic:
                argument = (0, 90, 90 * 65536, 0x40000000)[index]
                frame(base + 2, "Face", -1, base + 2, (argument,))
            else:
                frame(base + 2, "JumpIfTargetCloser", 0, base + 3,
                      (base + 4, distance))
                frame(base + 3, "Stop", -1, base + 3)
                frame(base + 4, "Stop", -1, base + 4)
        patch_text = "\n".join(patch)
        for index in range(4):
            base = 7600 + index * 10
            if face_diagnostic:
                patch_text += (f"\nFrame {base + 2}\nSprite number = 260\n"
                               f"Unknown 1 = {90 if index == 0 else 0}\n")
            else:
                patch_text += (f"\nFrame {base + 3}\nSprite number = 241\n"
                               f"\nFrame {base + 4}\nSprite number = 240\n")
    if debug_bootstrap:
        patch_text += (
            "\nFrame 7012\nSprite number = 231\nSprite subnumber = 0\n"
            "Duration = 0\nNext frame = 7013\nArgs1 = 7040\n"
            f"Args2 = {1000 * 65536}\n"
            "\nFrame 7040\nSprite number = 240\nSprite subnumber = 0\n"
            "Duration = -1\nNext frame = 7040\n"
            "\n[CODEPTR]\nFRAME 7012 = JumpIfTargetCloser\n"
        )
    if relay_diagnostic:
        patch_text += (
            "\nThing 353\nID # = -1\nInitial frame = 7010\n"
            "Hit points = 1\nWidth = 1048576\nHeight = 4194304\n"
            "Bits = 66068\nSpeed = 65536\n"
            "\nFrame 7012\nSprite number = 231\nSprite subnumber = 0\n"
            "Duration = 0\nNext frame = 7013\nArgs1 = 7040\n"
            f"Args2 = {1000 * 65536}\n"
            "\nFrame 7013\nSprite number = 241\nSprite subnumber = 0\n"
            "Duration = -1\nNext frame = 7013\n"
            "\nFrame 7040\nSprite number = 240\nSprite subnumber = 0\n"
            "Duration = -1\nNext frame = 7040\n"
            "\n[CODEPTR]\nFRAME 7012 = JumpIfTargetCloser\n"
            "FRAME 7013 = NULL\n"
        )
    for name, data in source:
        if name.startswith("E1M") and len(name) == 4:
            current = int(name[-1])
        if name == "THINGS" and current == 6:
            start = (-250, -450, 90)
            data = (struct.pack("<5h", *start, 1, 7)
                    + struct.pack("<5h", -250, 0, 270, 15400, 7))
            if debug_bootstrap or face_diagnostic:
                data = struct.pack("<5h", *start, 1, 7) + b"".join(
                    struct.pack("<5h", -400 + index * 100, 0, 270, 15400 + index, 7)
                    for index in range(4))
        if name == "DEHACKED":
            data += ("\n\n" + patch_text).encode("ascii")
        result.append((name, data))
    write_wad(path, result)


def read_probe_actor(path):
    """Read only the uniquely validated probe record in this KEX save layout."""
    data = path.read_bytes()
    start = data.index(0) + 1
    body = zlib.decompress(data[start + 8:])
    matches = []
    live_states = {7101 + index * 2 for index in range(32)} | {7500, 7503}
    for offset in range(120, len(body) - 40):
        if body[offset:offset + 4] != struct.pack("<i", 351):
            continue
        integer = lambda relative: struct.unpack_from("<i", body, offset + relative)[0]
        if (integer(-24), integer(-20), integer(-84)) != (16 * 65536, 64 * 65536, 249):
            continue
        if integer(24) not in live_states or integer(32) != 2 or integer(36) != 1:
            continue
        matches.append(dict(x=integer(-120) / 65536, y=integer(-116) / 65536,
                            z=integer(-112) / 65536, state=integer(24),
                            flags=integer(32), health=integer(36),
                            momx=integer(-16) / 65536, momy=integer(-12) / 65536))
    if len(matches) != 1:
        raise ValueError(f"Expected one recognized solid probe actor; found {len(matches)}")
    return matches[0]


def patrol_checks(positions):
    blocked = positions["obstructed"]
    blocked_later = positions["obstructed-later"]
    distance = lambda a, b: ((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2) ** .5
    checks = dict(
        grounded=all(abs(p["z"]) <= 1 / 65536 for p in positions.values()),
        solid_invulnerable_noncounting=all(p["flags"] == 2 and p["health"] == 1
                                          for p in positions.values()),
        bounded=all(abs(p["x"] + 250) < 1 and abs(p["y"]) <= 250
                    for p in positions.values()),
        travel_and_turns_observed=max(p["y"] for p in positions.values())
                                 - min(p["y"] for p in positions.values()) >= 256
                                 and min(p["momy"] for p in positions.values()) < -.9
                                 and max(p["momy"] for p in positions.values()) > .9,
        blocked_without_reset=distance(blocked, blocked_later) <= .01,
        resumed_after_obstruction=max(distance(blocked, positions[key])
                                      for key in ("resumed", "resumed-later")) >= 128,
        moving_after_load=distance(positions["after-load"],
                                   positions["after-load-final"]) >= 32,
    )
    if not all(checks.values()):
        raise AssertionError(f"Native patrol checks failed: {[k for k, v in checks.items() if not v]}")
    return checks


def verify_walker(debug_bootstrap=False, seconds=None, face_diagnostic=False,
                  relay_diagnostic=False):
    diagnostic = debug_bootstrap or face_diagnostic or relay_diagnostic
    full_patrol = not diagnostic and seconds is None
    label = ("paint-town-face-encoding-diagnostic" if face_diagnostic else
             "paint-town-relay-diagnostic" if relay_diagnostic else
             "paint-town-distance-units-diagnostic" if debug_bootstrap else
             "paint-town-radial-patrol-probe")
    output = ROOT / "runtime_validation" / label
    output.mkdir(parents=True, exist_ok=True)
    fixture = output / "walker-probe.wad"
    walker_fixture(fixture, debug_bootstrap, face_diagnostic, relay_diagnostic)
    native_save = LOGS / "saves" / f"ptt_walker_{uuid4().hex[:12]}.sav"
    saved_ammo = None
    positions = {}
    try:
        with OwnedGame(fixture, 6) as game:
            game.prepare_capture()
            captures = []
            started = time.monotonic()
            phases = (("bootstrap", 5),) if diagnostic else (
                (("clear", seconds),) if seconds is not None else
                (("clear", 20), ("obstructed", 18), ("resumed", 20),
                 ("after-load", 20)))
            for phase, phase_seconds in phases:
                if phase == "obstructed":
                    game.tap(0x57, 1.8)
                elif phase == "resumed":
                    game.tap(0x41, .5)
                elif phase == "after-load":
                    saved_ammo = game.snapshot(output / "walker-before-load.sav")
                    shutil.copyfile(output / "walker-before-load.sav", native_save)
                    game.command(f"load {native_save.stem}")
                    time.sleep(.5)
                phase_start = time.monotonic()
                while time.monotonic() - phase_start < phase_seconds:
                    path = output / f"{phase}-{len(captures):03}.png"
                    game.capture(path)
                    captures.append(dict(capture=path.name, phase=phase,
                                         seconds=time.monotonic() - started))
                if not diagnostic:
                    saved = output / f"walker-phase-{phase}.sav"
                    game.snapshot(saved)
                    positions[phase] = read_probe_actor(saved)
                    if phase in ("obstructed", "resumed"):
                        time.sleep(2)
                        saved = output / f"walker-phase-{phase}-later.sav"
                        game.snapshot(saved)
                        positions[f"{phase}-later"] = read_probe_actor(saved)
            if saved_ammo is not None:
                if game.snapshot(output / "walker-after-load.sav") != saved_ammo:
                    raise AssertionError("Walker save/load changed player ammunition")
                positions["before-load"] = read_probe_actor(output / "walker-before-load.sav")
                positions["after-load-final"] = read_probe_actor(output / "walker-after-load.sav")
            checks = patrol_checks(positions) if full_patrol else {}
            (output / "walker-observations.json").write_text(json.dumps(dict(
                wad_sha256=hashlib.sha256(CANDIDATE.read_bytes()).hexdigest(),
                fixture_sha256=hashlib.sha256(fixture.read_bytes()).hexdigest(),
                purpose="Isolated native argument diagnostic" if diagnostic else
                        "Grounded solid shuttle with two fixed references",
                acceptance="Native prototype only; not an integrated venue walker",
                checks=checks,
                distance_arguments=(100, 1000, 100 * 65536, 1000 * 65536)
                if debug_bootstrap else None,
                save_load_ammo_unchanged=saved_ammo is not None,
                positions=positions,
                captures=captures), indent=2) + "\n")
    finally:
        native_save.unlink(missing_ok=True)
        fixture.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--distance-diagnostic", "--debug-bootstrap",
                        dest="debug_bootstrap", action="store_true")
    parser.add_argument("--face-diagnostic", action="store_true")
    parser.add_argument("--relay-diagnostic", action="store_true")
    parser.add_argument("--seconds", type=float)
    args = parser.parse_args()
    if args.seconds is not None and args.seconds <= 0:
        parser.error("--seconds must be positive")
    if sum((args.debug_bootstrap, args.face_diagnostic, args.relay_diagnostic)) > 1:
        parser.error("Choose only one walker diagnostic")
    verify_walker(args.debug_bootstrap, args.seconds, args.face_diagnostic,
                  args.relay_diagnostic)
