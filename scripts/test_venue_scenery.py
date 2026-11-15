import json
import re
import struct
import unittest

from PIL import Image
from shapely.geometry import Point

from build_expansion import CANDIDATE, _doom_iwad
from doom_geometry import read_wad
from expansion_cast import CAMPAIGN_ENEMIES
from expansion_presentation import candidate_material_images
from export_game_assets import OUTPUT, patch_image
from project_paths import ROOT
from toronto_materials import texture_records
from toronto_venues import venue_specs
from venue_scenery import BY_KIND, DECORATIONS, FAN_KINDS, catalog, gameplay_patch, sprite_lumps


class VenueSceneryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lumps = read_wad(CANDIDATE)
        cls.assets = dict(cls.lumps)
        cls.specs = venue_specs()

    def test_static_actor_allocations_are_disjoint_and_noninteractive(self):
        actors = catalog()
        for field in ("doomednum", "thing", "state", "sprite_number", "sprite"):
            self.assertEqual(len({item[field] for item in actors}), len(actors))
        old_patch = dict(read_wad(ROOT / "Toronto_Realms.wad"))["DEHACKED"].decode("ascii")
        # Scenery is the final DEHACKED section in both published generations.
        old_patch = old_patch.partition("[SPRITES]\n240 = VAMP")[0]
        for item in actors:
            for label, field in (("Thing", "thing"), ("Frame", "state")):
                self.assertNotRegex(old_patch, rf"(?m)^{label} {item[field]}$")
            self.assertNotIn(item["doomednum"], {enemy.doomednum for enemy in CAMPAIGN_ENEMIES})
            self.assertFalse(any(item[field] for field in
                                 ("solid", "shootable", "counts_as_kill", "counts_as_item")))
            self.assertEqual(item["radius"], 0)
            self.assertEqual(item["action"], "NULL")
            self.assertEqual(sum(f["duration_tics"] for f in item["frames"]),
                             sum(item["frame_tics"]))
            if len(item["frames"]) == 1:
                self.assertEqual(item["duration_tics"], item["frame_tics"][0])
                self.assertEqual(item["next_state"], item["state"])
        patch = gameplay_patch()
        flags = list(map(int, re.findall(r"^Bits = (\d+)$", patch, re.M)))
        self.assertTrue(all(not flag & (1 | 2 | 4 | 65536 | 4194304 | 8388608)
                            for flag in flags))

    def test_sprite_posts_alpha_offsets_and_candidate_bytes(self):
        palette = _doom_iwad()["PLAYPAL"][:768]
        sprites = dict(sprite_lumps())
        for item in DECORATIONS:
            for frame in range(len(item.frame_tics)):
                name = f"{item.prefix}{chr(65 + frame)}{1 if item.directional else 0}"
                data = sprites[name]
                self.assertEqual(self.assets[name], data)
                image, metadata = patch_image(data, palette)
                self.assertEqual(image.size, (item.width, item.height) if item.width else (1, 1))
                self.assertLess(item.height, 255)
                self.assertEqual((metadata["left_offset"], metadata["top_offset"]),
                                 (item.width // 2, item.height))
                alpha = image.getchannel("A")
                if item.width:
                    self.assertEqual(set(alpha.tobytes()), {0, 255})
                    self.assertGreater(alpha.getbbox()[3], item.height - 3)

    def test_required_venue_counts_and_grounding(self):
        museum, park, square, nathan, union = self.specs[:5]
        self.assertGreaterEqual(len(museum.scenery), 8)
        self.assertGreaterEqual(len({kind for _, _, kind in museum.scenery}), 4)
        self.assertGreaterEqual(len(park.scenery), 24)
        self.assertEqual({kind for _, _, kind in park.scenery}, {"maple", "oak", "pine"})
        panels = [struct.unpack("<hh8s8s8sh", side)[3].rstrip(b"\0").decode()
                  for side in museum.compile().geometry.sides]
        self.assertGreaterEqual(sum(name.startswith("RMART") for name in panels), 12)
        self.assertIn("RMKING", panels)
        paintings = [name for name in panels if name.startswith("RMART")]
        self.assertEqual(len(paintings), len(set(paintings)))
        self.assertEqual(set(paintings), {f"RMART{i:X}" for i in range(1, 13)})
        signs = [region for region in square.regions
                 if region.title == "Surrounding billboard building"]
        self.assertEqual({region.surface.wall for region in signs}, {"SBILL1", "SBILL3", "SBILL4"})
        self.assertEqual(len(signs), 3)
        for region in signs:
            self.assertGreater(square.footprint.boundary.distance(region.polygon), 0)
        for spec in self.specs:
            venue = spec.compile()
            for x, y, kind in spec.scenery:
                item = BY_KIND[kind]
                if kind in FAN_KINDS:
                    self.assertTrue(any(region.solid and region.title.startswith("Ascending seating row")
                                        and polygon.covers(Point(x, y))
                                        for polygon, _, region in venue.faces))
                else:
                    self.assertTrue(venue.clear_at(x, y, 4))
                containing = [(region.surface.floor_height, region.surface.ceiling_height)
                              for polygon, _, region in venue.faces if polygon.covers(Point(x, y))]
                self.assertTrue(any(ceiling - floor >= item.height for floor, ceiling in containing))
            block = self.lumps[next(i for i, (name, _) in enumerate(self.lumps) if name == spec.name) + 1][1]
            placed = list(struct.iter_unpack("<5h", block))
            for x, y, kind in spec.scenery:
                self.assertIn((x, y, spec.scenery_angles[(x, y, kind)],
                               BY_KIND[kind].doomednum, 7), placed)

    def test_rink_landmarks_and_union_bearings(self):
        nathan, union = self.specs[3:5]
        rink = next(region for region in nathan.regions if region.title == "Reflecting pool / skating footprint")
        self.assertEqual((rink.surface.floor, rink.surface.floor_height, rink.surface.special),
                         ("NPSICE", 0, 0))
        towers = [region for region in nathan.regions if "City Hall" in region.title
                  and region.solid and region.surface.floor_height > 512]
        self.assertEqual(len(towers), 1)
        hotel = next(region for region in union.regions if region.title == "Royal York north facade")
        tracks = [region for region in union.regions if region.title == "South rail track"]
        self.assertGreater(hotel.polygon.bounds[1], union.start[1])
        for region in union.regions:
            if region.title.startswith("Royal York"):
                self.assertEqual(region.polygon.bounds[3], union.footprint.bounds[3])
        self.assertTrue(all(region.polygon.bounds[3] < 0 for region in tracks))
        self.assertEqual(len(tracks), 5)

    def test_tall_materials_reconstruct_exactly_from_short_patches(self):
        walls, _ = candidate_material_images(_doom_iwad()["PLAYPAL"][:768])
        pnames = self.assets["PNAMES"]
        names = [pnames[i:i + 8].rstrip(b"\0").decode()
                 for i in range(4, len(pnames), 8)]
        records = {record[:8].rstrip(b"\0").decode(): record
                   for record in texture_records(self.assets["TEXTURE1"])}
        for name in ["RMART1", "STAGEBK", "QENTRY", *[f"SBILL{i}" for i in range(1, 5)]]:
            record = records[name]
            width, height = struct.unpack_from("<hh", record, 12)
            result = Image.new("RGBA", (width, height))
            for x, y, index, _, _ in struct.iter_unpack("<5h", record[22:]):
                piece, _ = patch_image(self.assets[names[index]], _doom_iwad()["PLAYPAL"][:768])
                self.assertLessEqual(piece.height, 256)
                result.paste(piece, (x, y))
            self.assertEqual(result.tobytes(), walls[name].convert("RGBA").tobytes())

    def test_marker_equipment_remains_unchanged(self):
        old = read_wad(ROOT / "Toronto_Realms.wad")
        old_assets = dict(old)
        for name, data in self.lumps:
            if name.startswith(("PISG", "SHTG", "CHGG")):
                self.assertEqual(data, old_assets[name])

    def test_portable_decorations_resolve_to_exact_sprites_and_maps(self):
        actors = json.loads((OUTPUT / "decorations.json").read_text())
        self.assertEqual(actors, catalog())
        sprites = json.loads((OUTPUT / "sprites.json").read_text())
        manifest = json.loads((OUTPUT / "manifest.json").read_text())
        self.assertEqual(manifest["decoration_count"], len(actors))
        for actor in actors:
            sprite = sprites[actor["sprite"]]
            self.assertEqual((sprite["left_offset"], sprite["top_offset"]),
                             (actor["width"] // 2, actor["height"]))


if __name__ == "__main__":
    unittest.main()
