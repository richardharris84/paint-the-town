"""Capture original five-venue scenery in KEX, retaining actual map geometry."""

import hashlib
import json
import shutil
import struct
import time
from uuid import uuid4

from build_expansion import CANDIDATE
from doom_geometry import read_wad, write_wad
from project_paths import ROOT
from venue_scenery import BY_ID
from level_inset import MARKER_DOOMEDNUM
from portal_gates import EMITTER_ID, PANEL_ID
from verify_campaign_feedback import OwnedGame
from verify_expansion_runtime import LOGS


VIEWS = (
    (1, "rom-gallery", -1800, -450, 90),
    (1, "rom-fossils", 1800, 1000, 90),
    (2, "park-legislature", 0, -3550, 90),
    (2, "park-woodland", 0, 800, 90),
    (3, "sankofa-stage", -250, -360, 90),
    (3, "sankofa-billboards", 850, -330, 180),
    (4, "nathan-rink", -400, -1600, 90),
    (4, "nathan-city-hall", 0, 700, 90),
    (5, "union-hotel-north", 0, 1570, 90),
    (5, "union-platforms-south", 3000, -900, 225),
)


def build_fixture(path, map_number, x, y, angle):
    source = read_wad(CANDIDATE)
    current = None
    result = []
    for name, data in source:
        if name.startswith("E1M") and len(name) == 4:
            current = int(name[-1])
        if name == "THINGS" and current == map_number:
            props = [thing for thing in struct.iter_unpack("<5h", data)
                     if thing[3] in BY_ID or thing[3] in (EMITTER_ID, PANEL_ID)]
            markers = [(x, y, *thing[2:]) for thing in struct.iter_unpack("<5h", data)
                       if MARKER_DOOMEDNUM <= thing[3] < MARKER_DOOMEDNUM + 4]
            data = b"".join(struct.pack("<5h", *thing)
                            for thing in [(x, y, angle, 1, 7), *props, *markers])
        result.append((name, data))
    write_wad(path, result)


def verify():
    output = ROOT / "runtime_validation"
    output.mkdir(exist_ok=True)
    captures = []
    restored_difference = None
    for number, label, x, y, angle in VIEWS:
        fixture = output / f"scenery-{label}.wad"
        build_fixture(fixture, number, x, y, angle)
        try:
            with OwnedGame(fixture, number) as game:
                game.tap(0x57, .04)
                time.sleep(1)
                capture = output / f"scenery-{label}.png"
                game.capture(capture)
                if label == "rom-gallery":
                    save = output / "scenery-roundtrip.sav"
                    game.snapshot(save)
                    native_save = LOGS / "saves" / f"trscenery_{uuid4().hex[:12]}.sav"
                    try:
                        shutil.copy2(save, native_save)
                        before = (LOGS / "stdout.txt").read_text(errors="replace").count(
                            "P_SetupLevel: Using limit-removing structures")
                        game.tap(0x53, 0.4)
                        game.command(f"load {native_save.stem}")
                        time.sleep(2)
                        game.capture(output / "scenery-after-load.png")
                        log = (LOGS / "stdout.txt").read_text(errors="replace")
                        (output / "scenery-save-load.log").write_text(log)
                        if log.count("P_SetupLevel: Using limit-removing structures") != before + 1:
                            raise RuntimeError("Native scenery load was not confirmed in KEX log")
                        from PIL import Image, ImageChops, ImageStat
                        with Image.open(capture) as first, Image.open(output / "scenery-after-load.png") as loaded:
                            area = (0, 0, first.width, first.height // 2)
                            difference = ImageStat.Stat(ImageChops.difference(
                                first.convert("RGB").crop(area), loaded.convert("RGB").crop(area)))
                            restored_difference = max(difference.mean)
                            if restored_difference > 1:
                                raise RuntimeError("Save/load did not restore the scenery viewpoint")
                    finally:
                        native_save.unlink(missing_ok=True)
                captures.append(dict(map=f"E1M{number}", view=label,
                                     position=[x, y], angle=angle, capture=capture.name))
        finally:
            fixture.unlink(missing_ok=True)
    proof = dict(wad_sha256=hashlib.sha256(CANDIDATE.read_bytes()).hexdigest(),
                 scope="Actual geometry/materials/decorations; combat and pickups removed "
                       "only in screenshot fixtures. Compass bearings use +Y north.",
                 save_load=dict(map="E1M1", native_reload_confirmed=True,
                                restored_view_mean_pixel_error=restored_difference),
                 captures=captures)
    (output / "scenery-results.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    verify()
