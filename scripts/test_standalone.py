import hashlib
import json
import re
import unittest
import zipfile
from pathlib import Path

from PIL import Image

from build_standalone import DIST, PACKAGE, RELEASE, STEAM


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class StandalonePackageTests(unittest.TestCase):
    def test_package_structure_and_manifest_hashes(self):
        manifest = json.loads((PACKAGE / "manifest.json").read_text())
        self.assertEqual(manifest["release_sha256"], _hash(RELEASE))
        for name in ("Paint_the_Town.wad", "Paint the Town.bat", "Paint the Town.ps1",
                     "README-STANDALONE.txt", "iwad/freedoom1.wad", "port/woof.exe",
                     "port/woof.pk3", "licenses/WOOF-COPYING.txt",
                     "licenses/FREEDOOM-COPYING.txt", "licenses/SOURCES.txt",
                     "licenses/PAINT-THE-TOWN-PROVENANCE.txt"):
            self.assertIn(name, manifest["files"], name)
        for relative, digest in manifest["files"].items():
            self.assertEqual(_hash(PACKAGE / relative), digest, relative)
        self.assertEqual(_hash(PACKAGE / "Paint_the_Town.wad"), _hash(RELEASE))

    def test_no_commercial_iwad_is_bundled(self):
        forbidden = {"DOOM.WAD", "DOOM2.WAD", "PLUTONIA.WAD", "TNT.WAD", "DOOM1.WAD"}
        names = {path.name.upper() for path in PACKAGE.rglob("*") if path.is_file()}
        self.assertFalse(names & forbidden)
        with zipfile.ZipFile(DIST / "Paint_the_Town_Standalone.zip") as bundle:
            archive_names = {Path(name).name.upper() for name in bundle.namelist()}
        self.assertFalse(archive_names & forbidden)
        self.assertIn("FREEDOOM1.WAD", archive_names)

    def test_launcher_prefers_owned_doom_and_falls_back_to_freedoom(self):
        script = (PACKAGE / "Paint the Town.ps1").read_text()
        self.assertIn(r"iwad\freedoom1.wad", script)
        self.assertIn("DOOM.WAD", script)
        self.assertIn(r"port\woof.exe", script)
        self.assertIn("Paint_the_Town.wad", script)
        self.assertNotIn("C:\\Users\\", script)
        batch = (PACKAGE / "Paint the Town.bat").read_text()
        self.assertIn("Paint the Town.ps1", batch)

    def test_store_assets_match_their_required_dimensions(self):
        assets = STEAM / "store_assets"
        for path in assets.glob("*.png"):
            width, height = map(int, re.search(r"_(\d+)x(\d+)\.png$", path.name).groups())
            with Image.open(path) as image:
                self.assertEqual(image.size, (width, height), path.name)
        screenshots = list((assets / "screenshots").glob("*.png"))
        self.assertGreaterEqual(len(screenshots), 5)
        for path in screenshots:
            with Image.open(path) as image:
                self.assertEqual(image.size, (1920, 1080), path.name)

    def test_steam_build_scripts_reference_the_package(self):
        app = (STEAM / "app_build.vdf").read_text()
        depot = (STEAM / "depot_build.vdf").read_text()
        self.assertIn(r"..\\dist\\Paint_the_Town_Standalone\\", app)
        self.assertIn('"depot_build.vdf"', app)
        self.assertIn('"DepotID"', depot)
        self.assertIn('"recursive"\t"1"', depot)


if __name__ == "__main__":
    unittest.main()
