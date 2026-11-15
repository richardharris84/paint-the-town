import re
import tempfile
import struct
import unittest
import zlib
from pathlib import Path

from venue_walkers import gameplay_patch, sprite_lumps
from verify_venue_walkers import MAPS, matched_walkers, motion_checks, native_level_state
from verify_union_stability import reposition_fixture


# A synthetic two-route config exercising the matching logic; Union itself now
# hosts static commuters, so no shipped map uses two patrol routes.
TWO_ROUTES = dict(title="Test routes", expected_count=2,
                  controllers=((0, 1200), (-1200, 30)), radius=600)


class VenueWalkersTests(unittest.TestCase):
    def test_native_level_clock_requires_known_header_and_options(self):
        body = (bytes(64) + b"version 260".ljust(16, b"\0")
                + bytes((2, 1, 5, 1, 0, 0, 0))
                + b"d_pistolStart\0" + b"0\0"
                + b"d_soloNet\0" + b"0\0"
                + b"d_fastMonsters\0" + b"0\0"
                + b"d_noMonsters\0" + b"0\0"
                + b"d_respawnMonsters\0" + b"0\0"
                + b"d_modernCooperative\0" + b"1\0"
                + bytes(9) + (6301).to_bytes(3, "big"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "clock.sav"
            path.write_bytes(b"{}\0" + bytes(8) + zlib.compress(body))
            self.assertEqual(native_level_state(path), dict(episode=1, map=5, level_tics=6301))
            for invalid in (
                body.replace(b"version 260", b"version 999"),
                body.replace(b"d_soloNet", b"d_unknown"),
                body.replace(b"d_soloNet\0" + b"0\0", b"d_soloNet\0" + b"9\0"),
                body[:100],
            ):
                path.write_bytes(b"{}\0" + bytes(8) + zlib.compress(invalid))
                with self.assertRaises(ValueError):
                    native_level_state(path)

    @staticmethod
    def actor(x, y, state=7101):
        return dict(x=x, y=y, z=0, flags=2, health=1, state=state)

    def test_native_movement_cannot_compare_different_pedestrians(self):
        actors = [self.actor(0, 1380), self.actor(-1380, 30)]
        checks = motion_checks(actors, actors[::-1], TWO_ROUTES)
        self.assertFalse(checks["travel_observed"])
        self.assertFalse(checks["gait_state_advances"])
        moved = [self.actor(-1340, 30, 7103), self.actor(0, 1420, 7103)]
        self.assertTrue(all(motion_checks(actors, moved, TWO_ROUTES).values()))
        moved[0] = actors[1]
        self.assertFalse(motion_checks(actors, moved, TWO_ROUTES)["travel_observed"])

    def test_native_routes_require_one_actor_per_fixed_anchor(self):
        for actors in (
            [self.actor(0, 1200)],
            [self.actor(0, 1200), self.actor(0, 1220)],
            [self.actor(0, 1200), self.actor(-1900, 30)],
        ):
            with self.subTest(actors=actors), self.assertRaises(AssertionError):
                matched_walkers(actors, TWO_ROUTES)

    def test_native_safety_checks_include_both_snapshots(self):
        first = [self.actor(0, 1200), self.actor(-1200, 30)]
        second = [self.actor(0, 1240, 7103), self.actor(-1240, 30, 7103)]
        first[0]["z"] = 4
        first[1]["flags"] = 6
        checks = motion_checks(first, second, TWO_ROUTES)
        self.assertFalse(checks["grounded"])
        self.assertFalse(checks["solid_invulnerable_noncounting"])

    def test_intermediate_native_sample_detects_return_to_same_position(self):
        first = [self.actor(0, 1200), self.actor(-1200, 30)]
        middle = [self.actor(0, 1240, 7103), self.actor(-1240, 30, 7103)]
        self.assertTrue(all(motion_checks(first, first, TWO_ROUTES, intermediate=(middle,)).values()))
        middle[1]["z"] = 4
        self.assertFalse(motion_checks(first, first, TWO_ROUTES, intermediate=(middle,))["grounded"])

    def test_stability_fixtures_preserve_combat_geometry_and_other_maps(self):
        from build_expansion import CANDIDATE
        from doom_geometry import read_wad
        source = read_wad(CANDIDATE)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.wad"
            reposition_fixture(path, 5, 0, 1400, 90)
            actual = read_wad(path)
        self.assertEqual([name for name, _ in actual], [name for name, _ in source])
        current = None
        for (name, original), (_, updated) in zip(source, actual):
            if name.startswith("E1M") and len(name) == 4:
                current = int(name[-1])
            if name != "THINGS" or current != 5:
                self.assertEqual(updated, original, name)
                continue
            old = list(struct.iter_unpack("<5h", original))
            new = list(struct.iter_unpack("<5h", updated))
            self.assertEqual([thing for thing in old if thing[3] != 1], new[1:])
            self.assertEqual(new[0], (0, 1400, 90, 1, 7))

    def test_every_zero_tic_branch_reaches_a_timed_state(self):
        patch = gameplay_patch()
        frames = {
            int(number): dict(
                (key, int(value)) for key, value in
                re.findall(r"^(.+) = (-?\d+)$", body, re.M))
            for number, body in re.findall(r"Frame (\d+)\n(.*?)(?:\n\n)", patch, re.S)
        }
        jumps = {int(number) for number in
                 re.findall(r"FRAME (\d+) = JumpIfTracerCloser", patch)}

        def check_chain(state, visited):
            if frames[state]["Duration"] != 0:
                return
            self.assertNotIn(state, visited, f"Zero-tic cycle at frame {state}")
            successors = [frames[state]["Next frame"]]
            if state in jumps:
                successors.append(frames[state]["Args1"])
            for successor in successors:
                check_chain(successor, visited | {state})

        for state in frames:
            check_chain(state, set())
        for start in (7700, 9050, 9250):
            check = start + 102
            self.assertEqual(frames[check]["Next frame"], check + 1)
            self.assertEqual(frames[check + 1]["Duration"], 1)
            self.assertEqual(frames[check + 1]["Next frame"], check)

    def test_return_branch_remains_bounded_when_distance_test_never_succeeds(self):
        patch = gameplay_patch()
        for check in (7802, 9152, 9352):
            match = re.search(rf"Frame {check}\n(.*?)(?:\n\n)", patch, re.S)
            self.assertIsNotNone(match)
            successor = int(re.search(r"Next frame = (\d+)", match[1])[1])
            # The false branch must yield a simulation tic before testing again.
            timed = re.search(rf"Frame {successor}\n(.*?)(?:\n\n)", patch, re.S)
            self.assertIn("Duration = 1", timed[1])
            self.assertIn(f"Next frame = {check}", timed[1])

    def test_walkers_are_solid_noncombat_actors_with_turning_patrol_states(self):
        patch = gameplay_patch()
        self.assertIn("281 = ABWR\n285 = GRLG\n286 = GRLP", patch)
        self.assertNotIn("WALK", patch)
        self.assertNotIn("15400", patch)
        self.assertNotIn("15401", patch)
        self.assertIn("Thing 354\nID # = 15402", patch)
        self.assertIn("Thing 375\nID # = 15403", patch)
        self.assertIn("Thing 378\nID # = 15404", patch)
        self.assertIn("Thing 356\nID # = -1\nInitial frame = 7620", patch)
        self.assertIn("Thing 377\nID # = -1\nInitial frame = 9020", patch)
        self.assertIn("Thing 380\nID # = -1\nInitial frame = 9220", patch)
        self.assertIn("FRAME 7700 = JumpIfTracerCloser", patch)
        self.assertIn("FRAME 7701 = SeekTracer", patch)
        self.assertIn("FRAME 9050 = JumpIfTracerCloser", patch)
        self.assertIn("FRAME 9051 = SeekTracer", patch)
        self.assertIn("FRAME 9250 = JumpIfTracerCloser", patch)
        self.assertIn("FRAME 9251 = SeekTracer", patch)
        self.assertNotIn("= Stop", patch)
        self.assertNotIn("A_Scream", patch)
        self.assertNotIn("A_Pain", patch)

    def test_bootstrap_uses_one_fixed_noncounting_anchor_not_player_targeting(self):
        patch = gameplay_patch()
        self.assertNotIn("= Look", patch)
        self.assertNotIn("= MonsterProjectile", patch)
        self.assertNotIn("= FaceTarget", patch)
        self.assertNotIn("= JumpIfTargetCloser", patch)
        for base, anchor, actor in ((7600, 355, 356),
                                    (9000, 376, 377), (9200, 379, 380)):
            self.assertIn(f"FRAME {base + 1} = SpawnObject", patch)
            self.assertIn(f"FRAME {base + 12} = SpawnObject", patch)
            self.assertIn(f"FRAME {base + 21} = FindTracer", patch)
            for state, argument in ((base + 1, anchor), (base + 11, 4194304),
                                    (base + 12, actor), (base + 13, 4194304), (base + 14, 16)):
                body = re.search(rf"Frame {state}\n(.*?)(?:\n\n)", patch, re.S)[1]
                self.assertIn(f"Args1 = {argument}", body)
            for number in (actor, anchor,
                           {7600: 354, 9000: 375, 9200: 378}[base]):
                body = re.search(rf"Thing {number}\n(.*?)(?:\n\n)", patch, re.S)[1]
                bits = int(re.search(r"Bits = (\d+)", body)[1])
                self.assertEqual(bits & (4194304 | 65536), 0)
                if number != anchor:
                    self.assertEqual(bits & 4, 0)
        numbers = re.findall(r"^Frame (\d+)$", patch, re.M)
        self.assertEqual(len(numbers), len(set(numbers)))

    def test_each_walk_cycle_has_four_phases_in_all_eight_directions(self):
        lumps = sprite_lumps()
        self.assertEqual(len(lumps), 68)
        self.assertEqual(len({name for name, _ in lumps}), 68)
        self.assertEqual({name[:4] for name, _ in lumps}, {"ABWR", "GRLG", "GRLP"})
        # The green girl walks with full eight-direction rotations; the purple
        # girl keeps her supplied side-view art as a rotation-0 billboard.
        self.assertEqual(sorted(name for name, _ in lumps if name.startswith("GRLG")),
                         sorted(f"GRLG{chr(65 + phase)}{rotation}"
                                for phase in range(4) for rotation in range(1, 9)))
        self.assertEqual(sorted(name for name, _ in lumps if name.startswith("GRLP")),
                         [f"GRLP{chr(65 + phase)}0" for phase in range(4)])
        self.assertTrue(all(data for _, data in lumps))

    def test_arena_walker_cannot_override_zoo_bear_rotation_zero(self):
        from build_toronto_wad import NPC_ANIMATIONS
        prefixes = {row[0] for row in NPC_ANIMATIONS}
        self.assertNotIn("ABWR", prefixes)
        self.assertIn("BEAR", prefixes)
        self.assertFalse(any(name.startswith("BEAR") for name, _ in sprite_lumps()))


if __name__ == "__main__":
    unittest.main()
