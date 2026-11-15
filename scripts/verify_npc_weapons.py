"""Native KEX encounter smoke captures; exact attack graphs are unit-tested."""

import hashlib
import json
import time

from build_expansion import CANDIDATE
from doom_geometry import Geometry, Sector, build_nodes, read_wad, write_wad
from project_paths import ROOT
from verify_campaign_feedback import OwnedGame
from verify_expansion_runtime import LOGS


def verify():
    output = ROOT / "runtime_validation"
    output.mkdir(exist_ok=True)
    source = read_wad(CANDIDATE)
    examples = [(3004, "raccoon-pump"), (15004, "pigeon-starter"),
                (15002, "dinosaur-automatic")]
    results = []
    for kind, label in examples:
        geometry = Geometry("E1M1")
        room = geometry.sector(Sector(0, 256, "RFMARBL", "F_SKY1"))
        geometry.loop([(-256, -256), (-256, 512), (256, 512), (256, -256)], room, "RWSANDS")
        geometry.thing(0, 0, 1, angle=90)
        geometry.thing(0, 300, kind, angle=270)
        patch = b"\nMisc 0\nInitial Health = 1000\n\n"
        fixture = output / f"npc-{label}.wad"
        lumps = build_nodes(geometry.lumps()) + source[11:]
        write_wad(fixture, [(name, data + patch if name == "DEHACKED" else data) for name, data in lumps])
        with OwnedGame(fixture) as game:
            time.sleep(2)
            game.capture(output / f"npc-{label}.png")
            game.snapshot(output / f"npc-{label}.sav")
            text = (LOGS / "stdout.txt").read_text(errors="replace").lower()
            if any(error in text for error in ("unknown code pointer", "invalid state", "unknown action",
                                               "audiosourcexa2.cpp", "fatal error")):
                raise RuntimeError(f"{label}: native attack definition was rejected")
        results.append({"type": kind, "label": label, "native_encounter": "captured"})
    proof = dict(wad_sha256=hashlib.sha256(CANDIDATE.read_bytes()).hexdigest(),
                 scope="Native live encounters and saves; pellet count and burst graph verified by unit tests",
                 examples=results)
    (output / "npc-weapons-results.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    verify()
