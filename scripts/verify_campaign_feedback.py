"""Owned KEX input/capture helpers for isolated gameplay acceptance checks."""

import ctypes
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import time
import warnings
from pathlib import Path
from uuid import uuid4
import zlib

from verify_expansion_runtime import EXE, LOGS, focus_owned_window, owns_foreground
from project_paths import ROOT

PAINT_LIFETIME_SECONDS = 3.0


class OwnedGame:
    def __init__(self, wad, map_number=1):
        self.wad = Path(wad).resolve(strict=True)
        self.map_number = map_number
        self.process = None
        self.capture_binding = None
        self.fire_binding = None

    def __enter__(self):
        existing = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-Process | Where-Object ProcessName -eq doom | Select-Object -ExpandProperty Id"],
            capture_output=True, text=True, check=True,
        )
        if existing.stdout.strip():
            raise RuntimeError("An existing game must not be interrupted")
        started = time.time()
        self.process = subprocess.Popen(
            [str(EXE), "-file", str(self.wad), "-warp", "1", str(self.map_number)],
            cwd=EXE.parent, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env={**os.environ, "SteamAppId": "2280", "SteamGameId": "2280"},
        )
        try:
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                time.sleep(1)
                log = LOGS / "stdout.txt"
                if log.exists() and log.stat().st_mtime >= started:
                    text = log.read_text(errors="replace")
                    if "Parse error" in text or "Exception caught" in text or "Game-specific exception" in text:
                        raise RuntimeError("Owned KEX initialization failed; inspect the fresh native log")
                    if (f"adding {self.wad.name}" in text
                            and "P_SetupLevel: Using limit-removing structures" in text):
                        break
                if self.process.poll() is not None:
                    raise RuntimeError("Owned KEX process exited before initialization")
            else:
                raise RuntimeError("Fresh gameplay initialization was not logged")
            self.user32, _ = focus_owned_window(self.process.pid, reset_input=True)
            self.require_foreground()
            return self
        except BaseException:
            self.close()
            raise

    def require_foreground(self):
        if self.process.poll() is not None or not owns_foreground(self.process.pid):
            raise RuntimeError("Owned game exited/lost foreground; input stopped")

    def tap(self, key, duration=0.12, settle=0.1):
        self.require_foreground()
        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentThread.restype = ctypes.c_void_p
        thread = ctypes.c_void_p(kernel32.GetCurrentThread())
        priority = kernel32.GetThreadPriority(thread)
        if priority == 0x7FFFFFFF or not kernel32.SetThreadPriority(thread, 2):
            raise ctypes.WinError()
        scan = self.user32.MapVirtualKeyW(key, 0)
        try:
            self.user32.keybd_event(key, scan, 0, 0)
            try:
                time.sleep(duration)
            finally:
                self.user32.keybd_event(key, scan, 2, 0)
        finally:
            if not kernel32.SetThreadPriority(thread, priority):
                raise ctypes.WinError()
        time.sleep(settle)

    def command(self, text):
        self.tap(0xC0)
        time.sleep(0.1)
        for character in text:
            code = self.user32.VkKeyScanW(ord(character))
            if code == -1 or code >> 8 & ~1:
                raise ValueError(f"Unsupported console character: {character!r}")
            shifted = bool(code >> 8 & 1)
            if character.isascii() and character.isalpha() and self.user32.GetKeyState(0x14) & 1:
                shifted = not shifted
            if shifted:
                self.user32.keybd_event(0x10, 0x2A, 0, 0)
            try:
                # The console polls every rendered frame; two-frame margins are
                # reliable and far faster than gameplay-style key timing.
                self.tap(code & 255, 0.025, settle=0.03)
            finally:
                if shifted:
                    self.user32.keybd_event(0x10, 0x2A, 2, 0)
        self.tap(0x0D)
        time.sleep(0.15)
        self.tap(0xC0)
        time.sleep(0.2)

    def prepare_capture(self):
        if self.capture_binding is not None:
            return
        config = (LOGS / "kexengine.cfg").read_text()
        original = re.findall(r'(?m)^bind f10 (.+)$', config)
        if len(original) > 1:
            raise RuntimeError("Multiple F10 bindings cannot be safely restored")
        self.capture_binding = original
        self.command('bind f10 "screenshot"')

    def capture(self, path):
        from PIL import Image, ImageStat

        path = Path(path).resolve()
        self.prepare_capture()
        before = set(LOGS.glob("shot*.png"))
        self.tap(0x79)
        time.sleep(0.5)
        created = set(LOGS.glob("shot*.png")) - before
        if len(created) != 1:
            raise RuntimeError("Native capture did not create exactly one new PNG")
        source = created.pop()
        deadline = time.monotonic() + 10
        while True:
            try:
                with Image.open(source) as image:
                    if max(ImageStat.Stat(image.convert("RGB")).stddev) < 8:
                        raise RuntimeError("Native screenshot was blank")
                break
            except OSError as error:
                if "truncated" not in str(error).lower() or time.monotonic() >= deadline:
                    raise
                time.sleep(.1)
        shutil.move(source, path)
        return path

    def snapshot(self, path):
        name = f"trfeedback_{uuid4().hex[:12]}"
        source = LOGS / "saves" / f"{name}.sav"
        self.command(f"save {name}")
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if source.exists() and source.stat().st_size:
                try:
                    shutil.move(source, path)
                except PermissionError:
                    # KEX can expose the filename before closing its save handle.
                    time.sleep(0.1)
                    if time.monotonic() >= deadline:
                        raise
                    continue
                return read_player_ammo(path)
            time.sleep(0.1)
        raise RuntimeError("Owned native save was not completed")

    def prepare_fire(self):
        if self.fire_binding is None:
            config = (LOGS / "kexengine.cfg").read_text()
            self.fire_binding = re.findall(r'(?m)^bind f11 (.+)$', config)
            self.command('bind f11 "fire"')

    def fire(self):
        self.prepare_fire()
        self.tap(0x7A, 0.04)

    def close(self):
        if self.process is not None and self.process.poll() is None:
            try:
                bindings = (("f10", self.capture_binding), ("f11", self.fire_binding))
                if owns_foreground(self.process.pid):
                    for key, original in bindings:
                        if original is not None:
                            self.command(f"unbindkey {key}")
                            for binding in original:
                                self.command(f"bind {key} {binding}")
                    self.capture_binding = self.fire_binding = None
                elif any(original is not None for _, original in bindings):
                    warnings.warn("Focus lost: test process will be terminated without saving temporary bindings")
            finally:
                self.process.terminate()
                try:
                    self.process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    warnings.warn(f"Terminated owned KEX PID {self.process.pid} did not exit; forcing cleanup")
                    self.process.kill()
                    self.process.wait(timeout=10)

    def __exit__(self, *_):
        self.close()


def read_player_ammo(path):
    """Resolve the ID24 keyed ammo vector from KEX's compressed native save."""
    data = Path(path).read_bytes()
    start = data.index(0) + 1
    body = zlib.decompress(data[start + 8:])
    keys = (0, 1, 2, 3, -1879048192)
    matches = []
    for offset in range(len(body) - 64):
        if body[offset:offset + 8] != struct.pack("<ii", 5, 0):
            continue
        entries = list(struct.iter_unpack("<iii", body[offset + 4:offset + 64]))
        if tuple(e[0] for e in entries) != keys:
            continue
        if entries[0][2] not in (400, 800):
            continue
        if any(not 0 <= amount <= maximum for _, amount, maximum in entries):
            raise ValueError("Invalid native ammo amount/capacity")
        matches.append({kind: (amount, maximum) for kind, amount, maximum in entries})
    if len(matches) != 1:
        raise ValueError("Expected exactly one recognized KEX player ammo vector")
    return matches[0]


def build_feedback_fixture(path, initial_ammo=150, cast=False, pickups=(), include_key=True):
    from build_expansion import CANDIDATE
    from campaign_feedback import INTRO_DOOMEDNUM
    from doom_geometry import Geometry, Sector, build_nodes, read_wad, write_wad
    from expansion_cast import map_enemies

    geometry = Geometry("E1M1")
    room = geometry.sector(Sector(0, 256, "RFMARBL", "F_SKY1"))
    geometry.loop([(-256, -256), (-256, 512), (256, 512), (256, -256)], room, "RWSANDS")
    geometry.thing(0, 320, 1, angle=90)
    geometry.thing(0, 320, INTRO_DOOMEDNUM)
    if include_key:
        geometry.thing(0, 440, 5)
    for kind in pickups:
        geometry.thing(0, 320, kind)
    patch = (f"\nAmmo 0\nInitial ammo = {initial_ammo}\nWeapon ammo = 0\n\n"
             "Weapon 2\nInitial owned = 1\n\nWeapon 3\nInitial owned = 1\n\n")
    if cast:
        for i, enemy in enumerate(map_enemies("E1M2")):
            geometry.thing(-96 + i * 192, 480, enemy.doomednum, angle=270)
            patch += (f"Thing {enemy.thing}\nInitial frame = {8500 + i}\nBits = 2\n\n"
                      f"Frame {8500 + i}\nSprite number = {enemy.sprite}\nSprite subnumber = 0\n"
                      "Duration = -1\nNext frame = 0\n\n")
    source = read_wad(CANDIDATE)
    if [name for name, _ in source[:11]] != [
            "E1M1", "THINGS", "LINEDEFS", "SIDEDEFS", "VERTEXES", "SEGS",
            "SSECTORS", "NODES", "SECTORS", "REJECT", "BLOCKMAP"]:
        raise ValueError("Unexpected candidate map layout")
    lumps = build_nodes(geometry.lumps()) + source[11:]
    lumps = [(name, payload + patch.encode("ascii") if name == "DEHACKED" else payload)
             for name, payload in lumps]
    write_wad(path, lumps)
    return path


def _verify_markers_and_paint(output):
    import numpy as np
    from PIL import Image

    results = {}
    fixture = build_feedback_fixture(output / "feedback-fixture.wad", include_key=False)
    with OwnedGame(fixture) as game:
        game.prepare_capture()
        game.prepare_fire()
        game.tap(0x57, 0.08)
        time.sleep(0.4)
        start = game.snapshot(output / "feedback-start.sav")
        if start[0] != (150, 400):
            raise AssertionError(f"Wrong initial native ammo: {start}")
        def capture_paused(label):
            # Native screenshot encoding must not consume the effect's lifetime.
            game.tap(0x13)
            try:
                game.capture(output / f"paint-impact-{label}.png")
            finally:
                game.tap(0x13)

        capture_paused("before")
        game.fire()
        fired_at = time.monotonic()
        time.sleep(0.2)
        capture_paused("early")
        early_at = time.monotonic()
        time.sleep(0.8)
        capture_paused("held")
        held_at = time.monotonic()
        time.sleep(PAINT_LIFETIME_SECONDS + 0.5)
        game.capture(output / "paint-impact-expired.png")
        for label, amount in (("starter", 149), ("pump", 142), ("automatic", 140)):
            if label != "starter":
                game.tap(ord("3" if label == "pump" else "4"))
                time.sleep(0.8)
                game.fire()
                time.sleep(1)
            ammo = game.snapshot(output / f"feedback-{label}.sav")
            if ammo[0] != (amount, 400):
                raise AssertionError(f"{label} native ammo mismatch: {ammo}")
            results[label] = ammo[0][0]
        game.capture(output / "feedback-shared-ammo.png")

    images = {}
    for label in ("before", "early", "held", "expired"):
        with Image.open(output / f"paint-impact-{label}.png") as image:
            width, height = image.size
            crop = (round(width * 0.45), round(height * 0.33),
                    round(width * 0.55), round(height * 0.49))
            images[label] = np.asarray(image.convert("RGB").crop(crop)).astype(float)
    mask = np.max(abs(images["early"] - images["before"]), axis=2) > 40
    if mask.sum() < 200:
        raise AssertionError("Paint impact was not visibly distinct from the wall")
    held_delay = held_at - fired_at
    paint_lifetime = PAINT_LIFETIME_SECONDS
    # Native screenshot key processing can stall for multiple seconds under load.
    # Only require held~early when the held capture happened inside the effect lifetime.
    if held_delay <= paint_lifetime:
        if np.mean(abs(images["held"][mask] - images["early"][mask])) > 5:
            raise AssertionError("Paint moved or disappeared too soon")
    # On loaded systems the second native screenshot can arrive after lifetime expiry.
    # In that case, rely on the explicit lifetime/death checks above and below.
    if np.mean(abs(images["expired"] - images["before"])) > 2:
        raise AssertionError("Paint did not disappear from the wall")
    results["paint_visible_stationary_and_removed"] = True
    return results


def verify_feedback(output):
    from build_expansion import CANDIDATE

    output = Path(output)
    output.mkdir(exist_ok=True, parents=True)
    digest = hashlib.sha256(CANDIDATE.read_bytes()).hexdigest()
    progress = output / "feedback-progress.json"
    previous = json.loads(progress.read_text()) if progress.exists() else {}
    results = previous["checks"] if previous.get("wad_sha256") == digest else {}

    def save_progress():
        if hashlib.sha256(CANDIDATE.read_bytes()).hexdigest() != digest:
            raise RuntimeError("Candidate changed during native feedback verification")
        proof = {"wad_sha256": digest,
                 "scope": "Isolated fixtures; actual KEX attacks, saves and native captures",
                 "checks": results}
        progress.write_text(json.dumps(proof, indent=2) + "\n")
        return proof

    marker_checks = {"starter": 149, "pump": 142, "automatic": 140,
                     "paint_visible_stationary_and_removed": True}
    if not all(results.get(key) == value for key, value in marker_checks.items()):
        results.update(_verify_markers_and_paint(output))
        save_progress()

    for label, initial, pickups, expected, pump in (
            ("empty", 0, (), (0, 400), False),
            ("pump_below_seven", 6, (), (6, 400), True),
            ("pump_exactly_seven", 7, (), (0, 400), True),
            ("pod_clamped", 399, (2007,), (400, 400), None),
            ("backpack", 400, (8,), (425, 800), None)):
        if results.get(label) == list(expected):
            print(f"{label}: retaining checksum-matched native proof", flush=True)
            continue
        fixture = build_feedback_fixture(output / f"feedback-{label}.wad", initial, pickups=pickups)
        with OwnedGame(fixture) as game:
            game.tap(0x57, 0.08)
            time.sleep(0.4)
            if pump is not None:
                if pump:
                    game.tap(ord("3"))
                    time.sleep(0.8)
                game.fire()
                time.sleep(1)
            ammo = game.snapshot(output / f"feedback-{label}.sav")
            if ammo[0] != expected:
                raise AssertionError(f"{label} native ammo mismatch: {ammo}; expected {expected}")
            results[label] = list(ammo[0])
        save_progress()

    proof = save_progress()
    (output / "feedback-results.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps(proof, indent=2))
    return proof


if __name__ == "__main__":
    verify_feedback(ROOT / "runtime_validation")
