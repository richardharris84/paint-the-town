"""Owned native KEX checks for results/entering map pictures."""

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from build_expansion import CANDIDATE
from build_mod_previews import patch
from build_toronto_wad import _doom_palette, _indexed_canvas, _sprite_patch
from doom_geometry import read_wad, write_wad
from verify_campaign_feedback import OwnedGame
from verify_expansion_checkpoints import build_fixture
from verify_expansion_runtime import LOGS
from campaign_overworld import NODES


from project_paths import ROOT


def background_match(path, expected):
    with Image.open(path) as source:
        image = source.convert("RGB")
        scores = []
        for width in {image.width, round(image.height * 4 / 3)}:
            left = (image.width - width) // 2
            actual = image.crop((left, 0, left + width, image.height))
            actual = np.asarray(actual.resize((320, 200), Image.Resampling.BOX)).astype(float)
            delta = np.max(abs(actual - np.asarray(expected.convert("RGB")).astype(float)), axis=2)
            # The stock results/title UI is deliberately excluded from this band.
            scores.append(float(np.mean(delta[130:178, :] < 22)))
        return max(scores)


def progress_error(path, expected):
    with Image.open(path) as source:
        image = source.convert("RGB")
        errors = []
        expected = np.asarray(expected.convert("RGB")).astype(float)
        for width in {image.width, round(image.height * 4 / 3)}:
            left = (image.width - width) // 2
            actual = image.crop((left, 0, left + width, image.height))
            actual = np.asarray(actual.resize((320, 200), Image.Resampling.BOX)).astype(float)
            # Compare each progress symbol, not just mostly identical city scenery.
            errors.append(max(float(np.mean(abs(
                actual[y - 5:y + 6, x - 5:x + 6] - expected[y - 5:y + 6, x - 5:x + 6]
            ))) for x, y in NODES))
        return min(errors)


def probe_fixture(path):
    build_fixture(path)
    lumps = read_wad(path)
    palette = Image.new("P", (1, 1))
    palette.putpalette(_doom_palette())
    for name, colour in (("TRPROBEX", (30, 95, 155)), ("TRPROBEI", (50, 145, 75))):
        image = Image.new("RGBA", (320, 200), colour)
        draw = ImageDraw.Draw(image)
        for x in range(0, 320, 20):
            draw.rectangle((x, 130, x + 7, 177), fill=(240, 190, 65))
        lumps.append((name, _sprite_patch(_indexed_canvas(image, palette), (0, 0))))
    for index, (name, data) in enumerate(lumps):
        if name == "UMAPINFO":
            text = data.decode("ascii").replace(
                "    nointermission = false",
                '    nointermission = false\n    exitpic = "TRPROBEX"\n    enterpic = "TRPROBEI"',
            )
            lumps[index] = (name, text.encode("ascii"))
    write_wad(path, lumps)
    return path


def verify(probe=False, stages=(1, 4, 8), output=None):
    output = Path(output) if output is not None else ROOT / "runtime_validation"
    output.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(CANDIDATE.read_bytes()).hexdigest()
    fixture = output / ("overworld-probe.wad" if probe else "overworld-fixture.wad")
    (probe_fixture if probe else build_fixture)(fixture)
    assets = dict(read_wad(fixture))
    checks = []
    try:
        for stage in ((1,) if probe else stages):
            exit_name = "TRPROBEX" if probe else f"TRX{stage:02}"
            enter_name = "TRPROBEI" if probe else "TRZOO" if stage == 8 else f"TRI{stage + 1:02}"
            with OwnedGame(fixture, stage) as game:
                game.prepare_capture()
                game.tap(0x57, 2)
                game.tap(0x20, 0.15)
                game.tap(0x57, 3)
                time.sleep(2)
                prefix = "overworld-probe" if probe else f"overworld-{stage:02}"
                result = output / f"{prefix}-results.png"
                game.capture(result)
                exit_score = background_match(result, patch(exit_name, assets))
                if exit_score < 0.85:
                    raise RuntimeError(f"Results background mismatch/stock overlay: {exit_score:.3f}")
                entering = output / f"{prefix}-entering.png"
                for _ in range(5):
                    game.tap(0x20, 0.12)
                    # Capture after KEX's intermission wipe, before sending another USE.
                    time.sleep(2)
                    game.capture(entering)
                    enter_score = background_match(entering, patch(enter_name, assets))
                    if enter_score >= 0.85:
                        break
                else:
                    raise RuntimeError(f"Entering background mismatch/stock overlay: {enter_score:.3f}")
                if not probe and stage == 8:
                    time.sleep(7)
                    game.capture(entering)
                    enter_score = background_match(entering, patch(enter_name, assets))
                    if enter_score < 0.85:
                        raise RuntimeError("Zoo handoff map did not remain visible during its text")
                node_error = progress_error(entering, patch(enter_name, assets)) if not probe else 0
                if node_error >= 22:
                    raise RuntimeError(f"Campaign progress markers do not match: {node_error:.3f}")
                checks.append({"from": stage, "to": stage + 1,
                               "results_background_match": exit_score,
                               "entering_background_match": enter_score,
                               "progress_marker_error": node_error})
                print(checks[-1], flush=True)
            (output / f"{prefix}-stdout.txt").write_bytes((LOGS / "stdout.txt").read_bytes())
        if hashlib.sha256(CANDIDATE.read_bytes()).hexdigest() != digest:
            raise RuntimeError("Candidate changed during overworld check")
        proof = {"wad_sha256": digest, "stages": checks,
                 "scope": "Native results/entering pictures; actual keyed exits; combat removed"}
        (output / ("overworld-probe-results.json" if probe else "overworld-results.json")).write_text(
            json.dumps(proof, indent=2) + "\n"
        )
    finally:
        (output / "overworld-last-stdout.txt").write_bytes((LOGS / "stdout.txt").read_bytes())
        fixture.unlink(missing_ok=True)


def verify_introductions():
    from toronto_venues import venue_specs

    output = ROOT / "runtime_validation"
    output.mkdir(exist_ok=True)
    sheet = Image.new("RGB", (960, 240))
    for i, spec in enumerate(venue_specs()):
        with OwnedGame(CANDIDATE, i + 1) as game:
            game.prepare_capture()
            game.tap(0x57, 0.08)
            path = output / f"overworld-intro-{i + 1:02}.png"
            game.capture(path)
        with Image.open(path) as image:
            strip = image.convert("RGB").crop((0, 0, image.width, round(image.height * 0.12)))
            strip = strip.resize((320, 80), Image.Resampling.BOX)
            sheet.paste(strip, ((i % 3) * 320, (i // 3) * 80))
        print(f"Captured {spec.name}: {spec.title}", flush=True)
    sheet.save(output / "overworld-introductions.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--stages", nargs="+", type=int, default=[1, 4, 8])
    parser.add_argument("--introductions", action="store_true")
    args = parser.parse_args()
    if any(stage not in range(1, 9) for stage in args.stages):
        parser.error("Stages must be from 1 through 8")
    if args.introductions:
        verify_introductions()
    else:
        verify(args.probe, tuple(args.stages))
