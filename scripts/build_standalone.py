"""Build the standalone Steam-ready Paint the Town package and store artifacts."""

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from project_paths import ROOT, ART_SOURCES


PORTS = ROOT / "tools" / "ports"
WOOF_SOURCE = PORTS / "woof" / "Woof-16.0.0-win64"
FREEDOOM_SOURCE = PORTS / "freedoom" / "freedoom-0.13.0"
RELEASE = ROOT / "Paint_the_Town.wad"
DIST = ROOT / "dist"
PACKAGE = DIST / "Paint_the_Town_Standalone"
STEAM = ROOT / "steam"
WOOF_VERSION = "16.0.0"
FREEDOOM_VERSION = "0.13.0"
WOOF_SOURCE_URL = "https://github.com/fabiangreffrath/woof/releases/tag/woof_16.0.0"
FREEDOOM_URL = "https://github.com/freedoom/freedoom/releases/tag/v0.13.0"

LAUNCHER_PS1 = r'''# Paint the Town launcher: prefers an owned DOOM.WAD, else bundled Freedoom.
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$candidates = @(
    "C:\Program Files (x86)\Steam\steamapps\common\Ultimate Doom\base\DOOM.WAD",
    "C:\Program Files (x86)\Steam\steamapps\common\Ultimate Doom\rerelease\DOOM.WAD",
    "C:\Program Files\Steam\steamapps\common\Ultimate Doom\base\DOOM.WAD",
    "C:\GOG Games\DOOM\DOOM.WAD"
)
$iwad = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $iwad) {
    $iwad = Join-Path $root "iwad\freedoom1.wad"
    Write-Host "Using bundled Freedoom Phase 1 assets (BSD-licensed)."
    Write-Host "Own DOOM? Install it on Steam/GOG for the authentic base assets."
} else {
    Write-Host "Using your owned DOOM.WAD: $iwad"
}
New-Item -ItemType Directory -Path (Join-Path $root "saves") -Force | Out-Null
& (Join-Path $root "port\woof.exe") -iwad "$iwad" `
    -file (Join-Path $root "Paint_the_Town.wad") `
    -save (Join-Path $root "saves")
'''

LAUNCHER_BAT = r'''@echo off
rem Paint the Town launcher (delegates to the PowerShell launcher).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Paint the Town.ps1"
'''

STANDALONE_README = """Paint the Town - standalone package
===================================

A nine-map Toronto paintball campaign for the DOOM engine, bundled with the
Woof! source port (GPL) so it runs as its own game.

LEGAL / WHAT IS AND IS NOT INCLUDED
- Paint_the_Town.wad is original project-owned content.
- Woof! {woof} is free software (GPLv2+); its license is in licenses\\.
  Source code: {woof_url}
- Freedoom Phase 1 {freedoom} (freedoom1.wad) is included under its BSD
  license so the game runs fully standalone. {freedoom_url}
- NO commercial id Software/Bethesda IWAD is included. If you own DOOM
  (Ultimate Doom / DOOM + DOOM II on Steam or GOG), the launcher automatically
  uses your DOOM.WAD for the authentic base assets. Owning DOOM is OPTIONAL
  thanks to Freedoom, but recommended.
- This project is not affiliated with or endorsed by id Software, Bethesda,
  or Valve.

HOW TO PLAY
1. Double-click "Paint the Town.bat" (or the .ps1).
2. Start a NEW GAME. Find the Portal Key in each venue and press Spacebar at
   the gold EXIT panel.

ADD TO STEAM (local library entry)
1. Steam > Games menu > "Add a Non-Steam Game to My Library...".
2. Click Browse, change the file-type dropdown from "Executables" to
   "All Files (*.*)", then select "Paint the Town.bat" in this folder.
   (Alternative: add port\\woof.exe and set its Steam launch options to
   -iwad ..\\iwad\\freedoom1.wad -file ..\\Paint_the_Town.wad -save ..\\saves)
3. Rename the entry to "Paint the Town"; optionally set the artwork from
   steam_grid\\ in this package.

SAVES live in saves\\ inside this folder. Keyboard: W A S D + mouse;
Tab shows the map. Built by Richard Harris.

TROUBLESHOOTING: SOUND STOPS DURING PLAY
If the game goes silent while other apps still play sound, another
application took exclusive control of your audio device or changed its
format, which disconnects the game's audio stream.
- Instant fix in game: Options > General > Audio > change "Sound Module"
  (any change reconnects the audio immediately; you can change it back).
- Permanent fix in Windows: Settings > Sound > your output device >
  Properties > Advanced: untick "Allow applications to take exclusive
  control of this device" and set the format to 48000 Hz.
"""

PROVENANCE_NOTE = """Paint the Town content provenance
---------------------------------
All campaign art, maps, music and code in Paint_the_Town.wad are
project-owned, AI-assisted original work; no commercial game assets are
embedded. Full provenance lives in the source repository
(assets/art_sources, README.md and docs/). AI-assisted output is not certified for
exclusive copyright ownership. Woof! and Freedoom retain their own licenses
in this folder.
"""


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_package():
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    (PACKAGE / "iwad").mkdir(parents=True)
    (PACKAGE / "licenses").mkdir()
    (PACKAGE / "steam_grid").mkdir()
    shutil.copytree(WOOF_SOURCE, PACKAGE / "port",
                    ignore=shutil.ignore_patterns("woof-setup.exe"))
    # A config beside the executable keeps Woof fully portable.
    (PACKAGE / "port" / "woof.cfg").write_text("")
    shutil.copy2(RELEASE, PACKAGE / "Paint_the_Town.wad")
    shutil.copy2(FREEDOOM_SOURCE / "freedoom1.wad", PACKAGE / "iwad" / "freedoom1.wad")
    shutil.copy2(WOOF_SOURCE / "COPYING.txt", PACKAGE / "licenses" / "WOOF-COPYING.txt")
    for name in ("COPYING.txt", "CREDITS.txt"):
        shutil.copy2(FREEDOOM_SOURCE / name, PACKAGE / "licenses" / f"FREEDOOM-{name}")
    (PACKAGE / "licenses" / "SOURCES.txt").write_text(
        f"Woof! {WOOF_VERSION} (GPLv2+): {WOOF_SOURCE_URL}\n"
        f"Freedoom {FREEDOOM_VERSION} (BSD): {FREEDOOM_URL}\n")
    (PACKAGE / "licenses" / "PAINT-THE-TOWN-PROVENANCE.txt").write_text(PROVENANCE_NOTE)
    (PACKAGE / "Paint the Town.ps1").write_text(LAUNCHER_PS1)
    (PACKAGE / "Paint the Town.bat").write_text(LAUNCHER_BAT)
    (PACKAGE / "README-STANDALONE.txt").write_text(STANDALONE_README.format(
        woof=WOOF_VERSION, woof_url=WOOF_SOURCE_URL,
        freedoom=FREEDOOM_VERSION, freedoom_url=FREEDOOM_URL))
    grid_art()
    manifest = {"release_sha256": _hash(RELEASE), "woof_version": WOOF_VERSION,
                "freedoom_version": FREEDOOM_VERSION, "files": {}}
    for path in sorted(PACKAGE.rglob("*")):
        if path.is_file():
            manifest["files"][path.relative_to(PACKAGE).as_posix()] = _hash(path)
    (PACKAGE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    archive = DIST / "Paint_the_Town_Standalone.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(PACKAGE.rglob("*")):
            if path.is_file():
                bundle.write(path, Path("Paint_the_Town_Standalone") / path.relative_to(PACKAGE))
    print(f"Package: {PACKAGE} ({len(manifest['files'])} files); zip {archive.stat().st_size:,} bytes")


def _key_art():
    with Image.open(ART_SOURCES / "expansion_header_source.png") as source:
        return source.convert("RGB")


def _fit(size, centering=(0.5, 0.35)):
    return ImageOps.fit(_key_art(), size, method=Image.Resampling.LANCZOS,
                        centering=centering)


def _showcase(size, margin=0.0):
    """Zoomed-out wide art: the complete key art over a blurred, darkened fill.

    margin insets the foreground art so edge content (the painted title)
    survives the slight cropping Steam applies to detail-page backgrounds.
    """
    art = _key_art()
    base = ImageOps.fit(art, size, method=Image.Resampling.LANCZOS)
    base = base.filter(ImageFilter.GaussianBlur(max(size) // 70))
    base = ImageEnhance.Brightness(base).enhance(0.5)
    inner = (round(size[0] * (1 - margin)), round(size[1] * (1 - margin)))
    front = ImageOps.contain(art, inner, Image.Resampling.LANCZOS)
    base.paste(front, ((size[0] - front.width) // 2, (size[1] - front.height) // 2))
    return base


def grid_art():
    # Steam library artwork for the local non-Steam-game entry. The wide
    # formats show the complete key art (nothing cropped) over a blurred fill.
    targets = {"grid-600x900.png": ((600, 900), (0.5, 0.35)),
               "icon-256.png": ((256, 256), (0.5, 0.3))}
    for name, (size, centering) in targets.items():
        _fit(size, centering).save(PACKAGE / "steam_grid" / name)
    for name, size, margin in (("grid-920x430.png", (920, 430), 0.25),
                               ("hero-1920x620.png", (1920, 620), 0.30)):
        _showcase(size, margin).save(PACKAGE / "steam_grid" / name)


def store_assets():
    assets = STEAM / "store_assets"
    assets.mkdir(parents=True, exist_ok=True)
    sizes = {"main_capsule_616x353.png": ((616, 353), (0.5, 0.3)),
             "vertical_capsule_374x448.png": ((374, 448), (0.5, 0.35)),
             "library_capsule_600x900.png": ((600, 900), (0.5, 0.35)),
             "page_background_1438x810.png": ((1438, 810), (0.5, 0.4)),
             "community_icon_184x184.png": ((184, 184), (0.5, 0.3)),
             "client_icon_32x32.png": ((32, 32), (0.5, 0.3))}
    for name, size, margin in (("header_capsule_460x215.png", (460, 215), 0.0),
                               ("small_capsule_231x87.png", (231, 87), 0.0),
                               ("library_hero_3840x1240.png", (3840, 1240), 0.30)):
        _showcase(size, margin).save(assets / name)
    for name, (size, centering) in sizes.items():
        _fit(size, centering).save(assets / name)
    logo = Image.new("RGBA", (1280, 720))
    with Image.open(ART_SOURCES / "expansion_header_source.png") as source:
        title = source.convert("RGBA").crop((470, 10, 1190, 330))
    title = ImageOps.contain(title, (1100, 620), Image.Resampling.LANCZOS)
    logo.alpha_composite(title, ((1280 - title.width) // 2, (720 - title.height) // 2))
    logo.save(assets / "library_logo_1280x720.png")
    screenshots = assets / "screenshots"
    screenshots.mkdir(exist_ok=True)
    scenes = ROOT / "runtime_validation" / "candidate-revisions"
    for name in ("rom-gallery", "zoo-eurasia", "baseball-side", "islands-start",
                 "sankofa-stage", "union-hotel-north", "park-woodland"):
        source = scenes / f"{name}.png"
        if source.exists():
            with Image.open(source) as image:
                image.convert("RGB").save(screenshots / f"{name}-1920x1080.png")
    print(f"Store assets: {assets}")


if __name__ == "__main__":
    build_package()
    store_assets()
