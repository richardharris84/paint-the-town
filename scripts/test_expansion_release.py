import hashlib
import re
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from build_expansion import CANDIDATE, ROOT, campaign_mapinfo, validate_candidate, validate_resources, _doom_iwad
from doom_geometry import read_wad
from expansion_audio import NEW_SOUND_SPECS, expansion_sound_lumps
from expansion_music import (
    CAMPAIGN_TRACKS, MUSIC_DIR, PRESENTATION_MUSIC, campaign_score, beats_per_bar, programs_for,
)
from expansion_presentation import CAMPAIGN_SKIES, candidate_material_images
from toronto_music import BARS, RATE, midi_bytes
from expansion_cast import CAMPAIGN_ENEMIES
from campaign_feedback import PAINTBALL_CLIP
from toronto_venues import venue_specs
from campaign_order import remap_resource
from project_paths import RELEASE
from build_expansion import (
    publication_inputs, publish_kex_candidate, verify_kex_startup_evidence,
    verify_union_stability_evidence,
)


class ExpansionReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lumps = read_wad(CANDIDATE)
        cls.assets = dict(cls.lumps)

    def test_candidate_passes_full_validation(self):
        self.assertEqual(validate_candidate(CANDIDATE)[0], len(self.lumps))

    def test_new_game_offers_exactly_one_campaign_episode(self):
        info = campaign_mapinfo(venue_specs()).decode("ascii")
        first = info.split("map E1M2\n")[0]
        self.assertIn("episode = clear", first)
        self.assertIn('episode = "M_EPI1", "Paint the Town", "p"', first)
        self.assertEqual(info.count("episode = clear"), 1)
        self.assertEqual(info.count('episode = "'), 1)

    def test_campaign_infrastructure_thing_numbers_are_defined_once(self):
        # Base-NPC modifications legitimately repeat low thing numbers; every
        # campaign-added definition (tips, walkers, portals, girls) must be
        # unique or later patch sections silently overwrite earlier ones.
        dehacked = self.assets["DEHACKED"].decode("ascii", errors="replace")
        added = [int(n) for n in re.findall(r"(?m)^Thing (\d+)$", dehacked) if int(n) >= 180]
        self.assertEqual(sorted(set(added)), sorted(added))

    def test_conflicting_directional_art_cannot_override_a_zoo_npc_billboard(self):
        end = next(index for index, (name, _) in enumerate(self.lumps) if name == "S_END")
        conflicting = [*self.lumps[:end], ("BEARA1", self.assets["BEARA0"]), *self.lumps[end:]]
        with self.assertRaisesRegex(ValueError, "mixes billboard and directional"):
            validate_resources(conflicting, _doom_iwad())

    def test_verified_fallback_is_preserved(self):
        expected = "902be83dd2d04caebabbd309823ac90363216d2c362c8b4dffa7f428d9c766a9"
        backup = ROOT / "Toronto_Realms_three_map_backup.wad"
        self.assertEqual(hashlib.sha256(backup.read_bytes()).hexdigest(), expected)

    def test_published_campaign_matches_validated_candidate(self):
        release = RELEASE
        self.assertEqual(hashlib.sha256(release.read_bytes()).hexdigest(),
                         hashlib.sha256(CANDIDATE.read_bytes()).hexdigest())
        self.assertEqual(validate_candidate(release), validate_candidate(CANDIDATE))

    def test_publication_rejects_protected_paths(self):
        for path in (CANDIDATE, ROOT / "Toronto_Realms.wad",
                     ROOT / "Toronto_Realms_three_map_backup.wad"):
            with self.subTest(path=path):
                with self.assertRaisesRegex(ValueError, "Never overwrite"):
                    publication_inputs(path)

    def test_union_stability_gate_rejects_stale_incomplete_or_frozen_evidence(self):
        proof = dict(
            wad_sha256="fixture", elapsed_seconds=120,
            simulation_tics=[0, 1000, 2000, 3000, 4200],
            checks=dict(commuters_present=True, commuters_static=True,
                        commuter_animation=True, nathan_to_union=True,
                        save_load=True, extended_play=True))
        verify_union_stability_evidence("fixture", proof)
        for invalid in (
            {**proof, "wad_sha256": "stale"},
            {**proof, "elapsed_seconds": 119},
            {**proof, "simulation_tics": [0, 1000, 2000, 2000, 2000]},
            {**proof, "simulation_tics": [0, 1, 2, 3, 4]},
            {**proof, "simulation_tics": [0, 1000, 2000, 3000, 4199]},
            {**proof, "simulation_tics": [0]},
            {**proof, "checks": {**proof["checks"], "commuters_static": False}},
            {**proof, "checks": {key: value for key, value in proof["checks"].items()
                                 if key != "commuter_animation"}},
        ):
            with self.assertRaisesRegex(ValueError, "Union stability"):
                verify_union_stability_evidence("fixture", invalid)

    def test_limited_publication_records_scoped_evidence_and_rejects_stale_reports(self):
        import json
        payload = b"validated candidate"
        digest = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / "runtime_validation"
            directory.mkdir()
            (directory / "runtime-results.json").write_text("[]")
            proof_path = directory / "union-stability-results.json"
            proof_path.write_text(json.dumps({"wad_sha256": digest}))
            release = root / "release.wad"

            def replace(path, lumps, validator):
                path.write_bytes(payload)
                return 1, len(payload)

            with patch("build_expansion.ROOT", root), \
                    patch("build_expansion.publication_inputs", return_value=digest), \
                    patch("build_expansion.verify_kex_startup_evidence", return_value={}), \
                    patch("doom_geometry.read_wad", return_value=[]), \
                    patch("build_expansion.replace_validated", side_effect=replace) as replace_mock:
                publish_kex_candidate(release)
                report_path = directory / "kex-publication.json"
                report = json.loads(report_path.read_text())
                self.assertEqual(report["wad_sha256"], digest)
                self.assertFalse(report["full_feature_acceptance"])
                self.assertEqual(report["native_reports_sha256"], {
                    proof_path.name: hashlib.sha256(proof_path.read_bytes()).hexdigest(),
                })
                self.assertTrue(any("typography" in item for item in report["unverified"]))
                self.assertEqual(release.read_bytes(), payload)
                proof_path.write_text(json.dumps({"wad_sha256": "stale"}))
                with self.assertRaisesRegex(ValueError, "does not match"):
                    publish_kex_candidate(release)
                self.assertEqual(replace_mock.call_count, 1)
                self.assertEqual(json.loads(report_path.read_text()), report)

    def test_kex_publication_requires_all_current_maps_and_clean_native_logs(self):
        digest = hashlib.sha256(CANDIDATE.read_bytes()).hexdigest()
        rows = [dict(map=f"E1M{n}", title=f"Venue {n}", wad_sha256=digest,
                     startup_and_music="passed") for n in range(1, 10)]
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for row in rows:
                text = "\n".join((
                    f"adding {CANDIDATE.name}", f"{row['map']}: {row['title']}",
                    f"Playing 'D_{row['map']}.ogg'",
                    "P_SetupLevel: Using limit-removing structures",
                ))
                (directory / f"{row['map']}-stdout.txt").write_text(text)
            self.assertEqual(len(verify_kex_startup_evidence(digest, rows, directory)), 9)
            for invalid in (rows[:-1], [*rows[:-1], rows[0]],
                            [{**row, "wad_sha256": "stale"} for row in rows],
                            [{**row, "startup_and_music": "failed"} for row in rows]):
                with self.assertRaisesRegex(ValueError, "checksum-matched"):
                    verify_kex_startup_evidence(digest, invalid, directory)
            log = directory / "E1M9-stdout.txt"
            original = log.read_text()
            for text in ("unrelated log", original + "\nParse error",
                         original + "\nUnknown code pointer",
                         original + "\nGame-specific exception"):
                log.write_text(text)
                with self.assertRaisesRegex(ValueError, "KEX error"):
                    verify_kex_startup_evidence(digest, rows, directory)

    def test_retained_equipment_and_effects_match_fallback(self):
        from paintball_audio import SOUND_SPECS
        backup = dict(read_wad(ROOT / "Toronto_Realms_three_map_backup.wad"))
        names = {name for name in backup if name.startswith(("PISG", "SHTG", "CHGG"))}
        names.update(name for name, *_ in SOUND_SPECS)
        for name in names:
            with self.subTest(resource=name):
                self.assertEqual(self.assets[name], backup[name])

    def test_nine_distinct_skies_and_three_music_modes(self):
        walls, flats = candidate_material_images(_doom_iwad()["PLAYPAL"][:768])
        self.assertEqual(flats["PBFILL"].size, (64, 64))
        self.assertEqual(len(set(walls[name].tobytes() for name in CAMPAIGN_SKIES)), 9)
        self.assertTrue(all(walls[name].size == (1024, 128) for name in CAMPAIGN_SKIES))
        mixes = []
        for name, *_ in CAMPAIGN_TRACKS:
            ogg = (MUSIC_DIR / f"{name}.ogg").read_bytes()
            for mode in ("D", "O", "H"):
                self.assertEqual(self.assets[remap_resource(f"{mode}_{name}")], ogg)
            mixes.append(ogg)
        self.assertEqual(len(set(mixes)), 9)
        for cue, source in PRESENTATION_MUSIC.items():
            for mode in ("D", "O", "H"):
                self.assertEqual(self.assets[f"{mode}_{cue}"],
                                 self.assets[remap_resource(f"{mode}_{source}")])

    def test_missing_resource_fails_build_validation(self):
        broken = [(name, data) for name, data in self.lumps if name != "D_E1M9"]
        with self.assertRaisesRegex(ValueError, "Missing campaign music"):
            validate_resources(broken, _doom_iwad())

    def test_final_map_has_explicit_text_and_end_picture_without_self_loop(self):
        blocks = campaign_mapinfo(venue_specs()).decode("ascii").split("map E1M9\n")
        self.assertEqual(len(blocks), 2)
        final = blocks[1]
        for field in ('endpic = "TRVICTRY"', 'intertext = clear',
                      'intertextsecret = clear', 'intermusic = "D_E1M9"'):
            self.assertIn(field, final)
        # The campaign must end on the victory splash alone, without the
        # typewriter story screen between statistics and the end picture.
        self.assertNotIn('intertext = "', final)
        self.assertNotIn("interbackdrop", final)
        self.assertNotIn("endgame = true", final)
        self.assertNotIn("next =", final)
        self.assertNotIn("nextsecret =", final)
        # Widescreen victory splash: 560x200, auto-centred by the engines.
        self.assertEqual(struct.unpack_from("<4h", self.assets["TRVICTRY"]), (560, 200, 0, 0))
        from build_mod_previews import patch
        image = patch("TRVICTRY", self.assets)
        self.assertEqual(image.getchannel("A").getextrema(), (255, 255))
        colours = np.asarray(image.convert("RGB"))[:165].reshape(-1, 3)
        self.assertGreater(len(np.unique(colours, axis=0)), 100)
        self.assertLess(np.asarray(image.convert("RGB"))[170:, :].mean(), 100)

    def test_missing_victory_picture_fails_validation(self):
        broken = [(name, data) for name, data in self.lumps if name != "TRVICTRY"]
        with self.assertRaisesRegex(ValueError, "TRVICTRY"):
            validate_resources(broken, _doom_iwad())

    def test_pistol_start_ammunition_covers_encounter_health(self):
        health = {3004: 20, **{enemy.doomednum: enemy.health for enemy in CAMPAIGN_ENEMIES}}
        ammo = {2001: 2 * PAINTBALL_CLIP, 2002: 2 * PAINTBALL_CLIP,
                2007: PAINTBALL_CLIP, 2048: 5 * PAINTBALL_CLIP}
        map_name = None
        for name, payload in self.lumps:
            if name in {f"E1M{i}" for i in range(1, 10)}:
                map_name = name
            elif name == "THINGS":
                things = list(struct.iter_unpack("<5h", payload))
                for skill in (1, 2, 4):
                    with self.subTest(map=map_name, skill=skill):
                        active = [kind for _, _, _, kind, flags in things if flags & skill]
                        targets = sum(health.get(kind, 0) for kind in active)
                        # Expected stock hitscan damage; require twice total HP
                        # before relying on rival drops or the optional cache.
                        cache_box = 5 * PAINTBALL_CLIP
                        supply = 50 + sum(ammo.get(kind, 0) for kind in active) - cache_box
                        self.assertGreaterEqual(supply * 10, targets * 2)
                        self.assertFalse({2008, 2049} & set(active))
                        self.assertGreaterEqual(active.count(2012), 4)
                        self.assertIn(2018, active)

    def test_new_reactions_are_deterministic_and_clean_dmx(self):
        sounds = expansion_sound_lumps()
        self.assertEqual(sounds, expansion_sound_lumps())
        self.assertEqual(len(sounds), 48)
        self.assertEqual(len({data for _, data in sounds}), 48)
        for (name, data), (_, _, duration, _) in zip(sounds, NEW_SOUND_SPECS):
            with self.subTest(sound=name):
                self.assertEqual(self.assets[name], data)
                version, rate, count = struct.unpack_from("<HHI", data)
                self.assertEqual((version, rate, count), (3, 11025, len(data) - 8))
                samples = np.frombuffer(data[8:], dtype=np.uint8).astype(float) - 128
                self.assertLess(abs(float(samples.mean())), 2)
                self.assertGreater(np.sqrt(np.mean(samples ** 2)), 5)
                self.assertLess(np.max(np.abs(samples)), 126)
                self.assertTrue(np.all(samples[:16] == 0) and np.all(samples[-16:] == 0))
                self.assertAlmostEqual((count - 32) / rate, duration, delta=0.001)

    def test_new_scores_and_encoded_audio(self):
        ffmpeg = shutil.which("ffmpeg")
        self.assertIsNotNone(ffmpeg, "FFmpeg is required for soundtrack validation")
        for name, title, bpm, _, _ in CAMPAIGN_TRACKS:
            with self.subTest(map=name):
                notes = campaign_score(name)
                self.assertEqual(notes, campaign_score(name))
                meter = beats_per_bar(name)
                self.assertTrue(all(0 <= beat < beat + duration <= BARS * meter
                                    for beat, duration, *_ in notes))
                self.assertEqual((MUSIC_DIR / f"{name}.mid").read_bytes(),
                                 midi_bytes(notes, bpm, title, programs=programs_for(name),
                                            beats_per_bar=meter))
                result = subprocess.run(
                    [ffmpeg, "-hide_banner", "-loglevel", "error", "-i",
                     str(MUSIC_DIR / f"{name}.ogg"), "-f", "f32le",
                     "-ar", str(RATE), "-ac", "2", "pipe:1"],
                    check=True, capture_output=True,
                )
                audio = np.frombuffer(result.stdout, dtype="<f4").reshape(-1, 2)
                self.assertTrue(np.all(np.isfinite(audio)))
                self.assertAlmostEqual(len(audio) / RATE, BARS * meter * 60 / bpm, delta=0.03)
                self.assertLess(np.max(np.abs(audio)), 0.98)
                self.assertGreater(np.sqrt(np.mean(audio ** 2)), 0.06)
                self.assertLess(abs(float(audio.mean())), 0.01)
                self.assertLess(np.max(np.abs(audio[0] - audio[-1])), 0.12)


if __name__ == "__main__":
    unittest.main()
