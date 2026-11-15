import re
import struct
import tempfile
import unittest
from pathlib import Path

from doom_geometry import read_wad
from portal_gates import (
    BEAM_SPRITE, BEAM_THING, EMITTER_ID, PANEL_ID, SEGMENT_HEIGHT, SEGMENTS,
    DUST_PHASES, beam_image, dust_image, gameplay_patch, panel_image, place_gate, sprite_lumps,
)
from toronto_venues import venue_specs
from verify_expansion_checkpoints import build_fixture
from verify_portal_gates import build_portal_fixture


class PortalGateTests(unittest.TestCase):
    def test_fixed_ambush_emitter_and_noncombat_beam_states(self):
        patch = gameplay_patch()
        self.assertIn("Thing 358\nID # = 15410\nInitial frame = 7900", patch)
        self.assertIn("Bits = 560", patch)
        self.assertNotIn("Bits = 564", patch)
        self.assertNotIn("Bits = -", patch)
        self.assertIn("FRAME 7940 = Look", patch)
        look = patch.split("Frame 7940\n", 1)[1].split("[CODEPTR]", 1)[0]
        turn = patch.split("Frame 7941\n", 1)[1].split("[CODEPTR]", 1)[0]
        self.assertIn("Duration = 7\nNext frame = 7941", look)
        self.assertIn("Duration = 1\nNext frame = 7942\nUnknown 1 = 1073741824", turn)
        self.assertIn("FRAME 7941 = Turn", patch)
        self.assertEqual(patch.count(" = SpawnObject"), SEGMENTS)
        for index in range(SEGMENTS):
            self.assertIn(f"Args5 = {index * SEGMENT_HEIGHT * 65536}", patch)
        self.assertIn(f"Args1 = {BEAM_THING}", patch)
        for frame in range(4):
            self.assertIn(f"Sprite subnumber = {32768 | frame}", patch)
            self.assertIn(f"Next frame = {7920 + (frame + 1) % 4}", patch)
        frames = re.findall(r"Frame (\d+)\n(.*?)(?=\n\[CODEPTR\])", patch, re.S)
        self.assertTrue(all("Duration = 0\n" not in body for _, body in frames))

    def test_beam_animation_is_ground_anchored_and_tileable(self):
        images = [beam_image(frame) for frame in range(4)]
        self.assertEqual(len({image.tobytes() for image in images}), 4)
        for image in images:
            self.assertEqual(image.size, (144, SEGMENT_HEIGHT))
            self.assertEqual(image.crop((0, 0, 144, 1)).tobytes(),
                             image.crop((0, SEGMENT_HEIGHT - 4, 144, SEGMENT_HEIGHT - 3)).tobytes())
            self.assertTrue(all(image.getpixel((72, y))[3] == 255 for y in range(SEGMENT_HEIGHT)))
        sprites = dict(sprite_lumps())
        self.assertEqual(set(sprites), {"VBEAA0", "VBEAB0", "VBEAC0", "VBEAD0", "VPANA0",
                                       *(f"VDUS{chr(65 + i)}0" for i in range(DUST_PHASES))})
        self.assertEqual(struct.unpack_from("<4h", sprites["VBEAA0"]), (144, 224, 72, 224))

    def test_all_maps_have_one_panel_one_emitter_and_exit_inside_beam(self):
        for spec in venue_specs():
            venue = spec.compile()
            place_gate(venue.geometry, spec)
            things = venue.geometry.things
            self.assertEqual(sum(thing[3] == EMITTER_ID for thing in things), 1)
            self.assertEqual(sum(thing[3] == PANEL_ID for thing in things), 1)
            emitter = next(thing for thing in things if thing[3] == EMITTER_ID)
            self.assertEqual(emitter[:2], spec.exit_center)
            door = next(sector for sector in venue.geometry.sectors if sector.tag == 901)
            self.assertEqual(door.ceiling_texture, "F_SKY1")
            for line in venue.geometry.lines:
                if line[3] == 52:
                    for vertex in line[:2]:
                        x, y = venue.geometry.vertices[vertex]
                        self.assertLessEqual(abs(x - spec.exit_center[0]), 40)
                        self.assertLessEqual(abs(y - spec.exit_center[1]), 40)

    def test_inactive_dust_falls_and_does_not_accumulate_child_actors(self):
        first, second = dust_image(0), dust_image(1)
        pixels = lambda image: {(x, y) for y in range(image.height) for x in range(image.width)
                                 if image.getpixel((x, y))[3]}
        initial = pixels(first)
        self.assertLess(len(initial), first.width * first.height // 100)
        self.assertEqual(pixels(second), {(x, (y + 28) % first.height) for x, y in initial})
        patch = gameplay_patch()
        for phase in range(DUST_PHASES):
            self.assertIn(f"FRAME {7940 + phase * 2} = Look", patch)
        self.assertEqual(patch.count(" = SpawnObject"), SEGMENTS)
        panel = panel_image()
        self.assertEqual(panel.getbbox(), (7, 25, 73, 104))
        self.assertEqual(panel.getpixel((7, 103)), (229, 196, 107, 255))
        self.assertEqual(sum(panel.getpixel((x, 103))[3] > 0 for x in range(panel.width)), 66)
        self.assertNotEqual(panel.getpixel((40, 57))[:3], panel.getpixel((10, 57))[:3])

    def test_native_fixtures_preserve_portals_and_isolate_real_key_pickup(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "portal.wad"
            for side in ("south", "north"):
                spec, start_y = build_portal_fixture(path, 1, side)
                things = []
                current = None
                for name, data in read_wad(path):
                    if name.startswith("E1M") and len(name) == 4:
                        current = name
                    if name == "THINGS" and current == "E1M1":
                        things = list(struct.iter_unpack("<5h", data))
                        break
                player = next(t for t in things if t[3] == 1)
                key = next(t for t in things if t[3] == 5)
                self.assertEqual(player[:2], (spec.exit_center[0], start_y))
                self.assertEqual(abs(key[0] - player[0]), 72)
                self.assertEqual(key[1], player[1])
                self.assertEqual({t[3] for t in things if t[3] in (EMITTER_ID, PANEL_ID)},
                                 {EMITTER_ID, PANEL_ID})
            build_fixture(path)
            portal_count = sum(t[3] in (EMITTER_ID, PANEL_ID)
                               for name, data in read_wad(path) if name == "THINGS"
                               for t in struct.iter_unpack("<5h", data))
            self.assertEqual(portal_count, 18)


if __name__ == "__main__":
    unittest.main()
