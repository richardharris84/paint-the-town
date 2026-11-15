import hashlib
import json
import unittest

from PIL import Image, ImageChops, ImageOps

from prepare_venue_art import normalize
from venue_art import DIRECTORY, material, sprite
from venue_scenery import BY_KIND, DECORATIONS, decoration_image


class VenueArtTests(unittest.TestCase):
    def test_sources_and_normalized_images_have_matching_provenance(self):
        manifest = json.loads((DIRECTORY / "normalization.json").read_text())
        self.assertEqual(len(manifest["sources"]), 30)
        self.assertEqual(len(manifest["sprites"]), 827)
        for name, digest in manifest["sources"].items():
            self.assertEqual(hashlib.sha256((DIRECTORY / name).read_bytes()).hexdigest(), digest)
        for row in manifest["sprites"]:
            self.assertEqual(hashlib.sha256((DIRECTORY / "sprites" / row["file"]).read_bytes()).hexdigest(),
                             row["sha256"])

    def test_native_sprites_are_grounded_binary_alpha_and_not_placeholder_art(self):
        for item in DECORATIONS:
            for frame in range(len(item.frame_tics)):
                image = decoration_image(item, frame)
                self.assertEqual(image.size, (item.width, item.height))
                self.assertEqual(set(image.getchannel("A").tobytes()), {0, 255})
                self.assertEqual(image.getbbox()[3], image.height)
                colors = {pixel[:3] for pixel in image.getdata() if pixel[3]}
                self.assertGreater(len(colors), 80)

    def test_actual_silhouettes_match_human_and_species_scale(self):
        heights = {}
        for kind in ("referee", "pitcher", "catcher", "elephant", "giraffe", "deer",
                     "kangaroo", "tiger", "bison", "penguin"):
            image = sprite(kind)
            bounds = image.getbbox()
            heights[kind] = bounds[3] - bounds[1]
        self.assertTrue(56 <= heights["referee"] <= 64)
        self.assertTrue(56 <= heights["pitcher"] <= 64)
        self.assertLess(heights["catcher"], heights["pitcher"])
        self.assertTrue(96 <= heights["elephant"] <= 104)
        self.assertTrue(160 <= heights["giraffe"] <= 176)
        self.assertTrue(56 <= heights["deer"] <= 64)
        self.assertTrue(40 <= heights["tiger"] <= 48)
        self.assertTrue(20 <= heights["penguin"] <= 24)

    def test_animation_frames_share_scale_and_remain_distinct(self):
        for kind, count in (("referee", 4),):
            images = [sprite(kind, frame) for frame in range(count)]
            self.assertEqual(len({image.tobytes() for image in images}), count)
            self.assertEqual(len({image.size for image in images}), 1)
            self.assertTrue(all(image.getbbox()[3] == image.height for image in images))
            blue, red = sprite("hockey_blue"), sprite("hockey_red")
            self.assertEqual(BY_KIND["hockey_red"].frame_tics, (18, 18))
            self.assertTrue(blue.getbbox()[0] > 0 and red.getbbox()[0] > 0)
        original = [sprite("referee", frame) for frame in range(4)]
        resized = normalize(original, original[0].size)
        self.assertTrue(all(ImageChops.difference(a, b).getbbox() is None
                            for a, b in zip(original, resized)))

    def test_waiting_commuters_idle_with_watch_checks_not_walking(self):
        commuters = {kind: sprite(kind) for kind in
                     ("commuter_teal", "commuter_red", "commuter_gold")}
        self.assertEqual({image.size for image in commuters.values()},
                         {sprite("commuter_teal").size})
        self.assertEqual(len({image.tobytes() for image in commuters.values()}), 3)
        for kind, image in commuters.items():
            self.assertEqual(image.getbbox()[3], image.height, kind)
            frames = [sprite(kind, frame) for frame in range(4)]
            self.assertEqual(len({frame.tobytes() for frame in frames}), 4, kind)
            self.assertTrue(all(frame.getbbox()[3] == frame.height for frame in frames), kind)

    def test_directional_scenery_has_real_profiles_and_rear_views(self):
        for item in DECORATIONS:
            if not item.directional:
                continue
            views = [decoration_image(item, 0, rotation) for rotation in range(1, 9)]
            self.assertEqual(len({image.tobytes() for image in views}), 8, item.kind)
            self.assertNotEqual(views[0].tobytes(), views[4].tobytes(), item.kind)
            self.assertTrue(all(image.getbbox()[3] == item.height for image in views))
            if len(item.frame_tics) > 1:
                self.assertNotEqual(views[0].tobytes(), decoration_image(item, 1, 1).tobytes(),
                                    item.kind)

    def test_paintings_preserve_complete_source_aspect_ratio_inside_the_frame(self):
        from venue_scenery import material_images
        walls, _ = material_images()
        for index in range(12):
            name = "museum-paintings-source.png" if index < 6 else "museum-paintings-second-source.png"
            with Image.open(DIRECTORY / name) as source:
                cell = index % 6
                x, y = (cell % 3) * source.width / 3, (cell // 3) * source.height / 2
                cell_image = source.crop((round(x), round(y),
                                          round(x + source.width / 3), round(y + source.height / 2)))
                artwork = ImageOps.contain(cell_image.convert("RGB"), (218, 160),
                                           Image.Resampling.LANCZOS)
            left = 915 + (218 - artwork.width) // 2
            top = 114 + (160 - artwork.height) // 2
            displayed = walls[f"RMART{index + 1:X}"].crop(
                (left, top, left + artwork.width, top + artwork.height))
            self.assertEqual(displayed.tobytes(), artwork.tobytes())

    def test_royal_portrait_is_cropped_to_the_frame_and_centered(self):
        from venue_scenery import material_images
        walls, _ = material_images()
        with Image.open(DIRECTORY / "king-richard-source.png") as source:
            king = source.convert("RGB").crop((110, 86, 924, 963))
        king = ImageOps.contain(king, (320, 220), Image.Resampling.LANCZOS)
        left = 1024 - king.width // 2
        top = 78 + (220 - king.height) // 2
        displayed = walls["RMKING"].crop((left, top, left + king.width, top + king.height))
        self.assertEqual(displayed.tobytes(), king.tobytes())
        # All art must sit inside the band gallery walls actually display.
        band = walls["RMKING"].crop((0, 66, 2048, 323))
        self.assertGreater(len(set(band.getdata())), 1000)

    def test_walk_cycles_are_directional_grounded_and_consistently_scaled(self):
        for kind, size in (("polar_bear_walk-r", (120, 80)),
                           ("girl_green_walk-r", (40, 48))):
            for rotation in range(1, 9):
                frames = [sprite(f"{kind}{rotation}", phase) for phase in range(4)]
                self.assertEqual({frame.size for frame in frames}, {size})
                self.assertEqual(len({frame.tobytes() for frame in frames}), 4)
                self.assertTrue(all(frame.getbbox()[3] == size[1] for frame in frames))

    def test_high_definition_site_materials_and_skies_wrap_and_stay_rich(self):
        from build_toronto_wad import _doom_palette
        from expansion_presentation import venue_skies
        from venue_art import site_material
        for filename in ("materials_city.png", "materials_arena.png"):
            for index in range(8):
                image = site_material(filename, index)
                self.assertEqual(image.size, (128, 128))
                self.assertEqual(image.crop((0, 0, 1, 128)).tobytes(),
                                 image.crop((127, 0, 128, 128)).tobytes())
                self.assertEqual(image.crop((0, 0, 128, 1)).tobytes(),
                                 image.crop((0, 127, 128, 128)).tobytes())
                self.assertGreater(len(set(image.getdata())), 400, (filename, index))
        palette = Image.new("P", (1, 1))
        palette.putpalette(_doom_palette())
        skies = venue_skies(palette)
        self.assertEqual(set(skies), {"TSKYSAN", "TSKYNAT", "TSKYROG",
                                      "TSKYSCO", "TSKYQPK", "TSKYISL"})
        for name, sky in skies.items():
            self.assertEqual(sky.size, (1024, 128))
            data = sky.tobytes()
            self.assertTrue(all(data[row * 1024] == data[row * 1024 + 1023]
                                for row in range(128)), name)
            self.assertGreater(len(set(data)), 40, name)
            lavender = sum(192 <= value <= 207 for value in data[:1024 * 64])
            self.assertLess(lavender / (1024 * 64), 0.01, name)

    def test_materials_have_matching_opposite_edges_and_real_detail(self):
        for index in (0, 2, 4, 5, 6, 7, 9, 10, 12, 13, 14):
            image = material(index)
            self.assertEqual(image.crop((0, 0, 1, 128)).tobytes(),
                             image.crop((127, 0, 128, 128)).tobytes())
            self.assertEqual(image.crop((0, 0, 128, 1)).tobytes(),
                             image.crop((0, 127, 128, 128)).tobytes())
            self.assertGreater(len(set(image.getdata())), 1000)
        self.assertEqual(BY_KIND["referee"].height, 64)

    def test_key_body_is_smaller_and_has_a_pulsing_ground_halo(self):
        frames = [sprite("portal_key", frame) for frame in range(2)]
        for image in frames:
            body = image.crop((0, 0, image.width, 84)).getbbox()
            self.assertIsNotNone(body)
            self.assertGreaterEqual(body[1], 33)
            self.assertLessEqual(body[2] - body[0], 42)
            self.assertIsNotNone(image.crop((0, 84, 64, 96)).getbbox())
        self.assertNotEqual(frames[0].tobytes(), frames[1].tobytes())


if __name__ == "__main__":
    unittest.main()
