import argparse
import ctypes
import hashlib
import json
import os
import subprocess
import time
from ctypes import wintypes
from pathlib import Path

from build_expansion import CANDIDATE
from toronto_venues import venue_specs


EXE = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Ultimate Doom\rerelease\doom.exe")
LOGS = Path.home() / "Saved Games" / "Nightdive Studios" / "DOOM"


def owns_foreground(pid):
    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = ctypes.c_void_p
    owner = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(ctypes.c_void_p(user32.GetForegroundWindow()), ctypes.byref(owner))
    return owner.value == pid


def focus_owned_window(pid, reset_input=False):
    windows = []
    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = ctypes.c_void_p
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def visit(hwnd, _):
        owner = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(ctypes.c_void_p(hwnd)):
            rect = wintypes.RECT()
            user32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(rect))
            windows.append(((rect.right - rect.left) * (rect.bottom - rect.top), hwnd))
        return True

    user32.EnumWindows(callback_type(visit), 0)
    if not windows:
        raise RuntimeError("Owned KEX process has no visible capture window")
    _, hwnd = max(windows)
    handle = ctypes.c_void_p(hwnd)
    if reset_input:
        user32.ShowWindow(handle, 6)
        time.sleep(1)
    current_thread = ctypes.windll.kernel32.GetCurrentThreadId()
    foreground = user32.GetForegroundWindow()
    foreground_thread = user32.GetWindowThreadProcessId(ctypes.c_void_p(foreground), None)
    target_thread = user32.GetWindowThreadProcessId(handle, None)
    attached = {thread for thread in (foreground_thread, target_thread)
                if thread and thread != current_thread}
    for thread in attached:
        user32.AttachThreadInput(current_thread, thread, True)
    try:
        user32.ShowWindow(handle, 9)
        user32.SetForegroundWindow(handle)
    finally:
        for thread in attached:
            user32.AttachThreadInput(current_thread, thread, False)
    time.sleep(3)
    return user32, hwnd


def capture_window(pid, output, backend="gfxcapture", toggle_window=False):
    from PIL import Image, ImageStat
    user32, hwnd = focus_owned_window(pid)
    handle = ctypes.c_void_p(hwnd)
    if toggle_window:
        if user32.GetForegroundWindow() != hwnd:
            raise RuntimeError("Only the owned foreground game may receive window-toggle input")
        for vk, up in ((0x12, False), (0x0D, False), (0x0D, True), (0x12, True)):
            user32.keybd_event(vk, 0, 2 if up else 0, 0)
            time.sleep(0.1)
        time.sleep(4)
    print(f"Capturing owned KEX window {hwnd}, foreground={user32.GetForegroundWindow()}", flush=True)
    if backend == "ddagrab":
        if user32.GetForegroundWindow() != hwnd:
            raise RuntimeError("Desktop duplication requires the owned game to be foreground")
        rect = wintypes.RECT()
        user32.GetWindowRect(handle, ctypes.byref(rect))
        capture = (f"ddagrab=offset_x={max(0, rect.left)}:offset_y={max(0, rect.top)}:"
                   f"video_size={rect.right - rect.left}x{rect.bottom - rect.top}:draw_mouse=0")
    else:
        capture = f"gfxcapture=hwnd={hwnd}:capture_cursor=0:max_framerate=10"
    staged = output.with_name(output.stem + ".capture.png")
    try:
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
             capture, "-vf", "hwdownload,format=bgra", "-frames:v", "1", str(staged)],
            check=True, capture_output=True, timeout=30,
        )
        with Image.open(staged) as image:
            if max(ImageStat.Stat(image.convert("RGB")).stddev) < 8:
                raise RuntimeError("Graphics capture returned a black/blank frame; it is not gameplay evidence")
        staged.replace(output)
    finally:
        if staged.exists():
            staged.unlink()
        if toggle_window and user32.GetForegroundWindow() == hwnd:
            for vk, up in ((0x12, False), (0x0D, False), (0x0D, True), (0x12, True)):
                user32.keybd_event(vk, 0, 2 if up else 0, 0)
                time.sleep(0.1)


def verify(output, maps, capture=False, backend="gfxcapture", toggle_window=False):
    # Never interrupt an existing game or attribute its shared log to this test.
    existing = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-Process -Name doom -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id"],
        capture_output=True, text=True,
    )
    if existing.stdout.strip():
        raise RuntimeError("Close the existing DOOM game before running the runtime verifier")
    output.mkdir(parents=True, exist_ok=True)
    environment = {**os.environ, "SteamAppId": "2280", "SteamGameId": "2280"}
    wad_hash = hashlib.sha256(CANDIDATE.read_bytes()).hexdigest()
    manifest = output / "runtime-results.json"
    previous = json.loads(manifest.read_text()) if manifest.exists() else []
    results = [item for item in previous
               if item.get("wad_sha256") == wad_hash and item["map"] not in maps]
    for spec in venue_specs():
        if spec.name not in maps:
            continue
        started = time.time()
        process = subprocess.Popen(
            [str(EXE), "-file", str(CANDIDATE), "-warp", "1", spec.name[-1]],
            cwd=EXE.parent, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.monotonic() + 180
            initialized = False
            while time.monotonic() < deadline:
                time.sleep(2)
                log = LOGS / "stdout.txt"
                if log.exists() and log.stat().st_mtime >= started:
                    text = log.read_text(encoding="utf-8", errors="replace")
                    initialized = (f"{spec.name}: {spec.title}" in text
                                   and f"Playing 'D_{spec.name}.ogg'" in text
                                   and "P_SetupLevel: Using limit-removing structures" in text)
                    if initialized:
                        break
                if process.poll() is not None:
                    raise RuntimeError(f"{spec.name}: owned KEX process exited with {process.returncode}")
            if not initialized:
                raise RuntimeError(f"{spec.name}: map did not initialize in the KEX log")
            time.sleep(5)
            if process.poll() is not None:
                raise RuntimeError(f"{spec.name}: KEX exited after map setup")
            for name in ("stdout.txt", "stderr.txt"):
                source = LOGS / name
                if source.exists():
                    (output / f"{spec.name}-{name}").write_bytes(source.read_bytes())
            text = (output / f"{spec.name}-stdout.txt").read_text(encoding="utf-8", errors="replace")
            failures = [line for line in text.splitlines()
                        if any(marker in line for marker in
                               ("R_TextureNumForName:", "R_InitSprites:", "P_Load",
                                "I_Error:", "Unknown thing type", "Bad sfx", "Segmentation",
                                "Exception caught"))]
            if failures:
                raise RuntimeError(f"{spec.name}: runtime diagnostics: {failures}")
            if capture:
                capture_window(process.pid, output / f"{spec.name}-gameplay.png", backend, toggle_window)
            results.append({"map": spec.name, "title": spec.title,
                            "startup_and_music": "passed", "traversal": "not tested",
                            "wad_sha256": wad_hash, "graphics_capture": capture})
            print(f"{spec.name}: initialized with its own soundtrack; process remained alive", flush=True)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
            (output / "runtime-results.json").write_text(json.dumps(results, indent=2) + "\n")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check owned KEX map starts; not a traversal/performance test.")
    from project_paths import ROOT
    parser.add_argument("--output", type=Path, default=ROOT / "runtime_validation")
    parser.add_argument("--maps", nargs="+", default=[f"E1M{i}" for i in range(1, 10)])
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--capture-backend", choices=("gfxcapture", "ddagrab"), default="gfxcapture")
    parser.add_argument("--toggle-window", action="store_true")
    args = parser.parse_args()
    verify(args.output, set(args.maps), args.capture, args.capture_backend, args.toggle_window)
