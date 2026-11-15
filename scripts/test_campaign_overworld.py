import re
import struct
import unittest

from build_expansion import CANDIDATE, campaign_mapinfo, validate_resources, _doom_iwad
from build_mod_previews import patch
from campaign_order import STOPS, SOURCE_TO_SLOT
from campaign_overworld import NODES, overworld_lumps, stage_image
from doom_geometry import read_wad
from expansion_cast import map_enemies
from toronto_venues import venue_specs


class CampaignOverworldTests(unittest.TestCase):
    def test_exact_requested_route_and_venue_rivals(self):
        specs = venue_specs()
        self.assertEqual([s.title for s in specs], [
            "Royal Ontario Museum", "Queen's Park", "Sankofa Square",
            "Nathan Phillips Square", "Union Station", "Scotiabank Arena",
            "Rogers Centre", "Toronto Islands", "Toronto Zoo",
        ])
        self.assertEqual([s.name for s in specs], [f"E1M{i}" for i in range(1, 10)])
        self.assertEqual(len(SOURCE_TO_SLOT), 9)
        for i, rivals in enumerate((
                {"DINO", "ARMR"}, {"BLSQ", "STAG"}, {"BVER", "RFOX"},
                {"GOOS", "CHIP"}, {"DRON", "PIGE"}, {"SOWL", "WOLV"},
                {"BJAY", "GHOG"}, {"SWAN", "OTTR"}, {"BEAR", "WOLF"}), 1):
            self.assertEqual({e.prefix for e in map_enemies(f"E1M{i}")}, rivals)

    def test_all_pictures_decode_with_correct_dimensions_and_reproducibility(self):
        assets = dict(overworld_lumps())
        self.assertEqual(len(assets), 28)
        self.assertEqual(patch("TRZOO", assets).size, (320, 200))
        handoff_footer = patch("TRZOO", assets).crop((0, 182, 320, 200))
        self.assertEqual(len(set(handoff_footer.getdata())), 1,
                         "The native continuation prompt needs a clear footer")
        for stage, stop in enumerate(STOPS, 1):
            for prefix in ("TRI", "TRX"):
                name = f"{prefix}{stage:02}"
                self.assertEqual(struct.unpack_from("<4h", assets[name]), (320, 200, 0, 0))
                self.assertEqual(patch(name, assets).getchannel("A").getextrema(), (255, 255))
            title = patch(f"TRL{stage:02}", assets)
            self.assertLess(title.width, 300, stop.title)
            self.assertLess(title.height, 30)
        self.assertEqual(len({assets[f"TRI{i:02}"] for i in range(1, 10)}), 9)
        self.assertEqual(stage_image(4), stage_image(4))
        for invalid in (-1, 10):
            with self.assertRaises(ValueError):
                stage_image(invalid)

    def test_each_next_symbol_becomes_completed_at_the_following_stage(self):
        assets = dict(overworld_lumps())
        for stage in range(1, 10):
            before = patch(f"TRI{stage:02}", assets)
            after = patch(f"TRX{stage:02}", assets)
            x, y = NODES[stage - 1]
            box = (x - 5, y - 5, x + 6, y + 6)
            self.assertNotEqual(before.crop(box).tobytes(), after.crop(box).tobytes())
        # All final result markers have the same completed symbol.
        final = stage_image(9)
        symbols = [tuple(tuple(row[x - 2:x + 3]) for row in final[y - 2:y + 3])
                   for x, y in NODES]
        self.assertTrue(all(symbol == symbols[0] for symbol in symbols))

    def test_metadata_references_every_picture_and_only_zoo_ends_campaign(self):
        assets = dict(overworld_lumps())
        blocks = re.findall(r"map (E1M\d)\n\{(.*?)\}", campaign_mapinfo(venue_specs()).decode(),
                            re.DOTALL)
        self.assertEqual(len(blocks), 9)
        for stage, (name, block) in enumerate(blocks, 1):
            for field, prefix in (("exitpic", "TRX"), ("enterpic", "TRI"), ("levelpic", "TRL")):
                resource = f"{prefix}{stage:02}"
                self.assertIn(f'{field} = "{resource}"', block)
                self.assertIn(resource, assets)
            if stage < 9:
                self.assertIn(f'next = "E1M{stage + 1}"', block)
                self.assertNotIn("endpic", block)
            else:
                self.assertIn('levelname = "Toronto Zoo"', block)
                self.assertIn('endpic = "TRVICTRY"', block)
                self.assertNotIn("next =", block)
        self.assertIn('interbackdrop = "TRZOO"', blocks[7][1])
        self.assertIn('intertext = "NEXT STOP: TORONTO ZOO"', blocks[7][1])
        self.assertNotIn("intertextsecret", blocks[7][1])

    def test_missing_map_picture_is_rejected(self):
        broken = [(name, data) for name, data in read_wad(CANDIDATE) if name != "TRI09"]
        with self.assertRaisesRegex(ValueError, "TRI09"):
            validate_resources(broken, _doom_iwad())


if __name__ == "__main__":
    unittest.main()
