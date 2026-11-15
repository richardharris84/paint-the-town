"""Candidate-only native HUD, animation and venue evidence; never publishes."""

import hashlib
import json
import re
import shutil
import struct
import time
from uuid import uuid4

from build_expansion import CANDIDATE
from doom_geometry import read_wad, write_wad
from project_paths import ROOT, RELEASE, LEGACY_RELEASE
from verify_campaign_feedback import OwnedGame
from verify_expansion_runtime import LOGS
from verify_venue_scenery import build_fixture


OUTPUT = ROOT / "runtime_validation" / "candidate-revisions"
VIEWS = (
    (1, "rom-gallery", -1800, -450, 90),
    (1, "rom-fossils", 1800, 1000, 90),
    (2, "park-legislature", 0, -3550, 90),
    (2, "park-woodland", 0, 800, 90),
    (3, "sankofa-stage", -250, -360, 90),
    (3, "sankofa-billboards", 850, -330, 180),
    (5, "union-hotel-north", 0, 1570, 90),
    (5, "union-platforms-south", 3000, -900, 225),
    (4, "nathan-single-tower", 0, 700, 90),
    (6, "arena-referee", 0, -350, 90),
    (6, "referee-scale-near", 8, -168, 90),
    (6, "referee-scale-far", 8, -488, 90),
    (6, "hud-stress", 0, -350, 90),
    (7, "rogers-dugouts", 0, -640, 90),
    (7, "baseball-side", 800, 250, 180),
    (8, "islands-start", -3400, 1900, 90),
    (8, "islands-bridge", -2000, 300, 90),
    (8, "islands-waterfront", 0, -1400, 90),
    (9, "zoo-entry", 0, -2000, 90),
    (9, "zoo-indo-malaya", -1120, -1580, 90),
    (9, "zoo-africa", -1120, -280, 90),
    (9, "zoo-giraffe-scale", -1450, -350, 90),
    (9, "zoo-americas", 1180, 1020, 90),
    (9, "zoo-australasia", 1180, -280, 90),
    (9, "zoo-eurasia", 1180, -1580, 90),
    (9, "zoo-canadian-domain", -1120, 1020, 90),
    (9, "zoo-tundra-trek", 30, 570, 90),
)


def verify(views=VIEWS, output=OUTPUT):
    output.mkdir(parents=True, exist_ok=True)
    candidate_hash = hashlib.sha256(CANDIDATE.read_bytes()).hexdigest()
    protected_release = RELEASE if RELEASE.exists() else LEGACY_RELEASE
    published_hash = hashlib.sha256(protected_release.read_bytes()).hexdigest()
    results = []
    for level, label, x, y, angle in views:
        fixture = output / f"{label}-fixture.wad"
        build_fixture(fixture, level, x, y, angle)
        if label == "hud-stress":
            lumps = read_wad(fixture)
            current = None
            updated = []
            for name, data in lumps:
                if name.startswith("E1M") and len(name) == 4:
                    current = int(name[-1])
                if name == "THINGS" and current == level:
                    for kind in (8, 2013, 2013, 2019, 2001, 2002, *([2048] * 12)):
                        data += struct.pack("<5h", x, y, 0, kind, 7)
                updated.append((name, data))
            write_wad(fixture, updated)
        try:
            with OwnedGame(fixture, level) as game:
                game.tap(0x57, .08)
                time.sleep(1)
                capture = output / f"{label}.png"
                game.capture(capture)
                row = dict(map=f"E1M{level}", view=label, position=[x, y],
                           angle=angle, capture=capture.name)
                if label == "baseball-side":
                    # The roster is static art now: verify the native save/load
                    # round trip keeps the scene cosmetic, with no recordings.
                    save = output / "baseball-roundtrip.sav"
                    ammo_before = game.snapshot(save)
                    native_save = LOGS / "saves" / f"trrevision_{uuid4().hex[:12]}.sav"
                    try:
                        shutil.copy2(save, native_save)
                        before = (LOGS / "stdout.txt").read_text(errors="replace").count(
                            "P_SetupLevel: Using limit-removing structures")
                        game.command(f"load {native_save.stem}")
                        time.sleep(2)
                        log = (LOGS / "stdout.txt").read_text(errors="replace")
                        if log.count("P_SetupLevel: Using limit-removing structures") != before + 1:
                            raise RuntimeError("Native scene reload was not logged")
                        game.capture(output / "baseball-after-load.png")
                        ammo_after = game.snapshot(output / "baseball-after-load.sav")
                        if ammo_before != ammo_after:
                            raise RuntimeError("Cosmetic scene changed player ammunition")
                        row.update(native_reload_confirmed=True, unchanged_ammunition=True,
                                   static_roster=True)
                    finally:
                        native_save.unlink(missing_ok=True)
                if label == "arena-referee":
                    time.sleep(.8)
                    game.capture(output / "arena-referee-point.png")
                if label == "hud-stress":
                    ammo = game.snapshot(output / "hud-stress.sav")
                    if ammo[0] != (800, 800):
                        raise RuntimeError(f"HUD stress fixture did not reach 800/800: {ammo[0]}")
                    config = (LOGS / "kexengine.cfg").read_text()
                    settings = {}
                    for variable in ("d_screenSize", "d_renderWidescreen"):
                        values = re.findall(rf'(?m)^seta {variable} "(\d+)"$', config)
                        if len(values) != 1:
                            raise RuntimeError(f"Cannot safely restore {variable}")
                        settings[variable] = values[0]
                    try:
                        for screen, wide in ((11, 1), (12, 1), (10, 0), (11, 0)):
                            game.command(f"d_screenSize {screen}")
                            game.command(f"d_renderWidescreen {wide}")
                            time.sleep(.5)
                            game.capture(output / f"hud-mode-{screen}-wide-{wide}.png")
                    finally:
                        for variable, value in settings.items():
                            game.command(f"{variable} {value}")
                    row.update(ammo=list(ammo[0]), screen_modes=[10, 11, 12],
                               widescreen_modes=[0, 1], settings_restored=True)
                results.append(row)
        finally:
            fixture.unlink(missing_ok=True)
    if hashlib.sha256(CANDIDATE.read_bytes()).hexdigest() != candidate_hash:
        raise RuntimeError("Candidate changed during native scene verification")
    if hashlib.sha256(protected_release.read_bytes()).hexdigest() != published_hash:
        raise RuntimeError("Published WAD changed during candidate verification")
    proof = dict(candidate_sha256=candidate_hash, published_sha256=published_hash,
                 protected_release=protected_release.name,
                 published_unchanged=True, captures=results,
                 publication="Scene evidence only; publication requires separate checksum-bound release proofs.",
                 review="Captures/recordings require visual acceptance; file creation alone is not acceptance.")
    (output / "scene-results.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    verify()
