import re
import struct
import unittest

from PIL import Image

from expansion_cast import CAMPAIGN_ENEMIES
from npc_weapons import (
    ATTACK_STRIDE, ATTACK_TIERS, attack_start, attack_lumps, marker_receiver,
    weapon_slot, weapon_sounds,
)


class NpcWeaponTests(unittest.TestCase):
    def test_height_boundaries(self):
        self.assertEqual([weapon_slot(h) for h in (30, 54, 55, 87, 88, 128)], [2, 2, 3, 3, 4, 4])

    def test_all_nineteen_native_attack_graphs(self):
        patch = attack_lumps(CAMPAIGN_ENEMIES).decode("ascii")
        self.assertEqual(len(re.findall(r"^Thing \d+$", patch, re.M)), 19)
        frames = {int(number): body for number, body in
                  re.findall(r"Frame (\d+)\n(.*?)(?:\n\n)", patch, re.S)}
        self.assertEqual(len(frames), len(re.findall(r"^Frame \d+$", patch, re.M)))
        for index, height in enumerate([56] + [e.height for e in CAMPAIGN_ENEMIES]):
            start = attack_start(index)
            slot = weapon_slot(height)
            tier = ATTACK_TIERS[slot]
            final = start + tier.rounds * 2 + 1
            self.assertLess(final, start + ATTACK_STRIDE)
            actions = ["FaceTarget", *["PlaySound", "MonsterBulletAttack"] * tier.rounds,
                       "FaceTarget"]
            for offset, action in enumerate(actions):
                self.assertIn(f"FRAME {start + offset} = {action}", patch)
                if start + offset != final:
                    self.assertIn(f"Next frame = {start + offset + 1}", frames[start + offset])
            for shot in range(tier.rounds):
                sound = frames[start + 1 + shot * 2]
                fire = frames[start + 2 + shot * 2]
                self.assertIn(f"Unknown 1 = {tier.sound}", sound)
                self.assertIn(f"Args3 = {tier.pellets}", fire)
                self.assertIn("Args4 = 5", fire)
                self.assertIn("Args5 = 3", fire)
                self.assertIn(f"Duration = {tier.shot_tics}", fire)
            self.assertIn(f"Duration = {tier.recovery_tics}", frames[final])
            actor = 2 if index == 0 else CAMPAIGN_ENEMIES[index - 1].thing
            chase = 176 if index == 0 else CAMPAIGN_ENEMIES[index - 1].state + 2
            self.assertIn(f"Thing {actor}\nFar attack frame = {start}", patch)
            self.assertIn(f"Next frame = {chase}", frames[final])
        self.assertIn("Sprite number = 29", frames[2600])
        self.assertIn("Next frame = 176", frames[2603])

    def test_programmed_tier_damage_increases_with_size(self):
        small, medium, large = (ATTACK_TIERS[slot] for slot in (2, 3, 4))
        self.assertGreaterEqual(large.rounds, 4)
        self.assertGreater(large.expected_damage_per_minute, medium.expected_damage_per_minute)
        self.assertGreater(medium.expected_damage_per_minute, small.expected_damage_per_minute)
        for tier in (small, medium, large):
            self.assertAlmostEqual(tier.expected_damage_per_minute,
                                   tier.pellets * tier.rounds * 10 * 2100 / tier.chain_tics)

    def test_automatic_has_a_dedicated_nonlinked_sound(self):
        sounds = dict(weapon_sounds())
        self.assertEqual(set(sounds), {"DSFRE048"})
        payload = sounds["DSFRE048"]
        format_id, rate, count = struct.unpack_from("<HHI", payload)
        self.assertEqual((format_id, rate), (3, 11025))
        self.assertEqual(len(payload), count + 8)
        self.assertGreater(count, 32)
        self.assertGreater(len(set(payload[24:-16])), 1)

    def test_each_species_has_distinct_idle_and_firing_receiver_art(self):
        for prefix, height in [("POSS", 56)] + [(e.prefix, e.height) for e in CAMPAIGN_ENEMIES]:
            with self.subTest(prefix=prefix):
                source = Image.new("RGBA", (height, height), (90, 90, 90, 255))
                idle = marker_receiver(source.copy(), prefix, height)
                firing = marker_receiver(source.copy(), prefix, height, firing=True)
                self.assertNotEqual(source.tobytes(), idle.tobytes())
                self.assertNotEqual(idle.tobytes(), firing.tobytes())
                self.assertEqual(source.getbbox(), firing.getbbox())


if __name__ == "__main__":
    unittest.main()
