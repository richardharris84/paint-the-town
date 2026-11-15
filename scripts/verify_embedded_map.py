"""Probe the documented community minimap widget without changing game content."""

import hashlib
import json

from PIL import Image, ImageChops, ImageStat

from build_expansion import CANDIDATE
from doom_geometry import read_wad, write_wad
from project_paths import ROOT
from verify_campaign_feedback import OwnedGame


def verify():
    output = ROOT / "runtime_validation" / "embedded-map-probe"
    output.mkdir(parents=True, exist_ok=True)
    fixture = output / "minimap-fixture.wad"
    lumps = read_wad(CANDIDATE)
    definition = json.loads(dict(lumps)["SBARDEF"])
    definition["data"]["statusbars"][0]["children"].append({
        "minimap": dict(x=233, y=1, width=86, height=30, alignment=0,
                        conditions=None, children=None, background=2, scale=1.0)
    })
    try:
        with OwnedGame(CANDIDATE, 7) as game:
            game.capture(output / "baseline.png")
        write_wad(fixture, [(name, json.dumps(definition).encode("ascii")
                            if name == "SBARDEF" else data) for name, data in lumps])
        with OwnedGame(fixture, 7) as game:
            game.capture(output / "widget.png")
        with Image.open(output / "baseline.png") as baseline, Image.open(output / "widget.png") as widget:
            scale = baseline.height / 200
            left = (baseline.width - 320 * scale) / 2
            bounds = (round(left + 233 * scale), round(169 * scale),
                      round(left + 319 * scale), round(198 * scale))
            difference = ImageStat.Stat(ImageChops.difference(
                baseline.convert("RGB").crop(bounds), widget.convert("RGB").crop(bounds))).mean
        result = dict(candidate_sha256=hashlib.sha256(CANDIDATE.read_bytes()).hexdigest(),
                      widget="community SBARDEF minimap", mean_difference=difference,
                      rendered=False,
                      observation="Native capture falls back to the stock status bar; "
                                  "changed pixels are not proof of a rendered minimap.",
                      requires_visual_review=True)
        (output / "results.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
    finally:
        fixture.unlink(missing_ok=True)


if __name__ == "__main__":
    verify()
