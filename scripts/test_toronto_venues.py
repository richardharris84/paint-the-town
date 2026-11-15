import struct
import unittest

from shapely.geometry import LineString

from doom_geometry import build_nodes
from toronto_venues import UNITS_PER_FOOT, scotiabank_arena, venue_specs


class VenueLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.specs = venue_specs()
        cls.venues = {spec.name: spec.compile() for spec in cls.specs}

    def test_campaign_has_nine_distinct_venue_footprints(self):
        self.assertEqual([s.name for s in self.specs], [f"E1M{i}" for i in range(1, 10)])
        self.assertEqual(len({s.footprint.wkb for s in self.specs}), 9)
        for spec in self.specs:
            with self.subTest(map=spec.name):
                self.assertGreaterEqual(len(spec.districts), 4)
                self.assertGreaterEqual(sum(r.solid for r in spec.regions), 8)
                self.assertGreater(spec.footprint.area, 3_000_000)
                self.assertTrue(spec.scale_note)

    def test_two_full_length_routes_clear_the_largest_actor_plus_margin(self):
        # Largest approved actor radius 34 plus 16 = a 100-unit-wide corridor.
        for spec in self.specs:
            venue = self.venues[spec.name]
            with self.subTest(map=spec.name):
                self.assertEqual(len(spec.routes), 2)
                self.assertFalse(venue.walkable.buffer(-50).is_empty)
                for route in spec.routes:
                    self.assertEqual(route[0], spec.start)
                    self.assertEqual(route[-1], spec.exit_center)
                    for a, b in zip(route, route[1:]):
                        self.assertTrue(venue.walkable.covers(LineString((a, b)).buffer(50)),
                                        f"{spec.name}: blocked route segment {a} -> {b}")
                a, b = map(LineString, spec.routes)
                self.assertGreater(a.hausdorff_distance(b), 300)

    def test_cover_blocks_movement_sight_and_standing_height_hitscan(self):
        for spec in self.specs:
            venue = self.venues[spec.name]
            with self.subTest(map=spec.name):
                for polygon, sector, region in venue.faces:
                    surface = venue.geometry.sectors[sector]
                    if region.solid:
                        if region.title != "Dugout bench":
                            self.assertGreaterEqual(surface.floor, 56)
                        self.assertFalse(venue.clear_at(*polygon.representative_point().coords[0]))
                self.assertTrue(venue.clear_at(*spec.start, 50))
                self.assertTrue(venue.clear_at(*spec.exit_center, 50))
                self.assertEqual(sum(line[3] == 52 for line in venue.geometry.lines), 8)
                doors = [line for line in venue.geometry.lines if line[3] == 32]
                self.assertGreaterEqual(len(doors), 4)
                checkpoint = next(r for r in spec.regions if r.title == "Blue-key exit checkpoint")
                interior = next(r for r in spec.regions if r.title == "Exit checkpoint interior")
                self.assertAlmostEqual(sum(LineString((venue.geometry.vertices[line[0]],
                                                      venue.geometry.vertices[line[1]])).length
                                           for line in doors),
                                       checkpoint.polygon.length + interior.polygon.length, delta=0.1)
                door_sector = next(sector for _, sector, region in venue.faces
                                   if region.title == "Blue-key exit checkpoint")
                for line in doors:
                    self.assertEqual(struct.unpack_from("<h", venue.geometry.sides[line[6]], 28)[0],
                                     door_sector)
                    neighbor = struct.unpack_from("<h", venue.geometry.sides[line[5]], 28)[0]
                    self.assertGreaterEqual(venue.geometry.sectors[neighbor].ceiling, 128)
                    upper = struct.unpack_from("<8s", venue.geometry.sides[line[5]], 4)[0].rstrip(b"\0")
                    self.assertEqual(upper, b"-")
                    middle = struct.unpack_from("<8s", venue.geometry.sides[line[5]], 20)[0].rstrip(b"\0")
                    self.assertEqual(middle, b"-")
                transfers = [line for line in venue.geometry.lines if line[3] == 242]
                self.assertEqual(len(transfers), 1)
                for line in venue.geometry.lines:
                    if line[3] == 52:
                        self.assertNotEqual(struct.unpack_from("<h", venue.geometry.sides[line[5]], 28)[0],
                                            door_sector)
                door = venue.geometry.sectors[door_sector]
                self.assertEqual(door.floor, door.ceiling)
                # The closed ring now opens to sky so no visible cap hangs over
                # the activated exit column; the key gating itself is unchanged.
                self.assertEqual(door.ceiling_texture, "F_SKY1")
                self.assertEqual(door.tag, transfers[0][4])
                control = venue.geometry.sectors[
                    struct.unpack_from("<h", venue.geometry.sides[transfers[0][5]], 28)[0]]
                self.assertEqual(control.ceiling_texture, "F_SKY1")
                self.assertGreaterEqual(control.ceiling, 1500)
                # The supply cache is a plain brighter alcove now: the orb is a
                # health powerup in the open, not a hidden "secret" area.
                self.assertEqual(sum(sector.special == 9 for sector in venue.geometry.sectors), 0)

    def test_real_node_builder_accepts_all_nine_non_grid_layouts(self):
        for spec in self.specs:
            with self.subTest(map=spec.name):
                venue = spec.compile()
                venue.geometry.thing(*spec.start, 1, angle=90)
                output = dict(build_nodes(venue.geometry.lumps()))
                subsectors = list(struct.iter_unpack("<HH", output["SSECTORS"]))
                self.assertGreater(len(subsectors), 40)
                self.assertEqual(len(output["NODES"]) // 28, len(subsectors) - 1)
                self.assertTrue(all(count >= 1 for count, _ in subsectors))
                self.assertFalse(output["NODES"].startswith((b"XNOD", b"ZNOD")))

    def test_measured_sports_anchors_and_compressed_district_coverage(self):
        rink = scotiabank_arena()
        shape = next(r.polygon for r in rink.regions if r.title == "Complete hockey rink")
        x0, y0, x1, y1 = shape.bounds
        self.assertAlmostEqual(x1 - x0, 85 * UNITS_PER_FOOT, delta=2)
        self.assertAlmostEqual(y1 - y0, 200 * UNITS_PER_FOOT, delta=2)
        baseball = next(s for s in self.specs if s.title == "Rogers Centre")
        self.assertEqual(baseball.anchors["left_alley_ft"], 368)
        self.assertEqual(baseball.anchors["right_alley_ft"], 359)
        self.assertAlmostEqual(next(r.polygon for r in baseball.regions
                                    if r.title == "Complete playing field").bounds[3],
                               400 * UNITS_PER_FOOT, delta=1)
        zoo = next(s for s in self.specs if s.title == "Toronto Zoo")
        for district in ("Indo-Malaya", "Africa", "Americas", "Australasia", "Eurasia",
                         "Canadian Domain", "Tundra Trek"):
            self.assertIn(district, zoo.districts)
        islands = next(s for s in self.specs if s.title == "Toronto Islands")
        self.assertTrue({"Hanlan's Point", "Centre Island", "Ward's Island"} <= islands.districts.keys())
        self.assertEqual(sum(r.title.startswith("Public bridge") for r in islands.regions), 4)


if __name__ == "__main__":
    unittest.main()
