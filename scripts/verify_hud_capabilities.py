"""Bounded native test of community SBARDEF level-selection conditions."""

import hashlib
import json
import time

from PIL import Image, ImageStat

from build_expansion import CANDIDATE
from build_toronto_wad import _doom_palette, _indexed_canvas, _sprite_patch
from doom_geometry import read_wad, write_wad
from project_paths import ROOT
from verify_campaign_feedback import OwnedGame


def verify():
    output = ROOT / "runtime_validation"
    output.mkdir(exist_ok=True)
    fixture = output / "hud-capability-fixture.wad"
    lumps = read_wad(CANDIDATE)
    definition = json.loads(dict(lumps)["SBARDEF"])
    patches = []
    palette = Image.new("P", (1, 1))
    palette.putpalette(_doom_palette())
    for level in range(1, 10):
        image = Image.new("RGBA", (90, 28), (180, 25, 30) if level == 4 else (20, 180, 160))
        patches.append((f"TRPROB{level}", _sprite_patch(_indexed_canvas(image, palette), (0, 0))))
        element = {"graphic": dict(x=225, y=1, alignment=0, patch=f"TRPROB{level}",
                                  tranmap=None, translation=None, children=None,
                                  conditions=[{"condition": 41, "param": level},
                                              {"condition": 42, "param": level + 1}])}
        definition["data"]["statusbars"][0]["children"].append(element)
    write_wad(fixture, [(name, json.dumps(definition).encode("ascii") if name == "SBARDEF" else data)
                        for name, data in lumps] + patches)
    observations = []
    try:
        for level in (1, 4):
            with OwnedGame(fixture, level) as game:
                time.sleep(1)
                capture = output / f"hud-capability-map{level}.png"
                game.capture(capture)
                with Image.open(capture) as image:
                    # The HUD uses a centered 320-wide virtual canvas.
                    scale = image.height / 200
                    x = (image.width - 320 * scale) / 2 + 270 * scale
                    y = 185 * scale
                    color = ImageStat.Stat(image.convert("RGB").crop(
                        (round(x - 2), round(y - 2), round(x + 2), round(y + 2)))).mean
                observations.append(dict(level=level, color=color, capture=capture.name))
        red_first = observations[0]["color"][0] > observations[0]["color"][1]
        red_fourth = observations[1]["color"][0] > observations[1]["color"][1]
        supported = not red_first and red_fourth
        result = dict(wad_sha256=hashlib.sha256(CANDIDATE.read_bytes()).hexdigest(),
                      tested_conditions=[41, 42], level_selection_supported=supported,
                      observations=observations,
                      heading_interface="No heading value or conditional is defined by ID24 SBARDEF.")
        (output / "hud-capability-results.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
    finally:
        fixture.unlink(missing_ok=True)


if __name__ == "__main__":
    verify()
