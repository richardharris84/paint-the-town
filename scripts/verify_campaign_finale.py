"""Verify the actual final keyed exit through victory art, not just map entry."""

import hashlib
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image

from build_expansion import CANDIDATE
from build_mod_previews import patch
from doom_geometry import read_wad
from verify_campaign_feedback import OwnedGame
from verify_expansion_checkpoints import build_fixture
from verify_expansion_runtime import LOGS


def victory_error(path, assets):
    # TRVICTRY is widescreen (560x200). KEX stretches the full art across the
    # screen; other engines centre it and crop to a 4:3/16:9 logical window.
    # Accept whichever display hypothesis matches best.
    expected = patch("TRVICTRY", assets).convert("RGB")
    core = expected.crop(((expected.width - 320) // 2, 0,
                          (expected.width + 320) // 2, expected.height))
    with Image.open(path) as image:
        image = image.convert("RGB")
        window = round(image.height * 4 / 3)
        left = (image.width - window) // 2
        hypotheses = (
            (expected, image),
            (core, image.crop((left, 0, left + window, image.height))),
        )
        errors = []
        for target, actual in hypotheses:
            actual = actual.resize(target.size, Image.Resampling.BOX)
            errors.append(float(np.mean(abs(np.asarray(actual).astype(float)
                                            - np.asarray(target).astype(float)))))
    return min(errors)


def verify(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    proof_path = output / "finale-results.json"
    proof_path.unlink(missing_ok=True)
    digest = hashlib.sha256(CANDIDATE.read_bytes()).hexdigest()
    assets = dict(read_wad(CANDIDATE))
    fixture = build_fixture(output / "finale-fixture.wad")
    passed = False
    try:
        with OwnedGame(fixture, 9) as game:
            time.sleep(3)
            game.prepare_capture()
            game.tap(0x57, 2)
            game.tap(0x20, 0.15)
            game.tap(0x57, 3)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                text = (LOGS / "stdout.txt").read_text(errors="replace")
                if "D_inter.ogg" in text:
                    break
                game.require_foreground()
                time.sleep(1)
            else:
                raise RuntimeError("The actual keyed exit did not reach completion statistics")
            game.capture(output / "finale-statistics.png")
            screenshot = output / "finale-stage.png"
            # Widescreen stretch + engine gamma put the true victory screen
            # near error 16; every other screen measures 60+.
            for attempt in range(35):
                game.capture(screenshot)
                error = victory_error(screenshot, assets)
                if error < 30:
                    screenshot.replace(output / "finale-victory.png")
                    break
                if attempt < 5:
                    (output / f"finale-stage-{attempt}.png").write_bytes(screenshot.read_bytes())
                game.tap(0x20, 0.15)
                time.sleep(1)
            else:
                raise RuntimeError(f"Explicit victory art was not displayed; last pixel error {error:.2f}")
            time.sleep(15)
            game.require_foreground()
            game.capture(output / "finale-victory-stable.png")
            if victory_error(output / "finale-victory-stable.png", assets) >= 30:
                raise RuntimeError("Victory screen did not remain displayed")
            text = (LOGS / "stdout.txt").read_text(errors="replace")
            if "Exception caught" in text or "E1M1:" in text or "E1M5:" in text:
                raise RuntimeError("Finale crashed or unexpectedly loaded another map")
            passed = True
    finally:
        fixture.unlink(missing_ok=True)
        (output / "finale-stdout.txt").write_bytes((LOGS / "stdout.txt").read_bytes())
    if passed:
        proof = {
            "wad_sha256": digest, "actual_keyed_exit": True,
            "victory_screen_matches": True, "stable_after_victory": True,
            "scope": "Actual E1M9 geometry/key/exit; relocated start, combat removed; "
                     "statistics-to-finale transition, pixel-matched victory art and 15-second hold",
        }
        if hashlib.sha256(CANDIDATE.read_bytes()).hexdigest() != digest:
            raise RuntimeError("Candidate changed during finale test")
        proof_path.write_text(json.dumps(proof, indent=2) + "\n")
        print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    from project_paths import ROOT
    verify(ROOT / "runtime_validation")
