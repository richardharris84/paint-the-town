import math
import re
import struct
import unittest
from pathlib import Path

from paintball_audio import SAMPLE_RATE, SOUND_SPECS, sound_lumps, synthesize_sound
from toronto_enemies import ALL_ENEMIES


NPC_GROUPS = (("POSS", 23), *((enemy.prefix, 16) for enemy in ALL_ENEMIES))


class NpcAnimationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from project_paths import ROOT
        data = (ROOT / "Toronto_Realms_three_map_backup.wad").read_bytes()
        signature, count, offset = struct.unpack_from("<4sii", data)
        if signature != b"PWAD" or offset + count * 16 != len(data):
            raise ValueError("Expected a built PWAD with a standard directory")
        cls.lumps = {}
        for index in range(count):
            start, size, name = struct.unpack_from("<ii8s", data, offset + index * 16)
            cls.lumps[name.rstrip(b"\0").decode("ascii")] = data[start:start + size]

    def frames(self, prefix, count):
        return [self.lumps[f"{prefix}{chr(65 + index)}0"] for index in range(count)]

    @staticmethod
    def silhouette(patch):
        width, height = struct.unpack_from("<2h", patch)
        pixels = set()
        for x in range(width):
            cursor = struct.unpack_from("<I", patch, 8 + x * 4)[0]
            while patch[cursor] != 255:
                top, length = patch[cursor:cursor + 2]
                if top + length > height:
                    raise ValueError("Sprite post extends beyond the patch")
                pixels.update((x, y) for y in range(top, top + length))
                cursor += length + 4
        return pixels

    def test_all_119_frames_are_distinct(self):
        for prefix, count in NPC_GROUPS:
            with self.subTest(prefix=prefix):
                frames = self.frames(prefix, count)
                self.assertEqual(len(set(frames)), count)

    def test_shared_dimensions_and_ground_anchor(self):
        for prefix, count in NPC_GROUPS:
            with self.subTest(prefix=prefix):
                frames = self.frames(prefix, count)
                headers = {struct.unpack_from("<4h", patch) for patch in frames}
                self.assertEqual(len(headers), 1)
                width, height, left, top = headers.pop()
                self.assertEqual(left, width // 2)
                self.assertEqual(top, height - 2)
                for patch in frames:
                    pixels = self.silhouette(patch)
                    self.assertTrue(pixels)
                    self.assertLess(max(y for _, y in pixels), height - 1)
                    self.assertGreater(min(y for _, y in pixels), 0)

    def test_npc_threat_tiers_increase_size_without_changing_combat_stats(self):
        patch = self.lumps["DEHACKED"].decode("ascii")
        previous_height = 0
        previous_area = 0
        sizes = [("POSS", 2, 56, 20)] + [
            (enemy.prefix, enemy.thing, enemy.height, enemy.radius)
            for enemy in sorted(ALL_ENEMIES, key=lambda enemy: enemy.height)
        ]
        for prefix, thing, height, radius in sizes:
            with self.subTest(prefix=prefix):
                walk = [self.silhouette(self.lumps[f"{prefix}{letter}0"]) for letter in "ABCD"]
                visible_height = max(max(y for _, y in pixels) - min(y for _, y in pixels) + 1
                                     for pixels in walk)
                area = max(len(pixels) for pixels in walk)
                self.assertAlmostEqual(visible_height, height, delta=2)
                self.assertGreater(visible_height, previous_height)
                self.assertGreater(area, 300)
                previous_height, previous_area = visible_height, area
                match = re.search(rf"^Thing {thing}\n(.*?)(?:\n\n)", patch, re.MULTILINE | re.DOTALL)
                self.assertIsNotNone(match)
                fields = dict(re.findall(r"^(.+) = (\d+)$", match[1], re.MULTILINE))
                self.assertEqual(int(fields["Width"]), radius * 65536)
                self.assertEqual(int(fields["Height"]), height * 65536)
                if prefix == "POSS":
                    self.assertNotIn("Hit points", fields)
                    self.assertNotIn("Missile damage", fields)
                    self.assertNotIn("Speed", fields)

    def test_resized_actors_fit_passages_and_do_not_overlap_at_spawn(self):
        for map_name in ("E1M1", "E1M2", "E1M3"):
            # Map THINGS is scoped by map marker rather than the last duplicate lump.
            from project_paths import ROOT
            data = (ROOT / "Toronto_Realms_three_map_backup.wad").read_bytes()
            _, count, offset = struct.unpack_from("<4sii", data)
            for index in range(count):
                _, _, name = struct.unpack_from("<ii8s", data, offset + index * 16)
                if name.rstrip(b"\0").decode("ascii") == map_name:
                    start, size, _ = struct.unpack_from("<ii8s", data, offset + (index + 1) * 16)
                    things = list(struct.iter_unpack("<5h", data[start:start + size]))
                    break
            else:
                self.fail(f"Missing map: {map_name}")
            radii = {1: 16, 3004: 20,
                     **{enemy.doomednum: enemy.radius for enemy in ALL_ENEMIES}}
            solid = [(x, y, radii[kind]) for x, y, _, kind, _ in things if kind in radii]
            for i, (x, y, radius) in enumerate(solid):
                self.assertLess(radius * 2, 128)
                for other_x, other_y, other_radius in solid[i + 1:]:
                    self.assertTrue(
                        abs(x - other_x) >= radius + other_radius
                        or abs(y - other_y) >= radius + other_radius,
                        f"{map_name}: resized solid actors overlap at spawn",
                    )

    def test_defeat_finishes_low_and_horizontal(self):
        for prefix, last in (("POSS", "L"), *((enemy.prefix, "N") for enemy in ALL_ENEMIES)):
            with self.subTest(prefix=prefix):
                standing = self.silhouette(self.lumps[f"{prefix}A0"])
                resting = self.silhouette(self.lumps[f"{prefix}{last}0"])
                standing_height = max(y for _, y in standing) - min(y for _, y in standing) + 1
                resting_height = max(y for _, y in resting) - min(y for _, y in resting) + 1
                resting_width = max(x for x, _ in resting) - min(x for x, _ in resting) + 1
                self.assertLess(resting_height, standing_height * 0.6)
                self.assertGreater(resting_width, resting_height * 1.5)

    def test_exaggerated_knockout_has_nine_distinct_frames(self):
        for prefix in ("POSS",):
            with self.subTest(prefix=prefix):
                frames = [self.lumps[f"{prefix}{letter}0"] for letter in "MNOPQRSTU"]
                self.assertEqual(len(set(frames)), 9)
                pixels = self.silhouette(frames[-1])
                self.assertLess(max(y for _, y in pixels) - min(y for _, y in pixels), 40)

    def test_stock_npc_frame_changes_are_limited_to_two_idle_states(self):
        patch = self.lumps["DEHACKED"].decode("ascii")
        entries = re.findall(r"Frame (\d+)\nSprite subnumber = (\d+)", patch)
        entries = [(state, frame) for state, frame in entries if 100 <= int(state) < 1000]
        self.assertEqual(
            entries,
            [("174", "21"), ("175", "22")],
        )
        states = {int(state) for state in re.findall(r"^Frame (\d+)", patch, re.MULTILINE)}
        expected = {174, 175, 15, 16, 17, 1200, 1201}
        expected.update(enemy.state + n for enemy in ALL_ENEMIES for n in range(16))
        self.assertEqual(states, expected)
        self.assertIn("Patch format = 6", patch)
        for prefix, letters in (("POSS", "VW"), *((enemy.prefix, "OP") for enemy in ALL_ENEMIES)):
            for letter in letters:
                self.assertIn(f"{prefix}{letter}0", self.lumps)

    def test_all_used_weapon_frames_are_replaced(self):
        groups = (("PISG", 5), ("SHTG", 5), ("CHGG", 2),
                  ("PISF", 1), ("SHTF", 2), ("CHGF", 2))
        for prefix, count in groups:
            for frame in range(count):
                with self.subTest(prefix=prefix, frame=frame):
                    patch = self.lumps[f"{prefix}{chr(65 + frame)}0"]
                    width, height, left, top = struct.unpack_from("<4h", patch)
                    self.assertLess(left, 0)
                    self.assertLess(top, 0)
                    self.assertTrue(self.silhouette(patch))
                    if prefix.endswith("G"):
                        self.assertEqual((width, height, left, top), (160, 144, -80, -24))
                        self.assertLessEqual(-left + width, 320)
                        self.assertEqual(32 - top + height, 200)

    def test_weapon_actions_have_different_art(self):
        for prefix, letters in (("PISG", "ABCDE"), ("SHTG", "ABCD"), ("CHGG", "AB")):
            with self.subTest(prefix=prefix):
                patches = [self.lumps[f"{prefix}{letter}0"] for letter in letters]
                self.assertEqual(len(set(patches)), len(letters))

    def test_starter_sound_and_recoil_are_isolated_from_other_weapons(self):
        patch = self.lumps["DEHACKED"].decode("ascii")
        self.assertIn("Frame 15\nDuration = 2\nNext frame = 1201\n", patch)
        self.assertIn("Frame 1201\nSprite number = 3\nSprite subnumber = 3\n"
                      "Duration = 2\nNext frame = 16\n", patch)
        self.assertIn("Frame 16\nSprite subnumber = 4\n", patch)
        self.assertIn("Frame 17\nDuration = 0\nNext frame = 1200\nArgs1 = 8\nArgs2 = 0\n", patch)
        self.assertIn("Frame 1200\nSprite number = 4\nSprite subnumber = 32768\n"
                      "Duration = 7\nNext frame = 1\n", patch)
        self.assertEqual([(n, action) for n, action in re.findall(r"^FRAME (\d+) = (\w+)$", patch, re.MULTILINE)
                          if int(n) < 1300],
                         [("17", "WeaponSound"), ("1200", "Light1"), ("1201", "NULL")])
        self.assertNotEqual(self.lumps["DSPLASMA"], self.lumps["DSPISTOL"])
        self.assertEqual(self.lumps["DSPISTOL"], synthesize_sound("marker", 0.18, 1))
        self.assertEqual(self.lumps["DSSHOTGN"], synthesize_sound("scatter", 0.24, 2))
        self.assertEqual(self.lumps["DSSGCOCK"], synthesize_sound("pump", 0.26, 4))

    def test_stronger_weapons_have_larger_visible_silhouettes(self):
        bounds = []
        areas = []
        for prefix in ("PISG", "SHTG", "CHGG"):
            pixels = self.silhouette(self.lumps[f"{prefix}A0"])
            width = max(x for x, _ in pixels) - min(x for x, _ in pixels) + 1
            height = max(y for _, y in pixels) - min(y for _, y in pixels) + 1
            bounds.append((width, height))
            areas.append(len(pixels))
        for index in (1, 2):
            with self.subTest(tier=index):
                self.assertGreater(bounds[index][0], bounds[index - 1][0])
                self.assertGreater(bounds[index][1], bounds[index - 1][1])
                self.assertGreater(areas[index], areas[index - 1] * 1.25)
        shotgun_width = struct.unpack_from("<h", self.lumps["SHOTA0"])[0]
        automatic_width = struct.unpack_from("<h", self.lumps["MGUNA0"])[0]
        self.assertGreater(automatic_width, shotgun_width * 1.25)

    def test_weapons_and_paint_bursts_leave_the_aiming_area_clear(self):
        groups = (("PISG", 5), ("SHTG", 5), ("CHGG", 2),
                  ("PISF", 1), ("SHTF", 2), ("CHGF", 2))
        for prefix, count in groups:
            for frame in range(count):
                with self.subTest(prefix=prefix, frame=frame):
                    patch = self.lumps[f"{prefix}{chr(65 + frame)}0"]
                    _, _, left, top = struct.unpack_from("<4h", patch)
                    pixels = self.silhouette(patch)
                    # The crosshair can be at y=84 (status bar) or y=100 (fullscreen).
                    # All opaque weapon/effect pixels must remain below both centers.
                    self.assertGreaterEqual(min(32 - top + y for _, y in pixels), 112)
                    self.assertFalse(any(
                        140 <= -left + x <= 180 and 72 <= 32 - top + y <= 112
                        for x, y in pixels
                    ))

    def test_forearms_reach_status_bar_and_fullscreen_bottom(self):
        for prefix, count in (("PISG", 5), ("SHTG", 5), ("CHGG", 2)):
            for frame in range(count):
                with self.subTest(prefix=prefix, frame=frame):
                    patch = self.lumps[f"{prefix}{chr(65 + frame)}0"]
                    _, height, _, top = struct.unpack_from("<4h", patch)
                    pixels = self.silhouette(patch)
                    self.assertEqual(32 - top + height, 200)
                    for y in range(111, height):
                        row = {x for x, py in pixels if py == y}
                        self.assertTrue(any(x < 80 for x in row), "Left sleeve ends above screen bottom")
                        self.assertTrue(any(x > 80 for x in row), "Right sleeve ends above screen bottom")

    def test_gun_and_ammunition_pickups_are_replaced(self):
        for name in ("SHOTA0", "MGUNA0", "CLIPA0", "AMMOA0", "SHELA0", "SBOXA0"):
            with self.subTest(name=name):
                patch = self.lumps[name]
                width, height, left, top = struct.unpack_from("<4h", patch)
                self.assertEqual((left, top), (width // 2, height))
                self.assertTrue(self.silhouette(patch))

    def test_dmx_audio_is_padded_audible_and_not_clipped(self):
        for name, _, duration, _ in SOUND_SPECS:
            with self.subTest(name=name):
                data = self.lumps[name]
                encoding, rate, count = struct.unpack_from("<HHI", data)
                self.assertEqual((encoding, rate, count), (3, SAMPLE_RATE, len(data) - 8))
                self.assertEqual(data[8:24], bytes([128]) * 16)
                self.assertEqual(data[-16:], bytes([128]) * 16)
                pcm = data[24:-16]
                self.assertEqual(len(pcm), round(duration * SAMPLE_RATE))
                self.assertGreater(min(pcm), 0)
                self.assertLess(max(pcm), 255)
                self.assertLess(abs(pcm[0] - 128), 2)
                self.assertLess(abs(pcm[-1] - 128), 3)
                rms = math.sqrt(sum((value - 128) ** 2 for value in pcm) / len(pcm))
                self.assertGreater(rms, 5)
                self.assertLess(rms, 60)
                self.assertLess(abs(sum(pcm) / len(pcm) - 128), 8)

    def test_npc_sound_assignments_are_species_specific(self):
        patch = self.lumps["DEHACKED"].decode("ascii")
        for thing, alert, pain, death, active in ((2, 43, 29, 66, 77),):
            with self.subTest(thing=thing):
                match = re.search(rf"^Thing {thing}\n(.*?)(?:\n\n)", patch, re.MULTILINE | re.DOTALL)
                self.assertIsNotNone(match)
                fields = dict(re.findall(r"^(.+) = (\d+)$", match[1], re.MULTILINE))
                self.assertEqual({key: value for key, value in fields.items()
                                  if key not in ("Width", "Height")}, {
                    "Alert sound": str(alert), "Pain sound": str(pain),
                    "Death sound": str(death), "Action sound": str(active),
                })
                self.assertNotIn(alert, (36, 37, 38, 39, 40))
                self.assertNotIn(death, (59, 60, 61, 62, 63))
        self.assertNotEqual(self.lumps["DSVIPAIN"], self.lumps["DSMNPAIN"])
        self.assertNotEqual(self.lumps["DSPISTOL"], self.lumps["DSSHOTGN"])
        self.assertIn("GOTSHOTGUN = You got the pump paintball marker!", patch)
        self.assertIn("GOTCLIP = Picked up a paintball pod.", patch)

    def test_sound_build_is_reproducible(self):
        for name, data in sound_lumps():
            with self.subTest(name=name):
                self.assertEqual(data, self.lumps[name])

    def test_unknown_sound_is_an_explicit_error(self):
        with self.assertRaisesRegex(ValueError, "Unknown paintball sound kind"):
            synthesize_sound("unknown", 0.1, 1)


if __name__ == "__main__":
    unittest.main()
