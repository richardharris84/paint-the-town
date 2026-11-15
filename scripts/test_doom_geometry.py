import json
import hashlib
import struct
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from doom_geometry import Geometry, MAP_LUMPS, NODEBUILDER, Sector, build_nodes, read_wad, replace_validated, write_wad


def sample_map(name="E1M1"):
    geometry = Geometry(name)
    room = geometry.sector(Sector(0, 256, "FLOOR4_8", "CEIL3_5"))
    cover = geometry.sector(Sector(128, 256, "FLOOR4_8", "CEIL3_5"))
    geometry.loop([(-512, -512), (-512, 512), (512, 512), (512, -512)], room, "STARTAN3")
    geometry.loop([(-64, -64), (64, -64), (64, 64), (-64, 64)], room, "STARTAN3", cover)
    geometry.thing(0, -320, 1, angle=90)
    return geometry


class GeometryTests(unittest.TestCase):
    def test_installed_builder_matches_recorded_distribution(self):
        manifest = json.loads((NODEBUILDER.parent.parent / "nodebuilder.json").read_text())
        self.assertEqual(hashlib.sha256(NODEBUILDER.read_bytes()).hexdigest().upper(), manifest["sha256"])

    def test_polygon_with_cover_builds_classic_nodes(self):
        geometry = sample_map()
        output = build_nodes(geometry.lumps())
        self.assertEqual([name for name, _ in output], ["E1M1", *MAP_LUMPS])
        lumps = dict(output)
        for name, stride in (("SEGS", 12), ("SSECTORS", 4), ("NODES", 28)):
            self.assertGreater(len(lumps[name]), 0)
            self.assertEqual(len(lumps[name]) % stride, 0)
        self.assertEqual(len(lumps["SECTORS"]), 52)
        subsectors = list(struct.iter_unpack("<HH", lumps["SSECTORS"]))
        self.assertTrue(all(count >= 1 for count, _ in subsectors))
        self.assertEqual(len(lumps["NODES"]) // 28, len(subsectors) - 1)

    def test_read_write_preserves_order_and_duplicate_names(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "test.wad"
            original = [("E1M1", b""), ("THINGS", b"one"), ("E1M2", b""), ("THINGS", b"two")]
            write_wad(path, original)
            self.assertEqual(read_wad(path), original)

    def test_failed_validation_never_overwrites_working_wad(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "release.wad"
            path.write_bytes(b"working")
            def reject(staged):
                raise ValueError("Invalid candidate")
            with self.assertRaisesRegex(ValueError, "Invalid candidate"):
                replace_validated(path, [("TEST", b"candidate")], reject)
            self.assertEqual(path.read_bytes(), b"working")
            self.assertFalse(path.with_suffix(".staged.wad").exists())

    def test_malformed_geometry_and_missing_builder_are_explicit_errors(self):
        geometry = sample_map()
        with self.assertRaisesRegex(ValueError, "Zero-length"):
            geometry.line((1, 1), (1, 1), 0, "STARTAN3")
        with self.assertRaisesRegex(ValueError, "Invalid classic"):
            geometry.vertex((40000, 0))
        with self.assertRaisesRegex(ValueError, "Invalid Doom resource"):
            geometry.side(0, "TEXTURE_TOO_LONG")
        with self.assertRaisesRegex(FileNotFoundError, "Missing ZDBSP"):
            build_nodes(geometry.lumps(), Path("nonexistent-node-builder.exe"))


if __name__ == "__main__":
    unittest.main()
