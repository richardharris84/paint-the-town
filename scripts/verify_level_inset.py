"""Verify automatic static map selection through all native keyed transitions."""

import hashlib
import json
import shutil
import time
from uuid import uuid4

import numpy as np
from PIL import Image

from build_expansion import CANDIDATE
from build_mod_previews import patch
from doom_geometry import read_wad
from project_paths import ROOT
from verify_campaign_feedback import OwnedGame
from verify_expansion_checkpoints import build_fixture
from verify_expansion_runtime import LOGS


def identify(path, assets):
    with Image.open(path) as source:
        width = round(source.height * 4 / 3)
        left = (source.width - width) / 2
        area = (round(left + 233 * width / 320), round(169 * source.height / 200),
                round(left + 319 * width / 320), round(199 * source.height / 200))
        actual = np.asarray(source.convert("RGB").crop(area).resize(
            (86, 30), Image.Resampling.BOX)).astype(float)
    scores = {n: float(np.mean(abs(actual - np.asarray(
        patch(f"TRMAP{n}", assets).convert("RGB")).astype(float)))) for n in range(1, 10)}
    best = min(scores, key=scores.get)
    if scores[best] >= 6:
        raise RuntimeError(f"No rendered static map template matches: {scores}")
    return best, scores[best]


def verify():
    output = ROOT / "runtime_validation"
    output.mkdir(exist_ok=True)
    digest = hashlib.sha256(CANDIDATE.read_bytes()).hexdigest()
    assets = dict(read_wad(CANDIDATE))
    fixture = build_fixture(output / "static-inset-fixture.wad")
    checks = []
    try:
        with OwnedGame(fixture) as game:
            game.prepare_capture()
            for level in range(1, 10):
                game.tap(0x57, .08)
                time.sleep(1.5)
                capture = game.capture(output / f"static-inset-{level:02}.png")
                selected, error = identify(capture, assets)
                if selected != level:
                    raise RuntimeError(f"E1M{level}: selected wrong map {selected}")
                checks.append(dict(level=level, selected=selected, mean_pixel_error=error))
                print(checks[-1], flush=True)
                if level == 7:
                    saved = output / "static-inset-roundtrip.sav"
                    game.snapshot(saved)
                    native = LOGS / "saves" / f"trinset_{uuid4().hex[:12]}.sav"
                    try:
                        shutil.copy2(saved, native)
                        game.command(f"load {native.stem}")
                        time.sleep(2)
                        loaded = game.capture(output / "static-inset-after-load.png")
                        if identify(loaded, assets)[0] != level:
                            raise RuntimeError("Save/load did not preserve the level inset")
                    finally:
                        native.unlink(missing_ok=True)
                if level == 9:
                    break
                game.tap(0x57, 2)
                game.tap(0x20, .15)
                game.tap(0x57, 3)
                for _ in range(12):
                    time.sleep(1)
                    if f"E1M{level + 1}:" in (LOGS / "stdout.txt").read_text(errors="replace"):
                        break
                    game.tap(0x20, .12)
                    game.tap(0x57, 2)
                else:
                    raise RuntimeError(f"Native keyed transition failed after E1M{level}")
                time.sleep(1)
        if hashlib.sha256(CANDIDATE.read_bytes()).hexdigest() != digest:
            raise RuntimeError("Candidate changed during inset verification")
        proof = dict(wad_sha256=digest, maps=checks, save_load_preserved=True,
                     scope="Actual KEX keyed transitions, starts moved and combat removed; "
                           "all nine rendered templates matched after first movement")
        (output / "static-inset-results.json").write_text(json.dumps(proof, indent=2) + "\n")
        (output / "checkpoint-live-results.json").write_text(json.dumps(dict(
            wad_sha256=digest, maps_reached=[f"E1M{n}" for n in range(1, 10)],
            scope=proof["scope"]), indent=2) + "\n")
    finally:
        fixture.unlink(missing_ok=True)


if __name__ == "__main__":
    verify()
