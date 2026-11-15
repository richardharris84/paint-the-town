import shutil
import struct
import subprocess
import unittest

import numpy as np

from toronto_music import BARS, MUSIC_DIR, RATE, TRACKS, midi_bytes, score
import test_toronto_wad


class TorontoMusicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_toronto_wad.NpcAnimationTests.setUpClass()
        cls.lumps = test_toronto_wad.NpcAnimationTests.lumps

    def test_all_three_music_modes_are_replaced(self):
        digital = []
        for map_name, title, bpm, root, seed in TRACKS:
            with self.subTest(map=map_name):
                ogg = (MUSIC_DIR / f"{map_name}.ogg").read_bytes()
                midi = midi_bytes(score(root, seed), bpm, title)
                self.assertEqual(self.lumps[f"O_{map_name}"], ogg)
                self.assertEqual(self.lumps[f"H_{map_name}"], ogg)
                self.assertEqual(self.lumps[f"D_{map_name}"], ogg)
                self.assertEqual((MUSIC_DIR / f"{map_name}.mid").read_bytes(), midi)
                self.assertTrue(ogg.startswith(b"OggS"))
                self.assertEqual(struct.unpack_from(">IHHH", midi, 4), (6, 0, 1, 480))
                self.assertEqual(struct.unpack_from(">I", midi, 18)[0], len(midi) - 22)
                self.assertTrue(midi.endswith(b"\xff\x2f\x00"))
                digital.append(ogg)
        self.assertEqual(len(set(digital)), 3)

    def test_scores_are_deterministic_and_fit_loop(self):
        for _, _, _, root, seed in TRACKS:
            notes = score(root, seed)
            self.assertEqual(notes, score(root, seed))
            self.assertEqual({note[4] for note in notes}, {0, 1, 2, 9})
            for beat, duration, pitch, velocity, _ in notes:
                self.assertGreaterEqual(beat, 0)
                self.assertLessEqual(beat + duration, BARS * 4)
                self.assertTrue(0 <= pitch <= 127 and 0 < velocity <= 127)

    def test_encoded_tracks_decode_with_correct_duration_and_headroom(self):
        ffmpeg = shutil.which("ffmpeg")
        self.assertIsNotNone(ffmpeg, "FFmpeg is required for soundtrack verification")
        for map_name, _, bpm, _, _ in TRACKS:
            with self.subTest(map=map_name):
                result = subprocess.run(
                    [ffmpeg, "-hide_banner", "-loglevel", "error", "-i",
                     str(MUSIC_DIR / f"{map_name}.ogg"), "-f", "f32le",
                     "-ar", str(RATE), "-ac", "2", "pipe:1"],
                    check=True, capture_output=True,
                )
                audio = np.frombuffer(result.stdout, dtype="<f4").reshape(-1, 2)
                self.assertTrue(np.all(np.isfinite(audio)))
                self.assertAlmostEqual(len(audio) / RATE, BARS * 4 * 60 / bpm, delta=0.03)
                self.assertLess(np.max(np.abs(audio)), 0.98)
                self.assertGreater(np.sqrt(np.mean(audio ** 2)), 0.06)
                self.assertLess(abs(float(audio.mean())), 0.01)
                self.assertGreater(np.std(audio[:, 0] - audio[:, 1]), 0.005)
                seam = np.max(np.abs(audio[0] - audio[-1]))
                self.assertLess(seam, 0.12)


if __name__ == "__main__":
    unittest.main()
