import re
import struct
import unittest
from pathlib import Path

from build_toronto_wad import MAPS, _doom_iwad
from toronto_materials import MAP_SKIES, WALL_SAMPLES, FLAT_SAMPLES, texture_records, zone_for


class TorontoMaterialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from project_paths import ROOT
        data = (ROOT / "Toronto_Realms_three_map_backup.wad").read_bytes()
        _, count, offset = struct.unpack_from("<4sii", data)
        cls.entries = []
        for index in range(count):
            start, size, name = struct.unpack_from("<ii8s", data, offset + index * 16)
            cls.entries.append((name.rstrip(b"\0").decode("ascii"), data[start:start + size]))
        cls.lumps = dict(cls.entries)
        cls.iwad = _doom_iwad()

    @staticmethod
    def patch_pixels(data):
        width, height, left, top = struct.unpack_from("<4h", data)
        if (left, top) != (0, 0):
            raise ValueError("Material patch must have zero offsets")
        pixels = [[None] * width for _ in range(height)]
        for x in range(width):
            cursor = struct.unpack_from("<I", data, 8 + x * 4)[0]
            while data[cursor] != 255:
                y, size = data[cursor:cursor + 2]
                for dy in range(size):
                    pixels[y + dy][x] = data[cursor + 3 + dy]
                cursor += size + 4
        if any(value is None for row in pixels for value in row):
            raise ValueError("A wall or sky contains transparent holes")
        return width, height, pixels

    def test_original_texture_and_patch_indices_are_preserved(self):
        original_pnames = self.iwad["PNAMES"]
        count = struct.unpack_from("<i", original_pnames)[0]
        self.assertEqual(self.lumps["PNAMES"][4:4 + count * 8], original_pnames[4:])
        original = texture_records(self.iwad["TEXTURE1"])
        current = texture_records(self.lumps["TEXTURE1"])
        self.assertEqual(current[:len(original)], original)
        self.assertEqual(len(current), len(original) + 15)
        pnames = self.lumps["PNAMES"]
        names = [pnames[i:i + 8].rstrip(b"\0").decode("ascii") for i in range(4, len(pnames), 8)]
        for record in current[len(original):]:
            name, _, width, height, _, patches = struct.unpack_from("<8sihhih", record)
            x, y, patch, _, _ = struct.unpack_from("<5h", record, 22)
            name = name.rstrip(b"\0").decode("ascii")
            self.assertEqual((x, y, patches), (0, 0, 1))
            self.assertEqual(names[patch], name)
            self.assertEqual(struct.unpack_from("<2h", self.lumps[name]), (width, height))

    def test_wall_and_flat_resources_have_tileable_edges(self):
        walls = [name for names in WALL_SAMPLES.values() for name in names]
        skies = [name for _, name in MAP_SKIES.values()]
        for name in walls + skies:
            with self.subTest(name=name):
                width, height, pixels = self.patch_pixels(self.lumps[name])
                self.assertEqual((width, height), (1024 if name in skies else 128, 128))
                self.assertTrue(all(row[0] == row[-1] for row in pixels))
                self.assertGreater(len({p for row in pixels for p in row}), 5)
                if name in skies:
                    lavender = sum(192 <= p <= 207 for row in pixels[:64] for p in row)
                    self.assertLess(lavender / (width * 64), 0.01)
        names = [name for samples in FLAT_SAMPLES.values() for _, name in samples]
        start = next(i for i, (n, _) in enumerate(self.entries) if n == "F_START")
        end = next(i for i, (n, _) in enumerate(self.entries) if n == "F_END")
        self.assertEqual({name for name, _ in self.entries[start + 1:end]}, set(names))
        for name in names:
            with self.subTest(name=name):
                data = self.lumps[name]
                self.assertEqual(len(data), 4096)
                self.assertEqual(data[:64], data[-64:])
                self.assertTrue(all(data[y * 64] == data[y * 64 + 63] for y in range(64)))
                self.assertGreater(len(set(data)), 4)

    def test_every_sector_and_wall_uses_its_local_zone(self):
        for spec in MAPS:
            index = next(i for i, (name, _) in enumerate(self.entries) if name == spec["name"])
            lumps = dict(self.entries[index:index + 11])
            floors, ceilings, walls = set(), set(), set()
            sectors = list(struct.iter_unpack("<hh8s8shhh", lumps["SECTORS"]))
            for number, (floor, ceiling, floor_name, ceiling_name, light, _, _) in enumerate(sectors):
                row, col = divmod(number, spec["cols"])
                zone = zone_for(spec["name"], row, col)
                decode = lambda value: value.rstrip(b"\0").decode("ascii")
                self.assertEqual((decode(floor_name), decode(ceiling_name), light),
                                 (zone.floor, zone.ceiling, zone.light))
                self.assertGreaterEqual(ceiling - floor, 128)
                self.assertIn(zone.floor, self.lumps)
                floors.add(zone.floor)
                ceilings.add(zone.ceiling)
            for _, _, _, _, middle, sector in struct.iter_unpack("<hh8s8s8sh", lumps["SIDEDEFS"]):
                name = middle.rstrip(b"\0").decode("ascii")
                if name != "-":
                    row, col = divmod(sector, spec["cols"])
                    self.assertEqual(name, zone_for(spec["name"], row, col).wall)
                    self.assertIn(name, self.lumps)
                    walls.add(name)
            self.assertGreaterEqual(len(floors), 2)
            self.assertGreaterEqual(len(walls), 3)
            self.assertIn("F_SKY1", ceilings)
            self.assertGreater(len(ceilings), 1)

    def test_key_landmarks_and_transitions_have_intended_materials(self):
        cases = (
            ("E1M1", 0, 2, "UWLIMEX", "UFPLAZA", "F_SKY1"),
            ("E1M1", 2, 2, "UWZUMBR", "UFMARBL", "UFCOFFR"),
            ("E1M1", 3, 2, "UWCONCR", "UFTERRZ", "UFCOFFR"),
            ("E1M1", 4, 2, "UWPLATF", "UFCONCT", "UFCONCT"),
            ("E1M2", 1, 2, "RWMETAL", "RFSLABS", "RFACOUS"),
            ("E1M2", 2, 2, "RWLIMES", "RFMARBL", "RFGOLD"),
            ("E1M3", 1, 2, "ZWSTONE", "ZFASPH", "F_SKY1"),
            ("E1M3", 2, 4, "ZWCEDAR", "ZFEARTH", "F_SKY1"),
            ("E1M3", 3, 2, "ZWGLASS", "ZFCONCT", "ZFROOF"),
            ("E1M3", 4, 2, "ZWSTONE", "ZFGRASS", "F_SKY1"),
        )
        for map_name, row, col, wall, floor, ceiling in cases:
            with self.subTest(map=map_name, row=row, col=col):
                zone = zone_for(map_name, row, col)
                self.assertEqual((zone.wall, zone.floor, zone.ceiling), (wall, floor, ceiling))
        with self.assertRaisesRegex(ValueError, "No site materials"):
            zone_for("E2M1", 0, 0)

    def test_each_map_selects_its_own_sky_and_title(self):
        text = self.lumps["UMAPINFO"].decode("ascii")
        maps = re.findall(r'map (\w+)\s*\{\s*levelname = "([^"]+)"\s*skytexture = "(\w+)"\s*\}', text)
        self.assertEqual(maps, [(name, title, sky) for name, (title, sky) in MAP_SKIES.items()])
        self.assertEqual(len({self.lumps[sky] for _, sky in MAP_SKIES.values()}), 3)


if __name__ == "__main__":
    unittest.main()
