"""Native presentation captures of the AI-derived mallet's four palette poses."""

import hashlib
import json
import time

from build_expansion import CANDIDATE
from doom_geometry import read_wad, write_wad
from project_paths import ROOT
from verify_campaign_feedback import OwnedGame, build_feedback_fixture


def verify():
    output = ROOT / "runtime_validation"
    output.mkdir(exist_ok=True)
    proof_path = output / "mallet-art-results.json"
    proof_path.unlink(missing_ok=True)
    digest = hashlib.sha256(CANDIDATE.read_bytes()).hexdigest()
    assets = dict(read_wad(CANDIDATE))
    captures = []
    for frame, label in zip("ABCD", ("idle", "windup", "strike", "followthrough")):
        wad = CANDIDATE
        if frame != "A":
            wad = output / f"mallet-art-{label}.wad"
            build_feedback_fixture(wad)
            write_wad(wad, [(name, assets[f"PUNG{frame}0"] if name == "PUNGA0" else data)
                            for name, data in read_wad(wad)])
        try:
            with OwnedGame(wad) as game:
                game.tap(0x31)
                time.sleep(1)
                image = output / f"mallet-art-{label}.png"
                game.capture(image)
                if frame == "A":
                    game.fire()
                    game.snapshot(output / "mallet-art-after-swing.sav")
        finally:
            if wad != CANDIDATE:
                wad.unlink(missing_ok=True)
        captures.append({"pose": label, "capture": image.name, "held_fixture": frame != "A"})
    proof = {
        "wad_sha256": digest,
        "scope": "Actual candidate idle/melee smoke; isolated B/C/D presentation fixtures "
                 "replace only the ready image to hold each pose for visual inspection. "
                 "Full motion timing/realism is not accepted: Pause-key sampling was unreliable, "
                 "graphics recording stalled and desktop recording returned blank frames.",
        "captures": captures,
        "full_motion_accepted": False,
    }
    if hashlib.sha256(CANDIDATE.read_bytes()).hexdigest() != digest:
        raise RuntimeError("Candidate changed during mallet verification")
    proof_path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    verify()
