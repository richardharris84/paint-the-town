import unittest
import shutil
import subprocess

import numpy as np

from campaign_order import STOPS, SOURCE_TO_SLOT
from expansion_music import (
    CAMPAIGN_TRACKS, STYLES, PRESENTATION_MUSIC, MUSIC_DIR, beats_per_bar,
    campaign_score, programs_for, campaign_music_lumps, soundtrack_provenance,
)
from toronto_music import BARS, RATE, midi_bytes


class CampaignMusicTests(unittest.TestCase):
    def test_requested_venue_styles_are_not_assigned_by_historical_map_number(self):
        expected = (
            "choral_hiphop", "funk_rock", "hyphy", "city_anthem", "boom_bap",
            "glam_stomp", "ballpark_waltz", "southern_rap", "playful_hiphop",
        )
        self.assertEqual(tuple(STYLES[stop.source] for stop in STOPS), expected)
        self.assertEqual({track[0] for track in CAMPAIGN_TRACKS}, set(SOURCE_TO_SLOT))
        self.assertEqual(len({track[1] for track in CAMPAIGN_TRACKS}), 9)

    def test_all_nine_scores_are_deterministic_bounded_and_instrumented(self):
        scores = []
        for source, title, bpm, _, _ in CAMPAIGN_TRACKS:
            with self.subTest(source=source):
                notes = campaign_score(source)
                self.assertEqual(notes, campaign_score(source))
                self.assertGreater(len(notes), 300)
                programs = programs_for(source)
                for beat, duration, pitch, velocity, channel in notes:
                    self.assertTrue(0 <= beat < beat + duration <= BARS * beats_per_bar(source))
                    self.assertTrue(0 <= pitch <= 127 and 0 < velocity <= 127)
                    self.assertIn(channel, {*programs, 9})
                midi = midi_bytes(notes, bpm, title, programs=programs,
                                  beats_per_bar=beats_per_bar(source))
                for channel, program in programs.items():
                    self.assertIn(bytes((0xC0 | channel, program)), midi)
                self.assertTrue(midi.endswith(b"\xff\x2f\x00"))
                scores.append(tuple(notes))
        self.assertEqual(len(set(scores)), 9)

    def test_styles_have_distinctive_instrumentation_and_ballpark_meter(self):
        self.assertIn(10, programs_for("E1M2"))
        self.assertIn(3, programs_for("E1M8"))
        self.assertIn(6, programs_for("E1M4"))
        self.assertIn(5, programs_for("E1M5"))
        self.assertIn(8, programs_for("E1M1"))
        self.assertIn(3, programs_for("E1M7"))
        self.assertIn(7, programs_for("E1M9"))
        self.assertIn(2, programs_for("E1M3"))
        self.assertEqual(beats_per_bar("E1M6"), 3)
        self.assertTrue(all(beats_per_bar(source) == 4 for source in STYLES if source != "E1M6"))
        melody = [(beat, pitch) for beat, _, pitch, velocity, channel in campaign_score("E1M6")
                  if channel == 4 and velocity == 69]
        self.assertEqual(melody[:4], [(0, 55), (.5, 52), (1, 57), (2, 55)])
        self.assertNotEqual([pitch for _, pitch in melody[:7]], [60, 72, 69, 67, 64, 67, 62])

    def test_mellow_register_tempo_and_percussion_limits(self):
        for source, _, bpm, _, _ in CAMPAIGN_TRACKS:
            self.assertLessEqual(bpm, 96)
            notes = campaign_score(source)
            self.assertLessEqual(max(pitch for _, _, pitch, _, channel in notes if channel != 9), 67)
            self.assertLessEqual(max(velocity for _, _, _, velocity, channel in notes if channel == 9), 76)
            self.assertLessEqual(max(velocity for _, _, _, velocity, channel in notes if channel != 9), 69)

    def test_mellow_encoded_audio_has_headroom_and_limited_high_frequency_energy(self):
        ffmpeg = shutil.which("ffmpeg")
        self.assertIsNotNone(ffmpeg, "FFmpeg is required for soundtrack verification")
        for source, _, bpm, _, _ in CAMPAIGN_TRACKS:
            with self.subTest(source=source):
                result = subprocess.run(
                    [ffmpeg, "-hide_banner", "-loglevel", "error", "-i",
                     str(MUSIC_DIR / f"{source}.ogg"), "-f", "f32le",
                     "-ar", str(RATE), "-ac", "2", "pipe:1"],
                    check=True, capture_output=True)
                audio = np.frombuffer(result.stdout, dtype="<f4").reshape(-1, 2)
                self.assertTrue(np.all(np.isfinite(audio)))
                self.assertAlmostEqual(len(audio) / RATE, BARS * beats_per_bar(source) * 60 / bpm, delta=.03)
                self.assertLess(np.max(np.abs(audio)), .8)
                self.assertGreater(np.sqrt(np.mean(audio ** 2)), .06)
                self.assertLess(np.max(np.abs(audio[0] - audio[-1])), .12)
                mono = audio.mean(axis=1)
                power = np.abs(np.fft.rfft(mono)) ** 2
                frequency = np.fft.rfftfreq(len(mono), 1 / RATE)
                self.assertLess(power[frequency > 2000].sum() / power.sum(), .001)

    def test_all_music_is_original_project_output_with_hash_bound_provenance(self):
        import hashlib
        import json
        provenance = soundtrack_provenance()
        self.assertEqual(json.loads((MUSIC_DIR / "provenance.json").read_text()), provenance)
        self.assertEqual(len(provenance), 9)
        for row in provenance:
            self.assertFalse(row["commercial_samples"])
            self.assertFalse(row["third_party_compositions"])
            self.assertFalse(row["external_soundfonts"])
            self.assertEqual(row["external_audio_assets"], [])
            self.assertFalse(row["third_party_music_license_required"])
            self.assertFalse(row["third_party_music_royalties_required"])
            for extension, digest in row["sha256"].items():
                self.assertEqual(digest, hashlib.sha256(
                    (MUSIC_DIR / f"{row['source_id']}.{extension}").read_bytes()).hexdigest())

    def test_stock_presentation_music_is_replaced_in_every_audio_mode(self):
        lumps = dict(campaign_music_lumps())
        self.assertEqual(len(lumps), (9 + len(PRESENTATION_MUSIC)) * 3)
        for cue, source in PRESENTATION_MUSIC.items():
            for mode in ("D", "O", "H"):
                self.assertEqual(lumps[f"{mode}_{cue}"], lumps[f"{mode}_{source}"])


if __name__ == "__main__":
    unittest.main()
