import re
import unittest

from build_toronto_wad import (
    NPC_ANIMATIONS, NPC_ATTACK_SHEETS, NPC_SIZES,
    _animation_patch, _npc_sprite_canvases, _sprite_patch,
)
from expansion_cast import (
    CAMPAIGN_ENEMIES, NEW_ANIMATIONS, NEW_ATTACK_SHEETS, NEW_ENEMIES, map_enemies,
)


class ExpansionCastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.animations = NPC_ANIMATIONS + NEW_ANIMATIONS
        sizes = {**NPC_SIZES, **{e.prefix: (e.thing, e.height, e.radius) for e in CAMPAIGN_ENEMIES}}
        cls.sprites = _npc_sprite_canvases(cls.animations, sizes, NPC_ATTACK_SHEETS + NEW_ATTACK_SHEETS,
                                         campaign_weapons=True)
        cls.patch = _animation_patch(cls.animations, CAMPAIGN_ENEMIES, sizes).decode("ascii")

    def test_species_scale_matches_collision_and_dinosaur_exceeds_armour(self):
        sizes = {e.prefix: e.height for e in CAMPAIGN_ENEMIES}
        self.assertGreaterEqual(sizes["DINO"], sizes["ARMR"] * 1.35)
        self.assertGreater(sizes["BEAR"], sizes["WOLF"])
        self.assertEqual(sizes["WOLF"], 48)
        health = {e.prefix: e.health for e in CAMPAIGN_ENEMIES}
        self.assertEqual(health["DINO"], health["BEAR"])
        self.assertEqual(health["DINO"], 180)
        self.assertGreater(sizes["STAG"], sizes["BLSQ"] * 2)
        self.assertLess(sizes["CHIP"], sizes["GOOS"])
        for prefix, height in sizes.items():
            with self.subTest(actor=prefix):
                walk = self.sprites[prefix][:4]
                actual = max(self.bounds(f)[3] - self.bounds(f)[1] for f in walk)
                self.assertAlmostEqual(actual, height, delta=2)

    @staticmethod
    def bounds(frame):
        points = [(x, y) for y, row in enumerate(frame) for x, pixel in enumerate(row) if pixel is not None]
        if not points:
            raise ValueError("Empty sprite silhouette")
        return (min(x for x, _ in points), min(y for _, y in points),
                max(x for x, _ in points) + 1, max(y for _, y in points) + 1)

    def test_nineteen_types_and_exactly_two_exclusive_rivals_per_venue(self):
        self.assertEqual(len(self.sprites), 19)
        self.assertEqual(len(NEW_ENEMIES), 12)
        for i in range(1, 10):
            self.assertEqual(len(map_enemies(f"E1M{i}")), 2)
        for attribute in ("thing", "doomednum", "sprite", "prefix"):
            self.assertEqual(len({getattr(e, attribute) for e in CAMPAIGN_ENEMIES}), 18)
        states = [state for e in CAMPAIGN_ENEMIES for state in range(e.state, e.state + 16)]
        self.assertEqual(len(set(states)), 18 * 16)
        self.assertFalse(set(states) & {1200, 1201})
        self.assertEqual([slot for e in NEW_ENEMIES for slot in e.sounds], list(range(500, 548)))

    def test_all_new_animation_frames_are_distinct_nonempty_and_grounded(self):
        for enemy in NEW_ENEMIES:
            with self.subTest(actor=enemy.prefix):
                frames = self.sprites[enemy.prefix]
                self.assertEqual(len(set(_sprite_patch(f) for f in frames)), 16)
                dimensions = {(len(f[0]), len(f)) for f in frames}
                self.assertEqual(len(dimensions), 1)
                width, height = dimensions.pop()
                for frame in frames:
                    x0, y0, x1, y1 = self.bounds(frame)
                    self.assertGreaterEqual(x0, 1)
                    self.assertLess(x1, width)
                    self.assertGreaterEqual(y0, 1)
                    self.assertEqual(y1, height - 2)
                walk_height = max(self.bounds(f)[3] - self.bounds(f)[1] for f in frames[:4])
                self.assertAlmostEqual(walk_height, enemy.height, delta=2)
                for frame in frames[4:7] + frames[14:16]:
                    bounds = self.bounds(frame)
                    self.assertAlmostEqual(bounds[3] - bounds[1], enemy.height, delta=4)

    def test_intact_defeats_end_low_horizontal_without_a_standing_return(self):
        for enemy in NEW_ENEMIES:
            frames = self.sprites[enemy.prefix]
            with self.subTest(actor=enemy.prefix):
                x0, y0, x1, y1 = self.bounds(frames[13])
                self.assertLess(y1 - y0, enemy.height * 0.6)
                self.assertGreater(x1 - x0, (y1 - y0) * 1.5)
                heights = [self.bounds(f)[3] - self.bounds(f)[1] for f in frames[11:14]]
                self.assertLess(heights[0], enemy.height * 0.8)
                self.assertLessEqual(heights[1], heights[0] + 2)
                self.assertLessEqual(heights[2], heights[1] + 2)

    def test_each_new_actor_has_complete_state_graph_and_dedicated_front_attack(self):
        prefixes = [prefix for _, group in NEW_ATTACK_SHEETS for prefix in group]
        self.assertCountEqual(prefixes, [e.prefix for e in NEW_ENEMIES])
        for enemy in NEW_ENEMIES:
            with self.subTest(actor=enemy.prefix):
                self.assertIn(f"{enemy.sprite} = {enemy.prefix}", self.patch)
                self.assertEqual(len(re.findall(rf"(?m)^Thing {enemy.thing}$", self.patch)), 1)
                for state in range(enemy.state, enemy.state + 16):
                    self.assertRegex(self.patch, rf"(?m)^Frame {state}$")
                    self.assertRegex(self.patch, rf"(?m)^FRAME {state} = \w+$")
                self.assertIn(f"FRAME {enemy.state + 7} = {enemy.attack}", self.patch)
                self.assertLessEqual(enemy.radius, 34)
                self.assertEqual(enemy.attack_tics, tuple(int(value) for value in enemy.attack_tics))


if __name__ == "__main__":
    unittest.main()
