import struct
import unittest

from shapely.geometry import LineString, Point
from shapely.ops import unary_union

from toronto_venues import venue_specs


class VenueRevisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.specs = {spec.title: spec for spec in venue_specs()}

    def test_one_cylindrical_tower_and_clear_center_ice(self):
        nathan = self.specs["Nathan Phillips Square"]
        towers = [r for r in nathan.regions if r.solid and r.surface.floor_height > 512]
        self.assertEqual(len(towers), 1)
        self.assertEqual(towers[0].title, "City Hall single cylindrical tower")
        self.assertAlmostEqual(towers[0].polygon.centroid.x, 0)
        rink = self.specs["Scotiabank Arena"]
        self.assertFalse(any("Centre-ice blocker" in r.title for r in rink.regions))
        self.assertTrue(rink.compile().clear_at(0, 0, 50))
        self.assertIn("referee", {kind for _, _, kind in rink.scenery})

    def test_sankofa_billboard_buildings_are_filled_blocks_not_thin_walls(self):
        sankofa = self.specs["Sankofa Square"]
        signs = [region for region in sankofa.regions
                 if region.title == "Surrounding billboard building"]
        self.assertEqual(len(signs), 3)
        for region in signs:
            xmin, ymin, xmax, ymax = region.polygon.bounds
            self.assertGreaterEqual(min(xmax - xmin, ymax - ymin), 192,
                                    region.surface.wall)

    def test_expanded_streets_and_level_union_crossing(self):
        union = self.specs["Union Station"]
        regions = {region.title: region for region in union.regions}
        south = regions["Front Street south asphalt lane"]
        median = regions["Front Street cobblestone median"]
        north = regions["Front Street north asphalt lane"]
        self.assertEqual((south.surface.floor, median.surface.floor, north.surface.floor),
                         ("ASPHALT", "COBBLEF", "ASPHALT"))
        self.assertEqual(south.polygon.bounds[3], median.polygon.bounds[1])
        self.assertEqual(median.polygon.bounds[3], north.polygon.bounds[1])
        self.assertTrue(all(region.surface.floor_height == 0 for region in (south, median, north)))
        self.assertTrue(union.compile().walkable.covers(
            LineString(((0, 1950), (0, 3200))).buffer(32)))
        sankofa = self.specs["Sankofa Square"]
        self.assertGreater(sankofa.footprint.area, 10_000_000)
        self.assertTrue({"Yonge Street north and south approaches",
                         "South block light-stone frontage",
                         "Dundas Street intersection"} <= {region.title for region in sankofa.regions})
        nathan = self.specs["Nathan Phillips Square"]
        self.assertTrue({"Queen Street roadway", "Queen Street north sidewalk"}
                        <= {region.title for region in nathan.regions})
        self.assertEqual({kind for _, _, kind in nathan.scenery if kind.endswith("_vendor")},
                         {"hotdog_vendor", "icecream_vendor"})
        for _, y, kind in nathan.scenery:
            if kind.endswith("_vendor"):
                self.assertTrue(-2180 < y < -1900)

    def test_exactly_one_center_ice_faceoff_trio(self):
        rink = self.specs["Scotiabank Arena"]
        expected = {"referee": (0, 0), "hockey_blue": (24, 64),
                    "hockey_red": (-24, -64)}
        for kind, position in expected.items():
            self.assertEqual([(x, y) for x, y, placed in rink.scenery if placed == kind],
                             [position])
        self.assertLess(expected["hockey_red"][1], 0)
        self.assertEqual(expected["referee"][1], 0)
        self.assertGreater(expected["hockey_blue"][1], 0)
        self.assertEqual(expected["hockey_blue"][0], -expected["hockey_red"][0])
        self.assertLess(abs(expected["hockey_blue"][0]), 30)
        self.assertTrue(rink.compile().clear_at(0, 0, 80))

    def test_rinkside_bear_route_is_walkable_without_opening_the_boards(self):
        rink = self.specs["Scotiabank Arena"]
        route = next(region for region in rink.regions
                     if region.title == "Continuous walkable rinkside bear route")
        self.assertFalse(route.solid)
        venue = rink.compile()
        for point in ((493, 0), (493, 125), (-493, -125)):
            self.assertTrue(venue.clear_at(*point, 36))
            self.assertEqual(venue.geometry.sectors[venue.sector_at(*point)].floor, 0)
        self.assertFalse(venue.clear_at(430, 125, 1))
        self.assertFalse(venue.clear_at(600, 0, 36))
        self.assertEqual(rink.start, (350, -1660))
        self.assertTrue(venue.walkable.covers(
            LineString((rink.start, (350, -760))).buffer(36)))
        self.assertTrue(venue.clear_at(350, -700, 36))
        from venue_scenery import FAN_KINDS
        fan_positions = [(x, y) for x, y, kind in rink.scenery if kind in FAN_KINDS]
        self.assertTrue(all(any(poly.covers(Point(x, y)) and region.solid
                                and region.title.startswith("Ascending seating row")
                                for poly, _, region in venue.faces)
                            for x, y in fan_positions))

    def test_south_frontage_and_hotel_have_real_mass_without_blocking_routes(self):
        square = self.specs["Sankofa Square"]
        facade = next(r for r in square.regions if r.title == "South block light-stone frontage")
        self.assertEqual(facade.polygon.bounds[::2], square.footprint.bounds[::2])
        self.assertGreater(facade.polygon.bounds[3] - facade.polygon.bounds[1], 200)
        self.assertTrue(square.compile().clear_at(*square.start, 34))
        for route in square.routes:
            self.assertTrue(square.compile().walkable.covers(LineString(route).buffer(32)))
        union = self.specs["Union Station"]
        venue = union.compile()
        self.assertFalse(venue.walkable.intersects(LineString(((-1150, 3840), (1150, 3840)))))
        self.assertTrue(venue.clear_at(0, 3500, 34))

    def test_varied_crowds_fill_both_stadiums_and_face_the_field(self):
        from venue_scenery import FAN_KINDS, BY_KIND, decoration_image
        designs = {decoration_image(BY_KIND[kind]).tobytes() for kind in FAN_KINDS}
        self.assertGreaterEqual(len(designs), 8)
        for title in ("Scotiabank Arena", "Rogers Centre"):
            spec = self.specs[title]
            fans = [placed for placed in spec.scenery if placed[2] in FAN_KINDS]
            self.assertGreaterEqual(len(fans), 112)
            self.assertEqual({placed[2] for placed in fans}, set(FAN_KINDS))
            venue = spec.compile()
            for x, y, kind in fans:
                self.assertTrue(any(region.solid and polygon.covers(Point(x, y))
                                    and region.title.startswith("Ascending seating row")
                                    for polygon, _, region in venue.faces))
            self.assertGreater(len({spec.scenery_angles[placed] for placed in fans}), 4)

    def test_hockey_players_have_opposite_world_facing_not_default_billboards(self):
        spec = self.specs["Scotiabank Arena"]
        blue, red = spec.scenery_angles[(24, 64, "hockey_blue")], spec.scenery_angles[(-24, -64, "hockey_red")]
        self.assertEqual((blue - red) % 360, 180)
        from build_expansion import populate
        things = populate(spec, spec.compile()).things
        from venue_scenery import BY_KIND
        for kind, angle in (("hockey_blue", blue), ("hockey_red", red)):
            self.assertEqual([thing[2] for thing in things if thing[3] == BY_KIND[kind].doomednum],
                             [angle])

    def test_baseball_corridor_and_dugout_cover(self):
        spec = self.specs["Rogers Centre"]
        roster = {kind: (x, y) for x, y, kind in spec.scenery
                  if kind in ("pitcher", "catcher", "batter")}
        self.assertEqual(roster, {"pitcher": (0, 590), "catcher": (0, -100),
                                  "batter": (52, 24)})
        self.assertEqual(sum(kind == "baseman" for _, _, kind in spec.scenery), 3)
        venue = spec.compile()
        checkpoint = next(region for region in spec.regions
                          if region.title == "Blue-key exit checkpoint")
        self.assertTrue(venue.clear_at(spec.exit_center[0],
                                      round(checkpoint.polygon.bounds[1]) - 40, 34))
        self.assertTrue(venue.walkable.covers(LineString(((0, -180), (0, 700))).buffer(100)))
        bunkers = [r for r in spec.regions if r.title == "Tournament lane bunker"]
        self.assertFalse(any(r.polygon.centroid.y < 120 for r in bunkers))
        self.assertFalse(any(r.polygon.intersects(Point(x, 700).buffer(80))
                             for r in bunkers for x in (-600, 600)))
        interiors = [r for r in spec.regions if r.title == "Walk-in dugout interior"]
        self.assertEqual(len(interiors), 2)
        for region in interiors:
            x = region.polygon.centroid.x
            self.assertEqual((region.surface.floor_height, region.surface.ceiling_height), (-16, 160))
            for side in (-1, 1):
                entry = LineString(((x + side * 390, -150), (x, -150))).buffer(20)
                self.assertTrue(venue.walkable.covers(entry))
        walls = [r for r in spec.regions if r.title == "Dugout protective lower wall"]
        self.assertEqual(len(walls), 2)
        self.assertTrue(all(r.solid and r.surface.floor_height == 72 for r in walls))
        fence_edges = []
        for line in venue.geometry.lines:
            front, back = line[-2:]
            if back >= 0 and struct.unpack("<hh8s8s8sh", venue.geometry.sides[front])[4].rstrip(b"\0") == b"PTFENCE":
                self.assertEqual(line[2] & 17, 17)
                fence_edges.append(line)
        self.assertEqual(len(fence_edges), 2)

    def test_single_panel_and_revealed_portal_preserve_key_gating(self):
        for spec in self.specs.values():
            venue = spec.compile()
            sides = [struct.unpack("<hh8s8s8sh", data) for data in venue.geometry.sides]
            self.assertEqual(sum(side[2].rstrip(b"\0") == b"PTPANEL" for side in sides), 0)
            self.assertGreaterEqual(sum(line[3] == 32 for line in venue.geometry.lines), 4)
            self.assertEqual(sum(line[3] == 52 for line in venue.geometry.lines), 8)
            self.assertEqual(sum(line[3] == 242 for line in venue.geometry.lines), 1)
            self.assertEqual([(x, y) for x, y, kind in spec.scenery if kind == "portal"],
                             [])

    def test_outdoor_portal_approach_cannot_raise_the_boundary_into_a_chimney(self):
        for title in ("Queen's Park", "Toronto Zoo"):
            spec = self.specs[title]
            geometry = spec.compile().geometry
            for a, b, _, _, _, front, back in geometry.lines:
                if back >= 0:
                    continue
                p, q = geometry.vertices[a], geometry.vertices[b]
                if LineString((p, q)).distance(Point(spec.exit_center)) > 500:
                    continue
                sector = struct.unpack_from("<h", geometry.sides[front], 28)[0]
                self.assertLessEqual(geometry.sectors[sector].ceiling, 160)

    def test_baseball_spawn_faces_catcher_then_pitcher(self):
        from build_expansion import populate
        spec = self.specs["Rogers Centre"]
        geometry = populate(spec, spec.compile())
        starts = [thing for thing in geometry.things if thing[3] == 1]
        self.assertEqual(starts, [(0, -640, 90, 1, 7)])
        catcher_y = next(y for _, y, kind in spec.scenery if kind == "catcher")
        pitcher_y = next(y for _, y, kind in spec.scenery if kind == "pitcher")
        self.assertLess(spec.start[1], catcher_y)
        self.assertLess(catcher_y, pitcher_y)
        # The battery faces each other and never rotates with the player.
        angles = spec.scenery_angles
        self.assertEqual(angles[(0, 590, "pitcher")], 270)
        self.assertEqual(angles[(0, -100, "catcher")], 90)

    def test_zoo_is_compact_grounded_and_has_seven_regions_and_animals(self):
        spec = self.specs["Toronto Zoo"]
        self.assertLessEqual(spec.footprint.area, 30_918_750)
        expected = {"Indo-Malaya", "Africa", "Americas", "Australasia", "Eurasia",
                    "Canadian Domain", "Tundra Trek"}
        self.assertTrue(expected <= spec.districts.keys())
        from toronto_venues import ZOO_SPECIES
        species = [kind for pair in ZOO_SPECIES.values() for kind in pair]
        self.assertEqual(len(species), 14)
        self.assertEqual(len(set(species)), 14)
        for region, pair in ZOO_SPECIES.items():
            self.assertEqual(len(pair), 2)
            for species_name in pair:
                placements = [(x, y) for x, y, kind in spec.scenery if kind == species_name]
                self.assertEqual(len(placements), 1)
                habitat = next(r.polygon for r in spec.regions if r.title == region)
                self.assertTrue(habitat.covers(Point(*placements[0])))
        for region in spec.regions:
            if "pavilion" in region.title.lower():
                self.assertTrue(region.solid)
                self.assertGreaterEqual(region.surface.floor_height, 128)
                self.assertEqual(region.surface.ceiling, "F_SKY1")
        self.assertNotIn("Central pavilion", {r.title for r in spec.regions})

    def test_islands_water_edge_is_low_sky_and_explicitly_blocked(self):
        spec = self.specs["Toronto Islands"]
        venue = spec.compile()
        regions = [r for r in spec.regions if r.title == "Island open water horizon"]
        self.assertEqual(len(regions), 1)
        surface = regions[0].surface
        self.assertEqual((surface.floor_height, surface.ceiling_height), (-64, 0))
        self.assertEqual(surface.ceiling, "F_SKY1")
        water_titles = {"Island lake basin", "Island open water horizon"}
        water_sectors = {sector for _, sector, region in venue.faces
                         if region.title in water_titles}
        blocked_edges = 0
        for a, b, flags, _, _, front, back in venue.geometry.lines:
            if back < 0:
                continue
            fs = struct.unpack_from("<h", venue.geometry.sides[front], 28)[0]
            bs = struct.unpack_from("<h", venue.geometry.sides[back], 28)[0]
            if (fs in water_sectors) != (bs in water_sectors):
                self.assertTrue(flags & 1)
                blocked_edges += 1
        self.assertGreater(blocked_edges, 20)
        water = unary_union([polygon for polygon, _, region in venue.faces
                             if region.title in water_titles])
        self.assertEqual(venue.walkable.intersection(water).area, 0)
        self.assertIsNotNone(spec.playable_outline)
        self.assertGreater(spec.footprint.area, spec.playable_outline.area)


if __name__ == "__main__":
    unittest.main()
