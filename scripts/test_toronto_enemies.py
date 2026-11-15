import re
import struct
import unittest
from pathlib import Path

from build_toronto_wad import MAPS, NPC_ANIMATIONS, NPC_ATTACK_SHEETS, _doom_palette, _weapon_tiles
import test_toronto_wad
from toronto_enemies import ALL_ENEMIES, SITE_ENEMIES, THIRD_ENEMIES, enemy_for


class SiteEnemyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_toronto_wad.NpcAnimationTests.setUpClass()
        cls.lumps = test_toronto_wad.NpcAnimationTests.lumps
        cls.patch = cls.lumps["DEHACKED"].decode("ascii")

    def fields(self, thing):
        blocks = re.findall(rf"^Thing {thing}\n(.*?)(?:\n\n)", self.patch, re.MULTILINE | re.DOTALL)
        self.assertEqual(len(blocks), 1)
        return {key: int(value) for key, value in re.findall(r"^(.+) = (-?\d+)$", blocks[0], re.MULTILINE)}

    def test_former_human_is_raccoon_and_coyote_is_not_embedded(self):
        self.assertEqual(NPC_ANIMATIONS[0][1], "npc_gunner_actions.png")
        self.assertFalse(any(filename == "npc_coyote_actions.png" for _, filename, *_ in NPC_ANIMATIONS))
        self.assertFalse(any(filename == "npc_raccoon_actions.png" for _, filename, *_ in NPC_ANIMATIONS))
        self.assertFalse(any(name.startswith("SARG") for name in self.lumps))
        self.assertNotRegex(self.patch, r"(?m)^Thing 13$")
        fields = self.fields(2)
        self.assertNotIn("Hit points", fields)
        self.assertNotIn("Far attack frame", fields)
        self.assertEqual(fields["Alert sound"], 43)
        self.assertEqual(fields["Pain sound"], 29)

    def test_each_map_spawns_only_its_own_specialist(self):
        from project_paths import ROOT
        data = (ROOT / "Toronto_Realms_three_map_backup.wad").read_bytes()
        _, count, offset = struct.unpack_from("<4sii", data)
        map_things = {}
        for index in range(count):
            _, _, name = struct.unpack_from("<ii8s", data, offset + index * 16)
            map_name = name.rstrip(b"\0").decode("ascii")
            if map_name in {spec["name"] for spec in MAPS}:
                start, size, _ = struct.unpack_from("<ii8s", data, offset + (index + 1) * 16)
                map_things[map_name] = [thing[3] for thing in struct.iter_unpack("<5h", data[start:start + size])]
        for spec, enemy in zip(MAPS, SITE_ENEMIES):
            self.assertEqual(spec["name"], enemy.map_name)
            self.assertGreaterEqual(len(spec["site_enemy"]), 2)
            types = map_things[spec["name"]]
            self.assertEqual(types.count(enemy.doomednum), len(spec["site_enemy"]))
            self.assertIn(3004, types)
            third = enemy_for(spec["name"], THIRD_ENEMIES)
            self.assertEqual(types.count(third.doomednum), len(spec["animal"]))
            self.assertNotIn(3002, types)
            self.assertFalse(any(other.doomednum in types for other in ALL_ENEMIES
                                 if other.map_name != spec["name"]))
        for enemy in ALL_ENEMIES:
            fields = self.fields(enemy.thing)
            self.assertEqual(fields["ID #"], enemy.doomednum)
            self.assertEqual(fields["Hit points"], enemy.health)
            self.assertEqual(fields["Width"], enemy.radius * 65536)
            self.assertEqual(fields["Height"], enemy.height * 65536)
            self.assertLessEqual(enemy.radius * 2, 128)
            self.assertLess(enemy.height, 128)
            self.assertEqual(fields["Bits"], 4194310)
            self.assertEqual(fields["Respawn frame"], 0)
            self.assertEqual(fields["Close attack frame"], 0)
            for name, value in (("Initial frame", 0), ("First moving frame", 2),
                                ("Far attack frame", 6), ("Injury frame", 9),
                                ("Death frame", 10), ("Exploding frame", 10)):
                self.assertEqual(fields[name], enemy.state + value)

    def test_state_graphs_and_sound_routing_are_complete(self):
        slots = set()
        for enemy in ALL_ENEMIES:
            fields = self.fields(enemy.thing)
            self.assertIn(f"{enemy.sprite} = {enemy.prefix}", self.patch)
            for name, value in zip(("Alert sound", "Pain sound", "Death sound", "Action sound"), enemy.sounds):
                self.assertEqual(fields[name], value)
                self.assertNotIn(value, slots)
                slots.add(value)
            for index in range(16):
                state = enemy.state + index
                block = re.search(rf"^Frame {state}\n(.*?)\n\n", self.patch, re.MULTILINE | re.DOTALL)[1]
                values = dict(re.findall(r"^(.+) = (-?\d+)$", block, re.MULTILINE))
                self.assertEqual(int(values["Sprite number"]), enemy.sprite)
                next_state = int(values["Next frame"])
                self.assertTrue(next_state == 0 or enemy.state <= next_state < enemy.state + 16)
                self.assertRegex(self.patch, rf"(?m)^FRAME {state} = \w+$")
                if index == 7:
                    self.assertIn(f"FRAME {state} = {enemy.attack}", self.patch)
                if index in (6, 7, 8):
                    self.assertEqual(int(values["Duration"]), enemy.attack_tics[index - 6])
                if index == 15:
                    self.assertEqual(int(values["Duration"]), -1)
            self.assertEqual(len({self.lumps[f"{enemy.prefix}{chr(65+i)}0"] for i in range(16)}), 16)

    def test_new_rivals_have_distinct_combat_roles(self):
        pigeon, armour, wolf = THIRD_ENEMIES
        self.assertLess(sum(pigeon.attack_tics), sum(wolf.attack_tics))
        self.assertLess(sum(wolf.attack_tics), sum(armour.attack_tics))
        self.assertGreater(wolf.speed, pigeon.speed)
        self.assertGreater(pigeon.speed, armour.speed)
        self.assertGreater(armour.health, max(enemy.health for enemy in ALL_ENEMIES if enemy != armour))
        self.assertEqual((pigeon.attack, wolf.attack, armour.attack), ("PosAttack", "PosAttack", "SPosAttack"))

    def test_all_actors_use_dedicated_front_aim_attack_sources(self):
        prefixes = []
        for filename, rows in NPC_ATTACK_SHEETS:
            tiles = _weapon_tiles(filename, 3, 4)
            for row, prefix in enumerate(rows):
                prefixes.append(prefix)
                self.assertEqual(len({tile.tobytes() for tile in tiles[row * 3:row * 3 + 3]}), 3)
                for letter in ("EF" if prefix == "POSS" else "EFG"):
                    self.assertTrue(test_toronto_wad.NpcAnimationTests.silhouette(self.lumps[f"{prefix}{letter}0"]))
        self.assertCountEqual(prefixes, [prefix for prefix, *_ in NPC_ANIMATIONS])

    def test_pigeon_does_not_stand_back_up_during_settling(self):
        heights = []
        for letter in "LMN":
            pixels = test_toronto_wad.NpcAnimationTests.silhouette(self.lumps[f"PIGE{letter}0"])
            heights.append(max(y for _, y in pixels) - min(y for _, y in pixels) + 1)
        self.assertLessEqual(heights[1], heights[0] + 2)
        self.assertLessEqual(heights[2], heights[1] + 2)

    def test_large_markers_remain_visible_in_idle_attack_and_defeat(self):
        palette = _doom_palette()
        for prefix in ("DINO", "BEAR"):
            for letter in ("O", "E", "F", "N"):
                with self.subTest(prefix=prefix, frame=letter):
                    data = self.lumps[f"{prefix}{letter}0"]
                    width, height = struct.unpack_from("<2h", data)
                    colored = []
                    for x in range(width):
                        cursor = struct.unpack_from("<I", data, 8 + x * 4)[0]
                        while data[cursor] != 255:
                            y, size = data[cursor:cursor + 2]
                            for dy in range(size):
                                index = data[cursor + 3 + dy]
                                r, g, b = palette[index * 3:index * 3 + 3]
                                if (prefix == "BEAR" and r > 140 and g > 90 and b < r * 0.6
                                        or prefix == "DINO" and
                                        (b > r * 1.2 and b > g * 1.1
                                         or r > 140 and g > 70 and b < r * 0.6)):
                                    colored.append((x, y + dy))
                            cursor += size + 4
                    self.assertGreater(len(colored), 20)
                    span = max(x for x, _ in colored) - min(x for x, _ in colored) + 1
                    self.assertGreater(span, width * 0.20)


if __name__ == "__main__":
    unittest.main()
