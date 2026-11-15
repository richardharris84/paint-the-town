import struct
import unittest
import json
from tempfile import TemporaryDirectory
from pathlib import Path

from build_expansion import CANDIDATE
from doom_geometry import read_wad
from level_inset import MARKER_DOOMEDNUM, MARKER_ITEMS, image, selector
from toronto_venues import venue_specs


class LevelInsetTests(unittest.TestCase):
    def test_north_arrow_is_a_bold_connected_silhouette(self):
        plan = image(venue_specs()[0])
        pixels = {(x, y) for y in range(10) for x in range(76, 86)
                  if plan.getpixel((x, y))[:3] == (255, 239, 183)}
        self.assertGreater(len(pixels), 20)
        pending = [next(iter(pixels))]
        reached = set()
        while pending:
            x, y = pending.pop()
            if (x, y) not in pixels or (x, y) in reached:
                continue
            reached.add((x, y))
            pending.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))
        self.assertEqual(reached, pixels)

    def test_native_hud_wiring_and_non_counting_markers(self):
        assets = dict(read_wad(CANDIDATE))
        hud = json.loads(assets["SBARDEF"])
        bars = hud["data"]["statusbars"]
        for children in (bars[0]["children"], bars[1]["children"][0]["canvas"]["children"]):
            graphics = [child["graphic"] for child in children if "graphic" in child]
            plans = [g for g in graphics if g["patch"].startswith("TRMAP")]
            self.assertEqual(len(plans), 9)
            for level, graphic in enumerate(plans, 1):
                self.assertEqual(graphic["patch"], f"TRMAP{level}")
                self.assertEqual(graphic["conditions"], selector(level))
            keys = {g["patch"] for g in graphics if g["patch"].startswith("STKEYS")}
            self.assertEqual(keys, {"STKEYS0", "STKEYS3"})
        from level_inset import gameplay_patch
        patch = gameplay_patch()
        self.assertEqual(patch.count("Bits = 1\n"), 4)
        self.assertEqual(patch.count("Pickup bonus count = 0\n"), 4)
        self.assertEqual(patch.count("Pickup sound = 0\n"), 4)

    def test_exactly_one_selection_for_each_level(self):
        self.assertEqual(MARKER_ITEMS, (2, 3, 5, 6))
        for level in range(1, 10):
            owned = {item for bit, item in enumerate(MARKER_ITEMS) if level & (1 << bit)}
            matches = [number for number in range(1, 10)
                       if all((c["param"] in owned) == (c["condition"] == 10)
                              for c in selector(number))]
            self.assertEqual(matches, [level])
        self.assertFalse(any(all(c["condition"] == 10 for c in selector(n))
                             for n in range(1, 10)), "All-keys cheat must not display a wrong map")

    def test_distinct_plans_and_spawn_markers(self):
        lumps = read_wad(CANDIDATE)
        plans = set()
        for level, spec in enumerate(venue_specs(), 1):
            plan = image(spec)
            self.assertEqual(plan.size, (86, 30))
            plans.add(plan.tobytes())
            index = next(i for i, (name, _) in enumerate(lumps) if name == spec.name)
            things = list(struct.iter_unpack("<5h", lumps[index + 1][1]))
            actual = [t for t in things if MARKER_DOOMEDNUM <= t[3] < MARKER_DOOMEDNUM + 4]
            start = next(t for t in things if t[3] == 1)
            expected = [(start[0], start[1], 0, MARKER_DOOMEDNUM + bit, 7)
                        for bit in range(4) if level & (1 << bit)]
            self.assertEqual(actual, expected)
        self.assertEqual(len(plans), 9)

    def test_checkpoint_fixture_starts_are_clear_and_keep_map_markers(self):
        from verify_expansion_checkpoints import build_fixture
        with TemporaryDirectory() as directory:
            lumps = read_wad(build_fixture(Path(directory) / "checkpoints.wad"))
        for level, spec in enumerate(venue_specs(), 1):
            index = next(i for i, (name, _) in enumerate(lumps) if name == spec.name)
            things = list(struct.iter_unpack("<5h", lumps[index + 1][1]))
            start = next(t for t in things if t[3] == 1)
            self.assertTrue(spec.compile().clear_at(start[0], start[1], 24))
            markers = [t for t in things if MARKER_DOOMEDNUM <= t[3] < MARKER_DOOMEDNUM + 4]
            self.assertEqual(len(markers), level.bit_count())
            self.assertTrue(all(t[:2] == start[:2] for t in markers))


if __name__ == "__main__":
    unittest.main()
