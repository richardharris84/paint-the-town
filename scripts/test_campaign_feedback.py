import json
import math
import re
import struct
import tempfile
import unittest
from pathlib import Path

from build_expansion import ANIMATIONS, SIZES, CANDIDATE
from build_toronto_wad import _doom_palette, _mallet_weapon_lumps
from export_game_assets import patch_image
from campaign_feedback import (
    INTRO_DOOMEDNUM, INTRO_STATE, INTRO_THING, PAINT_STATE, PAINT_THING,
    PAINT_TICS, TIP, feedback_sprites, gameplay_patch, hud_lumps,
)
from doom_geometry import read_wad
from expansion_cast import CAMPAIGN_ENEMIES
from toronto_venues import venue_specs
from verify_campaign_feedback import build_feedback_fixture


class CampaignFeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.specs = venue_specs()
        cls.patch = gameplay_patch(ANIMATIONS, CAMPAIGN_ENEMIES, SIZES, cls.specs).decode("ascii")
        cls.lumps = read_wad(CANDIDATE)

    def block(self, category, number):
        blocks = re.findall(rf"(?m)^{category} {number}\n(.*?)(?:\n\n|\Z)", self.patch, re.S)
        return "\n".join(blocks)

    def test_paint_fixture_can_keep_the_portal_key_out_of_the_shot_path(self):
        for include_key, expected_keys in ((True, 1), (False, 0)):
            with self.subTest(include_key=include_key), tempfile.TemporaryDirectory() as directory:
                fixture = Path(directory) / "feedback.wad"
                build_feedback_fixture(fixture, include_key=include_key)
                lumps = read_wad(fixture)
                map_index = next(i for i, (name, _) in enumerate(lumps) if name == "E1M1")
                things = next(payload for name, payload in lumps[map_index + 1:]
                              if name == "THINGS")
                self.assertEqual(sum(kind == 5 for _, _, _, kind, _ in
                                     struct.iter_unpack("<5h", things)), expected_keys)

    def test_native_markers_use_one_pool_and_one_debit(self):
        for weapon, cost in ((1, 1), (2, 7), (3, 1)):
            block = self.block("Weapon", weapon)
            self.assertIn("Ammo type = 0", block)
            self.assertIn(f"Ammo per shot = {cost}", block)
        self.assertNotIn("ConsumeAmmo", self.patch)
        self.assertIn("Max ammo = 400", self.block("Ammo", 0))
        self.assertIn("Per ammo = 25", self.block("Ammo", 0))

    def test_message_only_pickups_use_valid_custom_mnemonics_and_no_bonus(self):
        self.assertIn("Doom version = 2024", self.patch)
        for i, spec in enumerate(self.specs):
            block = self.block("Thing", INTRO_THING + i)
            for field in ("Bits = 1", "Pickup item type = 0", "Pickup bonus count = 0",
                          "Pickup sound = 0", f"Pickup message = USER_TRINTRO{i + 1}"):
                self.assertIn(field, block)
            self.assertIn(f"USER_TRINTRO{i + 1} = {spec.title} | {TIP}", self.patch)
        self.assertIn("Duration = -1", self.block("Frame", INTRO_STATE))

    def test_each_map_has_one_intro_at_start_one_blue_key_and_no_shells(self):
        current = None
        for name, payload in self.lumps:
            if name in {s.name for s in self.specs}:
                current = next(s for s in self.specs if s.name == name)
            elif name == "THINGS":
                things = list(struct.iter_unpack("<5h", payload))
                intros = [t for t in things if INTRO_DOOMEDNUM <= t[3] < INTRO_DOOMEDNUM + 9]
                self.assertEqual(len(intros), 1)
                self.assertEqual(intros[0][:2], current.start)
                self.assertEqual(intros[0][3], INTRO_DOOMEDNUM + int(current.name[-1]) - 1)
                self.assertEqual(sum(t[3] == 5 for t in things), 1)
                self.assertFalse(any(t[3] in (2008, 2049) for t in things))

    def test_route_tips_offer_controls_map_objective_and_spacebar_advice(self):
        from campaign_feedback import (FIND_TIP_DOOMEDNUM, NAME_TIP_DOOMEDNUM,
                                       SPACEBAR_TIP_DOOMEDNUM, TAB_TIP_DOOMEDNUM)
        self.assertIn("USER_TRTAB = Tip: Press Tab to view the map", self.patch)
        self.assertIn("USER_TRFIND = Find the Portal Key & Exit!", self.patch)
        self.assertIn("USER_TRSPACE = Portal Key found! "
                      "Press Spacebar at the EXIT panel", self.patch)
        self.assertIn("Move: W A S D", self.patch)
        current = None
        for name, payload in self.lumps:
            if name in {s.name for s in self.specs}:
                current = next(s for s in self.specs if s.name == name)
            elif name == "THINGS" and current is not None:
                level = int(current.name[-1])
                things = list(struct.iter_unpack("<5h", payload))
                kinds = [t[3] for t in things]
                self.assertEqual(kinds.count(TAB_TIP_DOOMEDNUM), 2, current.title)
                self.assertEqual(kinds.count(FIND_TIP_DOOMEDNUM), 4, current.title)
                self.assertEqual(kinds.count(NAME_TIP_DOOMEDNUM + level - 1), 2, current.title)
                self.assertEqual(kinds.count(SPACEBAR_TIP_DOOMEDNUM), 1, current.title)
                key = next(t for t in things if t[3] == 5)
                tip = next(t for t in things if t[3] == SPACEBAR_TIP_DOOMEDNUM)
                self.assertLess(math.hypot(tip[0] - key[0], tip[1] - key[1]), 200)
                current = None

    def test_stationary_nonphysical_paint_child_lasts_exactly_three_seconds(self):
        self.assertEqual(sum(PAINT_TICS), 3 * 35)
        self.assertIn("Next frame = 2410", self.block("Frame", 93))
        self.assertIn(f"Args1 = {PAINT_THING}", self.block("Frame", 2410))
        self.assertIn("Args5 = -65536", self.block("Frame", 2410))
        self.assertIn("FRAME 2410 = SpawnObject", self.patch)
        self.assertIn("Bits = 528", self.block("Thing", PAINT_THING))
        for i, duration in enumerate(PAINT_TICS):
            block = self.block("Frame", PAINT_STATE + i)
            self.assertIn(f"Duration = {duration}", block)
            self.assertIn(f"Next frame = {PAINT_STATE + i + 1 if i < 3 else 0}", block)
        sprites = dict(feedback_sprites())
        self.assertNotEqual(sprites["BKEYA0"], sprites["BKEYB0"])
        self.assertEqual(len({sprites[f"PBLT{c}0"] for c in "ABCD"}), 4)
        for c in "ABCD":
            self.assertEqual(struct.unpack_from("<4h", sprites[f"PBLT{c}0"]), (40, 40, 20, 20))

    def test_stock_pickups_are_replaced_with_paint_kit_art_and_messages(self):
        from campaign_feedback import PICKUP_SPRITES
        sprites = dict(feedback_sprites())
        for prefix, kind, frames in PICKUP_SPRITES:
            names = [f"{prefix}{chr(65 + frame)}0" for frame in range(frames)]
            for name in names:
                self.assertIn(name, sprites, kind)
            self.assertEqual(len({sprites[name] for name in names}), frames, kind)
        for text in ("GOTSUPER = Paint Surge!", "QUITMSG = ", "GOTSTIM = ",
                     "GOTMEDIKIT = ", "GOTMEDINEED = ", "GOTARMOR = ", "GOTMEGA = ",
                     "GOTBACKPACK = ", "GOTHTHBONUS = ", "GOTARMBONUS = "):
            self.assertIn(text, self.patch)
        strings = self.patch.partition("[STRINGS]")[2]
        self.assertNotIn("soul", strings.lower())
        self.assertNotIn("armor bonus", strings.lower())

    def test_hud_draws_shared_pool_not_shell_rocket_or_fuel_counters(self):
        definition = json.loads(dict(hud_lumps())["SBARDEF"])
        self.assertEqual(definition["version"], "1.0.0")
        hud = definition["data"]
        self.assertEqual(
            hud["numberfonts"],
            [{"name": "Medium", "type": 0, "stem": "TRN"}],
        )
        self.assertEqual(len(hud["statusbars"]), 3)
        visible = hud["statusbars"][0]["children"]
        ammo = [element["number"] for element in visible
                if "number" in element and element["number"]["type"] in (3, 4, 5, 6, 7)]
        self.assertEqual([e["type"] for e in ammo], [3, 5])
        self.assertEqual([e["x"] for e in ammo], [27, 58])
        self.assertTrue(all(e["param"] == 0 for e in ammo))
        self.assertTrue(all(e["font"] == "Medium" for e in ammo))
        self.assertEqual(hud["statusbars"][0]["fillflat"], "PBFILL")
        self.assertTrue(all(bar["fillflat"] == "PBFILL" for bar in hud["statusbars"]))
        self.assertFalse(any("graphic" in e and e["graphic"]["patch"] in ("PBMAPTIP", "PBCNTRL")
                             for e in visible))
        self.assertIsNone(hud["statusbars"][-1]["children"])

    def test_selected_marker_is_distinct_from_ownership(self):
        from hud_art import hud_art_lumps
        assets = dict(hud_art_lumps())
        bars = json.loads(dict(hud_lumps())["SBARDEF"])["data"]["statusbars"]
        for children in (bars[0]["children"], bars[1]["children"][0]["canvas"]["children"]):
            icons = [c["graphic"] for c in children if "graphic" in c
                     and c["graphic"]["patch"].startswith(("TRON", "TROWN", "TROFF"))]
            for selected in (1, 2, 3, 4):
                for owned in ({2}, {2, 3}, {2, 3, 4}):
                    if selected != 1 and selected not in owned:
                        continue
                    visible = []
                    for icon in icons:
                        valid = all({
                            6: c["param"] in owned, 7: c["param"] not in owned,
                            8: c["param"] == selected, 9: c["param"] != selected,
                        }[c["condition"]] for c in icon["conditions"])
                        if valid:
                            visible.append(icon["patch"])
                    self.assertEqual(len(visible), 3)
                    self.assertEqual(sum(name.startswith("TRON") for name in visible),
                                     int(selected != 1))
            for slot in (2, 3, 4):
                self.assertEqual(len({assets[f"{stem}{slot}"]
                                      for stem in ("TRON", "TROWN", "TROFF")}), 3)

    def test_mallet_replaces_fist_art_without_changing_melee_definition(self):
        assets = dict(self.lumps)
        sprites = [assets[f"PUNG{frame}0"] for frame in "ABCD"]
        self.assertEqual(len(set(sprites)), 4)
        for sprite, left in zip(sprites, (-90, -90, -60, -80)):
            self.assertEqual(struct.unpack_from("<4h", sprite), (160, 144, left, -24))
        expected = dict(_mallet_weapon_lumps())
        bounds = []
        for frame, sprite in zip("ABCD", sprites):
            self.assertEqual(sprite, expected[f"PUNG{frame}0"])
            image, _ = patch_image(sprite, _doom_palette())
            alpha = image.getchannel("A")
            opaque = [(count, color) for count, color in image.getcolors(512) if color[3]]
            self.assertGreater(len(opaque), 80)
            self.assertGreater(sum(count for count, _ in opaque), 2000)
            self.assertEqual({value for _, value in alpha.getcolors()}, {0, 255})
            bounds.append(image.getbbox())
        self.assertLess(bounds[1][1], bounds[0][1])
        self.assertGreater(bounds[3][1], bounds[2][1])
        self.assertTrue(all(x0 >= 65 and x1 == 160 and y1 == 144
                            for x0, _, x1, y1 in bounds))
        self.assertGreater(bounds[0][0] + 90, 160)
        self.assertLess(bounds[2][0] + 60, 160)
        self.assertNotIn("Weapon 0", self.patch)

    def test_hud_has_no_control_hints_or_campaign_thumbnail(self):
        assets = dict(hud_lumps())
        self.assertNotIn("TRMAP", assets)
        self.assertNotIn("PBMAPTIP", assets)
        self.assertNotIn("PBCNTRL", assets)

    def test_owned_medium_glyphs_and_full_native_face_coverage(self):
        from build_expansion import _doom_iwad
        assets = dict(hud_lumps())
        expected = {name for name in _doom_iwad() if name.startswith("STF")
                    and not name.startswith("STFB")}
        self.assertEqual({name for name in assets if name.startswith("STF")}, expected)
        for name in expected:
            self.assertEqual(struct.unpack_from("<4h", assets[name]), (26, 32, 0, 0))
            self.assertNotEqual(assets[name], _doom_iwad()[name])
        for character in "0123456789":
            self.assertEqual(struct.unpack_from("<4h", assets[f"TRNNUM{character}"]), (7, 11, 0, 0))
        visible = json.loads(assets["SBARDEF"])["data"]["statusbars"][0]["children"]
        self.assertTrue(all(e[k]["font"] == "Medium" for e in visible
                            for k in ("number", "percent") if k in e))

    def test_player_face_stays_sharp_with_strong_contrast_and_hard_edges(self):
        from hud_art import face_images
        import numpy as np
        for name, image in face_images().items():
            with self.subTest(face=name):
                self.assertEqual(image.size, (26, 32))
                alpha = np.asarray(image.getchannel("A"))
                # Hard binary edges: no soft antialiased fringe to blur natively.
                self.assertEqual(set(alpha.flatten().tolist()) - {0}, {255})
                rgb = np.asarray(image.convert("RGB"), dtype=float)
                luminance = (rgb @ (0.299, 0.587, 0.114))[alpha > 0]
                self.assertGreaterEqual(luminance.std(), 60, name)
                self.assertGreaterEqual(luminance.max() - luminance.min(), 200, name)

    def test_transition_glyphs_reuse_hud_style_not_stock_red_art(self):
        from hud_art import digit_image, transition_images
        images = transition_images()
        for digit in "0123456789":
            self.assertEqual(images[f"WINUM{digit}"].tobytes(), digit_image(digit).tobytes())
        self.assertTrue({"WIF", "WIENTER", "WIOSTK", "WITIME", "WIPAR", "WICOLON"} <= images.keys())
        self.assertTrue({f"STCFN{code:03}" for code in range(33, 96)} <= images.keys())
        for name, image in images.items():
            self.assertIsNotNone(image.getbbox(), name)
            self.assertFalse(any(r > g * 1.5 and r > b * 1.5 and a
                                 for r, g, b, a in image.getdata()), name)


class BitmapLabelTests(unittest.TestCase):
    def test_all_toolbar_labels_share_markers_native_glyph_size(self):
        from hud_art import pixel_text
        image, _ = patch_image(dict(hud_lumps())["PBHUD"], _doom_palette())
        background = image.getpixel((1, 23))
        for x, text in ((2, "PAINTBALLS"), (69, "HEALTH"), (113, "MARKERS"),
                        (177, "ARMOUR")):
            with self.subTest(label=text):
                label = pixel_text(text, compact=True)
                self.assertEqual(label.getbbox()[3], 5)
                self.assertEqual(label.width, len(text) * 4)
                actual = image.crop((x, 23, x + label.width, 31))
                for y in range(8):
                    for column in range(label.width):
                        self.assertEqual(actual.getpixel((column, y)) != background,
                                         bool(label.getpixel((column, y))[3]))

    def test_markers_fits_without_resampling_or_partial_alpha(self):
        from hud_art import pixel_text, CREAM
        image = pixel_text("MARKERS", compact=True)
        self.assertLessEqual(image.width, 30)
        self.assertEqual(set(image.getchannel("A").tobytes()), {0, 255})
        self.assertEqual({pixel[:3] for pixel in image.getdata() if pixel[3]}, {CREAM})
        for index in range(7):
            bounds = image.crop((index * 4, 0, index * 4 + 3, 5)).getbbox()
            self.assertEqual(bounds, (0, 0, 3, 5))


if __name__ == "__main__":
    unittest.main()

