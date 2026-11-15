"""Source-port compatibility probe: title and in-map evidence per port/IWAD."""

import json
import subprocess
import time
from pathlib import Path

from PIL import ImageGrab

from project_paths import ROOT


PORTS = ROOT / "tools" / "ports"
OUTPUT = ROOT / "runtime_validation" / "standalone-compat"
RELEASE = ROOT / "Paint_the_Town.wad"
DOOM_WAD = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Ultimate Doom\base\DOOM.WAD")
FREEDOOM = PORTS / "freedoom" / "freedoom-0.13.0" / "freedoom1.wad"
WOOF = PORTS / "woof" / "Woof-16.0.0-win64" / "woof.exe"
GZDOOM = PORTS / "gzdoom" / "gzdoom.exe"


def probe(port, iwad, label, warp, seconds=16):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    log = OUTPUT / f"{label}.log"
    arguments = [str(port), "-iwad", str(iwad), "-file", str(RELEASE), "-nosound"]
    if port == GZDOOM:
        arguments += ["+logfile", str(log), "-norun" if False else "+vid_fps", "0"]
        if warp:
            arguments += ["+map", "E1M1", "-skill", "3"]
    else:
        if warp:
            arguments += ["-warp", "1", "1", "-skill", "3"]
    stdout = open(OUTPUT / f"{label}-stdout.txt", "w", encoding="utf-8", errors="replace")
    process = subprocess.Popen(arguments, stdout=stdout, stderr=subprocess.STDOUT,
                               cwd=str(port.parent))
    try:
        time.sleep(seconds)
        alive = process.poll() is None
        ImageGrab.grab().save(OUTPUT / f"{label}.png")
        return dict(label=label, alive_after_seconds=alive, capture=f"{label}.png")
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        stdout.close()


def main():
    results = []
    for port, port_name in ((WOOF, "woof"), (GZDOOM, "gzdoom")):
        for iwad, iwad_name in ((DOOM_WAD, "doom"), (FREEDOOM, "freedoom")):
            for warp, scene in ((False, "title"), (True, "map")):
                label = f"{port_name}-{iwad_name}-{scene}"
                print("probing", label, flush=True)
                results.append(probe(port, iwad, label, warp))
    (OUTPUT / "probe-results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
