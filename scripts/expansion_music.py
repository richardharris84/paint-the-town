"""Original venue-specific instrumentals; no commercial recordings or sampled riffs."""

import hashlib
import json

import numpy as np

from campaign_order import SOURCE_TO_SLOT, STOPS
from project_paths import MUSIC
from toronto_music import BARS, music_lumps as load_music_lumps, write_track


MUSIC_DIR = MUSIC / "paint_the_town"
CAMPAIGN_TRACKS = (
    ("E1M1", "Platform Cipher", 80, 41, 4101),
    ("E1M2", "Gates of Memory", 78, 45, 4102),
    ("E1M3", "Wildlife Midway", 84, 43, 4103),
    ("E1M4", "Square Bounce", 86, 38, 4104),
    ("E1M5", "Winter Borough Lights", 76, 43, 4105),
    ("E1M6", "Seventh-Inning Portal", 96, 36, 4106),
    ("E1M7", "Boardside Thunder", 92, 40, 4107),
    ("E1M8", "Legislature Voltage", 88, 40, 4108),
    ("E1M9", "Island Afterburn", 94, 38, 4109),
)
STYLES = {
    "E1M1": "boom_bap",
    "E1M2": "choral_hiphop",
    "E1M3": "playful_hiphop",
    "E1M4": "hyphy",
    "E1M5": "city_anthem",
    "E1M6": "ballpark_waltz",
    "E1M7": "glam_stomp",
    "E1M8": "funk_rock",
    "E1M9": "southern_rap",
}
PROGRAMS = {0: 33, 1: 89, 2: 11, 3: 26, 4: 16, 5: 60, 6: 4, 7: 33, 8: 4, 10: 52}
PRESENTATION_MUSIC = {
    "INTRO": "E1M2", "INTROA": "E1M2", "INTER": "E1M4",
    "VICTOR": "E1M5", "BUNNY": "E1M9",
}


def beats_per_bar(source):
    return 3 if STYLES[source] == "ballpark_waltz" else 4


def campaign_score(source):
    _, _, _, root, seed = next(track for track in CAMPAIGN_TRACKS if track[0] == source)
    style = STYLES[source]
    meter = beats_per_bar(source)
    end = BARS * meter
    rng = np.random.default_rng(seed)
    notes = []

    def note(beat, duration, pitch, velocity, channel):
        if not (0 <= beat < end and 0 <= pitch <= 127 and 0 < velocity <= 127):
            raise ValueError(f"{source}: invalid score event")
        if channel != 9:
            if channel not in (0, 7):
                pitch -= 12
            while pitch > 67:
                pitch -= 12
            velocity = max(1, round(velocity * .75))
        else:
            velocity = max(1, round(velocity * (.55 if pitch in (42, 46, 49, 76) else .7)))
        notes.append((beat, min(duration, end - beat), pitch, velocity, channel))

    if style == "ballpark_waltz":
        # Original organ melody; no borrowed ballpark-song refrain.
        opening = (
            ((67, .5), (64, .5), (69, 1), (67, 1)),
            ((72, .75), (71, .75), (67, 1.5)),
            ((69, 1), (74, .5), (71, .5), (67, 1)),
            ((65, 1.5), (62, .5), (67, 1)),
            ((64, .5), (67, 1), (72, .5), (69, 1)),
            ((67, .5), (71, .5), (74, 1), (72, 1)),
            ((69, .75), (65, .75), (72, 1.5)),
            ((71, 1), (67, .5), (62, .5), (64, 1)),
        )
        bridge = (
            ((69, 1), (68, 1), (69, 1)), ((64, 1), (65, 1), (67, 1)),
            ((69, 2), (65, 1)), ((62, 3),),
            ((65, 1), (69, 1), (72, 1)), ((71, 1), (69, 1), (67, 1)),
            ((62, 1), (67, 1), (71, 1)), ((72, 3),),
        )
        for bar in range(BARS):
            base = bar * 3
            chord = (0, 0, 7, 7, 0, 0, 5, 7)[bar % 8]
            note(base, .65, root + chord, 85, 0)
            for beat in (1, 2):
                for interval in (4, 7, 12):
                    note(base + beat, .45, root + 12 + chord + interval, 48, 4)
            cursor = base
            for pitch, duration in (opening + bridge)[bar % 16]:
                note(cursor, duration * .9, pitch, 92, 4)
                cursor += duration
            note(base, .12, 36, 78, 9)
            for beat in (1, 2):
                note(base + beat, .08, 42, 42, 9)
        return notes

    progressions = {
        "choral_hiphop": (0, 5, 1, 7), "funk_rock": (0, 0, 3, 10),
        "hyphy": (0, 0, 5, 3), "city_anthem": (0, 8, 5, 10),
        "boom_bap": (0, 3, -2, 5), "glam_stomp": (0, 5, 10, 7),
        "southern_rap": (0, 0, 3, 5), "playful_hiphop": (0, 5, 9, 7),
    }
    rock = style in {"funk_rock", "glam_stomp"}
    for bar in range(BARS):
        base = bar * 4
        transpose = progressions[style][(bar // 2) % 4]
        tonic = root + transpose
        breakdown = 16 <= bar < 20
        kick = ((0, 1, 2, 3) if style == "glam_stomp" else
                (0, .75, 2, 2.75, 3.5) if style == "funk_rock" else
                (0, 1.5, 2.75) if style == "hyphy" else
                (0, 1.75, 3.25) if style == "southern_rap" else
                (0, 1.5, 2.5))
        for beat in kick[:1] if breakdown else kick:
            note(base + beat, .2, 36, 108 if beat == 0 else 88, 9)
        if not breakdown:
            for beat in (1, 3):
                note(base + beat + (0 if rock else .025), .14,
                     39 if style == "hyphy" else 38, 106 if rock else 94, 9)
                if style == "glam_stomp":
                    note(base + beat, .16, 39, 82, 9)
            steps = 16 if style == "southern_rap" else 8
            for step in range(steps):
                swing = .06 if style == "boom_bap" and step % 2 else 0
                note(base + step * 4 / steps + swing, .06, 42,
                     int(rng.integers(38, 72)), 9)
            if rock and bar % 8 == 0:
                note(base, .7, 49, 88, 9)
            if bar % 8 == 7:
                for index, drum in enumerate((45, 43, 41)):
                    note(base + 3 + index / 3, .15, drum, 82, 9)
        if style == "funk_rock":
            riff = ((0, .3, 0), (.75, .2, 12), (1.25, .35, 10),
                    (2, .3, 0), (2.75, .25, 3), (3.5, .25, 7))
        elif style == "glam_stomp":
            riff = ((0, .65, 0), (1, .35, 7), (1.75, .3, 10),
                    (2.5, .35, 3), (3.25, .5, 5))
        elif style == "hyphy":
            riff = ((0, .4, 0), (1.125, .25, 0), (2, .3, 7), (3.25, .4, 12))
        elif style == "southern_rap":
            riff = ((0, 1.2, 0), (1.75, .55, 0), (2.75, .9, 7))
        else:
            riff = ((0, .7, 0), (1.5, .35, 7), (2.5, .65, 3), (3.5, .3, 10))
        for beat, duration, interval in riff[:2] if breakdown else riff:
            note(base + beat, duration, tonic + interval, 92,
                 7 if style == "southern_rap" else 0)
            if rock:
                for harmonic in (12, 19):
                    note(base + beat, duration * .8, tonic + harmonic, 82, 3)
        if style == "choral_hiphop":
            if bar % 2 == 0:
                for interval in (0, 3, 7):
                    note(base + .25, 6.8, tonic + 24 + interval, 53, 10)
            for beat, interval in ((.75, 19), (2.25, 15), (3.5, 22)):
                if not breakdown:
                    note(base + beat, .35, tonic + 24 + interval, 49, 8)
        elif style == "boom_bap":
            for beat in (.5, 2.25):
                for interval in (3, 7, 10, 14):
                    note(base + beat, .5, tonic + 24 + interval, 49, 8)
        elif style == "city_anthem":
            for beat, duration in ((.5, .55), (2.75, .7)):
                for interval in (0, 3, 7):
                    note(base + beat, duration, tonic + 24 + interval, 68, 5)
        elif style == "hyphy":
            for beat, interval in ((.5, 24), (1.75, 31), (2.5, 27), (3.5, 34)):
                if not breakdown:
                    note(base + beat, .18, tonic + interval, 72, 6)
            if bar % 2:
                note(base + 2.75, .1, 76, 64, 9)
        elif style == "southern_rap":
            for beat, interval in ((.75, 31), (1.5, 27), (2.75, 24)):
                if not breakdown:
                    note(base + beat, .3, tonic + interval, 71, 3)
        elif style == "playful_hiphop":
            for beat, interval in ((.5, 24), (1.25, 28), (2.5, 31), (3.25, 26)):
                if not breakdown:
                    note(base + beat, .24, tonic + interval, 65, 2)
            if bar % 2 == 0:
                for interval in (4, 7, 11):
                    note(base, 1.6, tonic + 24 + interval, 39, 8)
        elif style == "glam_stomp" and bar % 2 == 0:
            for interval in (0, 7, 12):
                note(base + .5, 1.25, tonic + 24 + interval, 43, 4)
    return notes


def programs_for(source):
    channels = {row[4] for row in campaign_score(source)} - {9}
    return {channel: PROGRAMS[channel] for channel in sorted(channels)}


def campaign_music_lumps():
    expected = soundtrack_provenance()
    if json.loads((MUSIC_DIR / "provenance.json").read_text()) != expected:
        raise ValueError("Soundtrack provenance or file hashes differ; regenerate the soundtrack")
    lumps = load_music_lumps(CAMPAIGN_TRACKS, MUSIC_DIR)
    assets = dict(lumps)
    lumps.extend((f"{mode}_{cue}", assets[f"{mode}_{source}"])
                 for cue, source in PRESENTATION_MUSIC.items() for mode in ("D", "O", "H"))
    return lumps


def soundtrack_provenance():
    provenance = []
    for source, title, bpm, _, _ in CAMPAIGN_TRACKS:
        slot = SOURCE_TO_SLOT[source]
        provenance.append(dict(
            map=slot, venue=STOPS[int(slot[-1]) - 1].title, title=title,
            source_id=source, bpm=bpm, beats_per_bar=beats_per_bar(source),
            bars=BARS, style=STYLES[source],
            arrangement="Mellow revision: lower register, softened leads and percussion",
            melodic_pitch_ceiling=67, synthesis="Warm sine-led voices; smoothed percussion",
            provenance="Original project composition and mathematical synthesis; no borrowed melody or recording",
            commercial_samples=False, third_party_compositions=False,
            external_audio_assets=[], external_soundfonts=False,
            third_party_music_license_required=False, third_party_music_royalties_required=False,
            ownership="AI-assisted project output; exclusive copyright ownership is not certified",
            sha256={extension: hashlib.sha256((MUSIC_DIR / f"{source}.{extension}").read_bytes()).hexdigest()
                    for extension in ("mid", "ogg")}))
    return provenance


def build():
    for source, title, bpm, _, seed in CAMPAIGN_TRACKS:
        write_track(source, title, bpm, campaign_score(source), seed, MUSIC_DIR,
                    programs=programs_for(source), beats_per_bar=beats_per_bar(source),
                    drone_level=.015 if STYLES[source] == "choral_hiphop" else 0,
                    mellow=True)
    provenance = soundtrack_provenance()
    (MUSIC_DIR / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")


if __name__ == "__main__":
    build()
