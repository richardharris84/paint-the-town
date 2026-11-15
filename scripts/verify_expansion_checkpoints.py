import argparse
import hashlib
import json
import os
import struct
import subprocess
import time
from pathlib import Path

from build_expansion import CANDIDATE
from doom_geometry import read_wad, write_wad
from toronto_venues import venue_specs
from verify_expansion_runtime import EXE, LOGS, focus_owned_window, owns_foreground


def build_fixture(path):
    """Keep actual map geometry, but isolate key doors/exits from combat."""
    specs = {spec.name: spec for spec in venue_specs()}
    lumps = []
    current = None
    for name, payload in read_wad(CANDIDATE):
        if name in specs:
            current = specs[name]
        if name == "THINGS" and current is not None:
            x, y = current.exit_center
            checkpoint = next(r for r in current.regions
                              if r.title == "Blue-key exit checkpoint")
            start_y = round(checkpoint.polygon.bounds[1]) - 40
            if not current.compile().clear_at(x, start_y, 24):
                raise ValueError(f"{current.name}: checkpoint fixture start is obstructed")
            from level_inset import MARKER_DOOMEDNUM
            from portal_gates import EMITTER_ID, PANEL_ID
            markers = [thing for thing in struct.iter_unpack("<5h", payload)
                       if MARKER_DOOMEDNUM <= thing[3] < MARKER_DOOMEDNUM + 4]
            portals = [thing for thing in struct.iter_unpack("<5h", payload)
                       if thing[3] in (EMITTER_ID, PANEL_ID)]
            payload = (struct.pack("<5h", x, start_y, 90, 1, 7)
                       + struct.pack("<5h", x, start_y, 0, 5, 7)
                       + b"".join(struct.pack("<5h", x, start_y, *t[2:]) for t in markers)
                       + b"".join(struct.pack("<5h", *t) for t in portals))
        lumps.append((name, payload))
    demo = bytearray((109, 2, 1, 1, 0, 0, 0, 1, 0, 1, 0, 0, 0))
    for tic in range(6300):
        # Rising use edges open each actual blue-key door; attack edges advance
        # the intermissions. No cheats or collision bypass are in the demo.
        buttons = (2 if tic % 500 == 20 else 0) | (1 if tic % 70 < 35 else 0)
        demo.extend((25, 0, 0, buttons))
    demo.append(128)
    lumps.append(("CHECKDEM", bytes(demo)))
    write_wad(path, lumps)
    return path


def live_verify(path):
    existing = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-Process -Name doom -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id"],
        capture_output=True, text=True,
    )
    if existing.stdout.strip():
        raise RuntimeError("An existing game must not be interrupted")
    started = time.time()
    source_hash = hashlib.sha256(CANDIDATE.read_bytes()).hexdigest()
    process = subprocess.Popen(
        [str(EXE), "-file", str(path), "-warp", "1", "1"],
        cwd=EXE.parent, env={**os.environ, "SteamAppId": "2280", "SteamGameId": "2280"},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    user32 = None
    seen = []
    try:
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            time.sleep(2)
            log = LOGS / "stdout.txt"
            if log.exists() and log.stat().st_mtime >= started:
                text = log.read_text(encoding="utf-8", errors="replace")
                first = venue_specs()[0]
                if f"adding {path.name}" in text and f"{first.name}: {first.title}" in text:
                    break
            if process.poll() is not None:
                raise RuntimeError("Owned game exited before checkpoint map initialization")
        else:
            raise RuntimeError("Fresh checkpoint map initialization was not logged")
        user32, hwnd = focus_owned_window(process.pid, reset_input=True)
        if not owns_foreground(process.pid):
            raise RuntimeError("Could not focus owned game; no input was sent")
        for _ in range(80):
            if process.poll() is not None:
                raise RuntimeError("Owned game exited before checkpoint verification completed")
            if not owns_foreground(process.pid):
                raise RuntimeError("Game lost foreground; input test stopped")
            # Do not repeatedly USE a normal door while it rises: Doom treats
            # another press as a request to reverse/close it.
            for vk, scan, duration in ((0x57, 0x11, 2), (0x20, 0x39, 0.15), (0x57, 0x11, 3)):
                if not owns_foreground(process.pid):
                    raise RuntimeError("Game lost foreground; no further input was sent")
                user32.keybd_event(vk, scan, 0, 0)
                try:
                    time.sleep(duration)
                finally:
                    user32.keybd_event(vk, scan, 2, 0)
            text = (LOGS / "stdout.txt").read_text(encoding="utf-8", errors="replace")
            seen = [f"E1M{i}" for i in range(1, 10) if f"E1M{i}:" in text]
            if len(seen) == 9:
                print("All nine maps reached through eight actual-map keyed exits", flush=True)
                return seen
        raise RuntimeError(f"Checkpoint input test reached only {seen}")
    finally:
        if user32 is not None:
            for vk, scan in ((0x57, 0x11), (0x20, 0x39)):
                user32.keybd_event(vk, scan, 2, 0)
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
        suffix = "" if len(seen) == 9 else "-last-attempt"
        (path.parent / f"checkpoint-live{suffix}-stdout.txt").write_bytes((LOGS / "stdout.txt").read_bytes())
        (path.parent / f"checkpoint-live{suffix}-results.json").write_text(json.dumps({
            "maps_reached": seen, "scope": "Eight keyed exits; nine maps reached; starts moved; combat removed",
            "wad_sha256": source_hash,
            "final_ending": "not visually tested",
            "full_traversal": "not tested",
        }, indent=2) + "\n")


def demo_verify(path):
    existing = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-Process -Name doom -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id"],
        capture_output=True, text=True,
    )
    if existing.stdout.strip():
        raise RuntimeError("An existing game must not be interrupted")
    started = time.time()
    digest = hashlib.sha256(CANDIDATE.read_bytes()).hexdigest()
    process = subprocess.Popen(
        [str(EXE), "-file", str(path), "-playdemo", "CHECKDEM"],
        cwd=EXE.parent, env={**os.environ, "SteamAppId": "2280", "SteamGameId": "2280"},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    seen = []
    try:
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            time.sleep(2)
            log = LOGS / "stdout.txt"
            if log.exists() and log.stat().st_mtime >= started:
                text = log.read_text(encoding="utf-8", errors="replace")
                if f"adding {path.name}" in text and "Playing demo CHECKDEM" in text:
                    seen = [f"E1M{i}" for i in range(1, 10) if f"E1M{i}:" in text]
                    if len(seen) == 9:
                        print("Deterministic demo reached all nine maps through actual keyed exits", flush=True)
                        return seen
            if process.poll() is not None:
                raise RuntimeError(f"Owned checkpoint demo exited after reaching {seen}")
        raise RuntimeError(f"Checkpoint demo reached only {seen}")
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
        suffix = "" if len(seen) == 9 else "-last-attempt"
        (path.parent / f"checkpoint-demo{suffix}-stdout.txt").write_bytes((LOGS / "stdout.txt").read_bytes())
        (path.parent / f"checkpoint-demo{suffix}-results.json").write_text(json.dumps({
            "maps_reached": seen, "wad_sha256": digest,
            "scope": "Eight keyed exits; nine maps reached; starts moved; combat removed",
            "final_ending": "not visually tested", "full_traversal": "not tested",
        }, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Isolated actual-map checkpoint test, not full traversal.")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--live", action="store_true")
    modes.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    from project_paths import ROOT
    target = ROOT / "runtime_validation" / "checkpoint-fixture.wad"
    target.parent.mkdir(exist_ok=True)
    print(build_fixture(target))
    if args.live:
        live_verify(target)
    elif args.demo:
        demo_verify(target)
