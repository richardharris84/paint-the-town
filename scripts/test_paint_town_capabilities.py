import copy
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from verify_paint_town_capabilities import patrol_checks, read_probe_actor


class PatrolProofTests(unittest.TestCase):
    def save(self, directory, *, duplicate=False, **changes):
        body = bytearray(600)
        fields = {-120: -250 * 65536, -116: 200 * 65536, -112: 0,
                  -84: 249, -24: 16 * 65536, -20: 64 * 65536,
                  -16: 0, -12: 65536, 0: 351, 24: 7101, 32: 2, 36: 1}
        fields.update(changes.get("fields", {}))
        for offset in ((128, 400) if duplicate else (128,)):
            for relative, value in fields.items():
                struct.pack_into("<i", body, offset + relative, value)
        path = Path(directory) / "probe.sav"
        path.write_bytes(b"fixture\0" + b"\0" * 8 + zlib.compress(body))
        return path

    def test_strict_native_record_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            actor = read_probe_actor(self.save(directory))
        self.assertEqual((actor["x"], actor["y"], actor["z"]), (-250, 200, 0))
        self.assertEqual((actor["state"], actor["flags"], actor["health"]), (7101, 2, 1))
        self.assertEqual((actor["momx"], actor["momy"]), (0, 1))

    def test_rejects_ambiguous_or_unrecognized_records(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "found 2"):
                read_probe_actor(self.save(directory, duplicate=True))
            for relative, value in ((-84, 240), (-24, 0), (-20, 0),
                                    (24, 7002), (32, 6), (36, 0)):
                with self.subTest(relative=relative):
                    with self.assertRaisesRegex(ValueError, "found 0"):
                        read_probe_actor(self.save(directory, fields={relative: value}))

    def positions(self):
        values = {"clear": 225, "obstructed": 50, "obstructed-later": 50,
                  "resumed": 50, "resumed-later": -100, "before-load": -225,
                  "after-load": -200, "after-load-final": -100}
        return {key: dict(x=-250, y=y, z=0, flags=2, health=1,
                          momy=-1 if key == "clear" else 1)
                for key, y in values.items()}

    def test_requires_measured_patrol_contracts(self):
        positions = self.positions()
        self.assertTrue(all(patrol_checks(positions).values()))
        cases = (
            ("grounded", "clear", "z", 1),
            ("solid_invulnerable_noncounting", "clear", "flags", 6),
            ("bounded", "clear", "x", -260),
            ("travel_and_turns_observed", "clear", "momy", 1),
            ("blocked_without_reset", "obstructed-later", "y", 51),
            ("resumed_after_obstruction", "resumed-later", "y", 60),
            ("moving_after_load", "after-load-final", "y", -199),
        )
        for check, key, field, value in cases:
            with self.subTest(check=check):
                changed = copy.deepcopy(positions)
                changed[key][field] = value
                with self.assertRaisesRegex(AssertionError, check):
                    patrol_checks(changed)


if __name__ == "__main__":
    unittest.main()
