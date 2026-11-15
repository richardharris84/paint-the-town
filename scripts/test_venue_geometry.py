import struct
import unittest

from shapely.geometry import box

from doom_geometry import build_nodes
from venue_geometry import Region, Surface, add_exit, compile_venue


STONE = Surface("STARTAN3", "FLOOR4_8", "CEIL3_5")
WOOD = Surface("WOOD1", "FLOOR4_8", "CEIL3_5", floor_height=128)


class VenueGeometryTests(unittest.TestCase):
    def venue(self):
        return compile_venue("E1M1", box(-512, -512, 512, 512), STONE, [
            Region("Wooden blocker", box(-64, -64, 64, 64), WOOD, True),
        ])

    def test_cover_is_real_raised_sector_with_matching_visible_edges(self):
        venue = self.venue()
        self.assertTrue(venue.clear_at(0, -256, 34))
        self.assertFalse(venue.clear_at(0, 0, 16))
        self.assertFalse(venue.clear_at(70, 0, 16))
        self.assertTrue(venue.clear_at(120, 0, 34))
        sector = venue.geometry.sectors[venue.sector_at(0, 0)]
        self.assertEqual(sector.floor, 128)
        shared = [line for line in venue.geometry.lines if line[2] & 4]
        self.assertEqual(len(shared), 4)
        for line in shared:
            side = struct.unpack("<hh8s8s8sh", venue.geometry.sides[line[5]])
            self.assertEqual(side[3].rstrip(b"\0"), b"WOOD1")

    def test_cover_obstructs_direct_path_but_leaves_both_flanks(self):
        from shapely.geometry import LineString
        venue = self.venue()
        self.assertFalse(venue.walkable.covers(LineString([(0, -256), (0, 256)])))
        for side in (-160, 160):
            route = LineString([(0, -256), (side, -256), (side, 256), (0, 256)]).buffer(34)
            self.assertTrue(venue.walkable.covers(route))

    def test_intersecting_regions_create_shared_noded_edges(self):
        venue = compile_venue("E1M1", box(-512, -512, 512, 512), STONE, [
            Region("Timber gallery", box(-300, -512, 100, 512),
                   Surface("WOOD1", "FLOOR4_8", "CEIL3_5")),
            Region("Wooden blocker", box(-64, -64, 64, 64), WOOD, True),
        ])
        venue.geometry.thing(0, -320, 1, angle=90)
        add_exit(venue, (-64, 320), (64, 320))
        output = dict(build_nodes(venue.geometry.lumps()))
        self.assertGreater(len(output["NODES"]), 28)
        self.assertEqual(sum(line[3] == 52 for line in venue.geometry.lines), 1)

    def test_disconnecting_cover_and_out_of_bounds_regions_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "disconnected"):
            compile_venue("E1M1", box(-512, -512, 512, 512), STONE,
                          [Region("Wall", box(-512, -32, 512, 32), WOOD, True)])
        with self.assertRaisesRegex(ValueError, "outside footprint"):
            compile_venue("E1M1", box(-512, -512, 512, 512), STONE,
                          [Region("Lost gallery", box(1000, 1000, 2000, 2000), STONE)])


if __name__ == "__main__":
    unittest.main()
