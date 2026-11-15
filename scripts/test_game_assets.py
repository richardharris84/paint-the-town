import json
from pathlib import Path
import struct
import tempfile
import unittest
import wave

from PIL import Image

from export_game_assets import OUTPUT, digest, patch_image, export
from doom_geometry import read_wad
from project_paths import ASSETS, ROOT, CANDIDATE, RELEASE


class GameAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((OUTPUT / "manifest.json").read_text(encoding="utf-8"))

    def load(self, name):
        return json.loads((OUTPUT / name).read_text(encoding="utf-8"))

    def test_root_is_organized_and_export_matches_candidate(self):
        self.assertFalse(list(ROOT.glob("*.py")))
        self.assertFalse(list(ROOT.glob("*.png")))
        self.assertEqual(self.manifest["source_sha256"],
                         digest(CANDIDATE))
        published = RELEASE.exists() and CANDIDATE.read_bytes() == RELEASE.read_bytes()
        self.assertEqual(self.manifest["source_is_published"], published)
        self.assertEqual(self.manifest["published_wad_sha256"],
                         digest(RELEASE) if RELEASE.exists() else None)
        self.assertEqual(self.manifest["release_status"],
                         "published" if published else "candidate only; not yet published")
        images = self.load("source_images.json")
        self.assertEqual({entry["path"] for entry in images}, {p.name for p in ASSETS.glob("*.png")})
        for entry in images:
            self.assertEqual(entry["sha256"], digest(ASSETS / entry["path"]))
        scripts = self.load("scripts.json")
        self.assertEqual({entry["path"] for entry in scripts},
                         {p.name for p in (ROOT / "scripts").glob("*.py")})

    def test_all_manifest_files_have_valid_hashes(self):
        paths = [entry["path"] for entry in self.manifest["files"]]
        self.assertEqual(len(paths), len(set(paths)))
        for entry in self.manifest["files"]:
            with self.subTest(path=entry["path"]):
                path = (OUTPUT / entry["path"]).resolve()
                self.assertTrue(path.is_relative_to(OUTPUT))
                self.assertEqual(entry["sha256"], digest(path))
        self.assertEqual(set(paths) | {"manifest.json"},
                         {p.relative_to(OUTPUT).as_posix() for p in OUTPUT.rglob("*") if p.is_file()})

    def test_roster_sprites_and_sounds_are_resolvable(self):
        actors = self.load("npcs.json")
        sprites, audio = self.load("sprites.json"), self.load("audio.json")
        self.assertEqual(len(actors), 19)
        self.assertEqual(len({actor["doomednum"] for actor in actors}), 19)
        for actor in actors:
            for frames in actor["animations"].values():
                for frame in frames:
                    self.assertIn(f'{actor["prefix"]}{frame}0', sprites)
            for sound in actor["sound_resources"]:
                self.assertIn(sound, audio["sounds"])
            self.assertIn(actor["firing_sound"], audio["sounds"])
            slot = actor["weapon_slot"]
            self.assertEqual(slot, 2 if actor["height"] <= 54 else 3 if actor["height"] < 88 else 4)
            self.assertEqual(actor["pellets_per_shot"], 7 if slot == 3 else 1)
            state = actor["far_attack_state"]
            states = actor["attack_states"]
            self.assertEqual(states[str(state)]["action"], "FaceTarget")
            self.assertEqual(states[str(state + 1)]["action"], "PlaySound")
            shot = states[str(state + 2)]
            self.assertEqual(shot["action"], "MonsterBulletAttack")
            self.assertEqual(shot["args"], [368640, 0, actor["pellets_per_shot"], 5, 3])
            self.assertEqual(shot["next"], state + 3)
            self.assertEqual(states[str(state + 1)]["misc1"], {2: 8, 3: 2, 4: 548}[slot])
            fire = [row for row in states.values() if row["action"] == "MonsterBulletAttack"]
            self.assertEqual(len(fire), actor["rounds_per_burst"])
            self.assertEqual(len(fire), 6 if slot == 4 else 1)
            self.assertEqual(sum(row["tics"] for row in states.values()), actor["attack_chain_tics"])
            self.assertEqual(sum(actor["attack_tics"]), actor["attack_chain_tics"])
            self.assertAlmostEqual(actor["programmed_expected_damage_per_minute"],
                                   len(fire) * actor["pellets_per_shot"] * 10 * 2100
                                   / actor["attack_chain_tics"])
        for record in sprites.values():
            with Image.open(OUTPUT / record["path"]) as image:
                self.assertEqual(image.mode, "RGBA")
                self.assertEqual(image.size, (record["width"], record["height"]))
        for record in audio["sounds"].values():
            with wave.open(str(OUTPUT / record["path"]), "rb") as stream:
                self.assertEqual(stream.getparams()[:3], (1, 1, record["sample_rate"]))
                self.assertGreater(stream.getnframes(), 0)
        wad = dict(read_wad(CANDIDATE))
        presentation = self.load("Music/presentation.json")
        for cue in ("INTRO", "INTROA", "INTER", "VICTOR", "BUNNY"):
            record = presentation[cue]
            audio_track = next(track for track in audio["music"] if track["map"] == record["map"])
            for extension in ("ogg", "mid"):
                self.assertEqual(record[extension], audio_track[extension])
            for mode in ("D", "O", "H"):
                self.assertEqual(wad[f"{mode}_{cue}"], wad[f"{mode}_{record['map']}"])
        for track in audio["music"]:
            for mode in ("D", "O", "H"):
                self.assertEqual((OUTPUT / track["ogg"]).read_bytes(), wad[f'{mode}_{track["map"]}'])
            self.assertEqual(track["beats_per_bar"], 3 if track["map"] == "E1M7" else 4)
            self.assertFalse(track["commercial_samples"])
            self.assertFalse(track["third_party_compositions"])
            self.assertFalse(track["third_party_music_license_required"])
            self.assertFalse(track["third_party_music_royalties_required"])
            self.assertTrue(track["midi_programs"])

    def test_historical_music_cannot_be_mislabeled_as_current_export(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "export"
            with self.assertRaisesRegex(ValueError, "differs from the current soundtrack"):
                export(output, ROOT / "Toronto_Realms.wad")
            self.assertFalse(output.exists())

    def test_levels_cover_spawn_types_and_geometry_indices(self):
        levels = self.load("levels.json")
        self.assertEqual([level["id"] for level in levels], [f"E1M{i}" for i in range(1, 10)])
        npcs = {actor["doomednum"] for actor in self.load("npcs.json")}
        pickups = {int(key) for key in self.load("pickups.json")}
        decorations = {item["doomednum"] for item in self.load("decorations.json")}
        walkers = self.load("venue_walkers.json")
        walker_by_type = {item["doomednum"]: item for item in walkers["controllers"]}
        walker_types = set(walker_by_type)
        self.assertEqual(walker_types, {15402, 15403, 15404})
        self.assertEqual({kind for kind, item in walker_by_type.items()
                          if item["map"] == "E1M5"}, set())
        self.assertEqual({kind for kind, item in walker_by_type.items()
                          if item["map"] == "E1M6"}, {15402})
        self.assertEqual({kind for kind, item in walker_by_type.items()
                          if item["map"] == "E1M2"}, {15403})
        self.assertEqual({kind for kind, item in walker_by_type.items()
                          if item["map"] == "E1M3"}, {15404})
        inset = self.load("gameplay.json")["static_level_inset"]
        markers = set(inset["native_marker_types"])
        self.assertEqual(markers, set(range(15300, 15304)))
        for number in range(1, 10):
            with Image.open(OUTPUT / inset["images"][f"E1M{number}"]) as image:
                self.assertEqual(image.size, (86, 30))
        for entry in levels:
            level = self.load(entry["path"])
            self.assertEqual(
                {thing["type"] for thing in level["things"]} & walker_types,
                {kind for kind, item in walker_by_type.items()
                 if item["map"] == entry["id"]},
            )
            for line in level["lines"]:
                self.assertTrue(0 <= line["a"] < len(level["vertices"]))
                self.assertTrue(0 <= line["b"] < len(level["vertices"]))
                self.assertTrue(0 <= line["front"] < len(level["sides"]))
                self.assertTrue(line["back"] == -1 or 0 <= line["back"] < len(level["sides"]))
            for side in level["sides"]:
                self.assertTrue(0 <= side["sector"] < len(level["sectors"]))
            for thing in level["things"]:
                self.assertIn(thing["type"], npcs | pickups | decorations
                              | set(range(15100, 15109)) | markers | walker_types
                              # One-shot route tip messages: Tab map, objective,
                              # venue names and the spacebar exit advice.
                              | {15110, 15111, 15112} | set(range(15120, 15129))
                              | {15410, 15411})
            self.assertEqual(sum(thing["type"] == 15410 for thing in level["things"]), 1)
            self.assertEqual(sum(thing["type"] == 15411 for thing in level["things"]), 1)
            with Image.open(OUTPUT / level["map_image"]) as image:
                self.assertEqual(image.size, (1024, 768))

    def test_patch_decoder_preserves_transparency_and_offsets(self):
        payload = struct.pack("<4hI", 1, 2, -3, 5, 12) + bytes((1, 1, 0, 1, 0, 255))
        image, info = patch_image(payload, [0, 0, 0, 25, 50, 75])
        self.assertEqual(image.getpixel((0, 0)), (0, 0, 0, 0))
        self.assertEqual(image.getpixel((0, 1)), (25, 50, 75, 255))
        self.assertEqual((info["left_offset"], info["top_offset"]), (-3, 5))


if __name__ == "__main__":
    unittest.main()
