import math
import random
import struct


SAMPLE_RATE = 11025

# These are existing sound slots used only by actors absent from our maps.
ACTOR_SOUNDS = (
    (2, {"Alert sound": 43, "Pain sound": 29, "Death sound": 66, "Action sound": 77}),
)
SOUND_SPECS = (
    ("DSPISTOL", "marker", 0.18, 1),
    ("DSSHOTGN", "scatter", 0.24, 2),
    ("DSCHGUN", "marker", 0.15, 3),
    ("DSSGCOCK", "pump", 0.26, 4),
    ("DSVIPAIN", "drone_hit", 0.25, 5),
    ("DSMNPAIN", "raccoon_hit", 0.28, 6),
    ("DSCACDTH", "drone_out", 0.42, 7),
    ("DSSKLDTH", "raccoon_out", 0.44, 8),
    ("DSCACSIT", "drone_alert", 0.32, 9),
    ("DSBRSSIT", "raccoon_alert", 0.32, 10),
    ("DSBGACT", "drone_idle", 0.23, 11),
    ("DSDMACT", "raccoon_idle", 0.27, 12),
    ("DSSGTATK", "swish", 0.18, 13),
    ("DSSLOP", "splat", 0.24, 14),
    ("DSPLPAIN", "tap", 0.18, 15),
    ("DSPLDETH", "tag_out", 0.35, 16),
    ("DSPDIEHI", "tag_out", 0.38, 17),
    ("DSPUNCH", "tap", 0.16, 18),
    ("DSOOF", "tap", 0.12, 19),
    ("DSTINK", "splat", 0.14, 20),
    ("DSPLASMA", "starter", 0.22, 21),
    ("DSDMPAIN", "skeleton_hit", 0.24, 22),
    ("DSBRSDTH", "skeleton_out", 0.46, 23),
    ("DSCYBSIT", "skeleton_alert", 0.34, 24),
    ("DSBSPACT", "skeleton_idle", 0.26, 25),
    ("DSPEPAIN", "bear_hit", 0.30, 26),
    ("DSCYBDTH", "bear_out", 0.50, 27),
    ("DSSPISIT", "bear_alert", 0.38, 28),
    ("DSBSPWLK", "bear_idle", 0.32, 29),
    ("DSBSPSIT", "pigeon_alert", 0.36, 30),
    ("DSPOPAIN", "pigeon_hit", 0.22, 31),
    ("DSSPIDTH", "pigeon_out", 0.44, 32),
    ("DSVILACT", "pigeon_idle", 0.30, 33),
    ("DSKNTSIT", "armour_alert", 0.40, 34),
    ("DSSKEPCH", "armour_hit", 0.24, 35),
    ("DSBSPDTH", "armour_out", 0.50, 36),
    ("DSHOOF", "armour_idle", 0.28, 37),
    ("DSVILSIT", "wolf_alert", 0.42, 38),
    ("DSVILATK", "wolf_hit", 0.25, 39),
    ("DSVILDTH", "wolf_out", 0.48, 40),
    ("DSMETAL", "wolf_idle", 0.32, 41),
)


def _encode_dmx(samples):
    peak = max(abs(value) for value in samples)
    if not peak:
        raise ValueError("Cannot encode silent paintball audio")
    pcm = bytes(round(128 + 96 * value / peak) for value in samples)
    # DMX expects unsigned 8-bit mono with sixteen guard samples at both ends.
    guarded = bytes([128]) * 16 + pcm + bytes([128]) * 16
    return struct.pack("<HHI", 3, SAMPLE_RATE, len(guarded)) + guarded


def synthesize_sound(kind, duration, seed):
    rng = random.Random(seed)
    count = round(duration * SAMPLE_RATE)
    samples = []
    phase = 0.0
    low_noise = 0.0
    for index in range(count):
        t = index / SAMPLE_RATE
        progress = index / (count - 1)
        noise = rng.uniform(-1, 1)
        low_noise += 0.32 * (noise - low_noise)
        fade = min(1.0, t / 0.004) * min(1.0, (duration - t) / 0.018)
        if kind == "starter":
            phase += 2 * math.pi * (125 + 430 * math.exp(-t / 0.007)) / SAMPLE_RATE
            crack = (noise - low_noise) * math.exp(-t / 0.009)
            body = math.sin(phase) * math.exp(-t / 0.038)
            air = low_noise * math.exp(-t / 0.027)
            bolt = noise * math.exp(-((t - 0.060) / 0.004) ** 2)
            reseat = low_noise * math.exp(-((t - 0.100) / 0.007) ** 2)
            value = 0.42 * crack + 0.65 * body + 0.45 * air + 0.24 * bolt + 0.18 * reseat
        elif kind in ("marker", "scatter"):
            decay = 0.032 if kind == "marker" else 0.05
            phase += 2 * math.pi * (180 + 500 * math.exp(-t / 0.008)) / SAMPLE_RATE
            air = (0.65 * noise + 0.35 * low_noise) * math.exp(-t / decay)
            body = math.sin(phase) * math.exp(-t / 0.028)
            latch = noise * math.exp(-((t - 0.055) / 0.006) ** 2)
            value = 0.5 * air + 0.45 * body + 0.12 * latch
        elif kind.startswith("drone_"):
            reaction = kind.split("_", 1)[1]
            frequency = 650 + 200 * math.sin(2 * math.pi * 3 * progress)
            if reaction == "out":
                frequency *= 1 - 0.8 * progress
            phase += 2 * math.pi * frequency / SAMPLE_RATE
            value = (0.32 * math.sin(phase) + 0.12 * low_noise) * math.sin(math.pi * progress) ** 1.4
        elif kind.startswith("skeleton_"):
            phase += 2 * math.pi * (390 + 180 * math.exp(-t / 0.04)) / SAMPLE_RATE
            clicks = sum(math.exp(-((t - point) / 0.012) ** 2)
                         for point in (0.025, duration * 0.35, duration * 0.68))
            value = (0.55 * low_noise + 0.20 * math.sin(phase)) * clicks
        elif kind.startswith("armour_"):
            phase += 2 * math.pi * 710 / SAMPLE_RATE
            pulse = sum(math.exp(-((t - point) / 0.018) ** 2)
                        for point in (0.025, duration * 0.4, duration * 0.75))
            value = (0.35 * math.sin(phase) + 0.18 * math.sin(phase * 1.43)
                     + 0.35 * low_noise) * pulse
        elif kind.startswith("pigeon_"):
            phase += 2 * math.pi * (310 + 85 * math.sin(2 * math.pi * progress)) / SAMPLE_RATE
            pulse = (0.65 + 0.35 * math.sin(6 * math.pi * progress))
            value = (0.45 * math.sin(phase) + 0.09 * low_noise) * pulse * math.sin(math.pi * progress) ** 1.4
        elif kind.startswith("wolf_"):
            phase += 2 * math.pi * (390 + 240 * math.sin(math.pi * progress)) / SAMPLE_RATE
            value = (0.36 * math.sin(phase) + 0.12 * math.sin(2 * phase)
                     + 0.12 * low_noise) * math.sin(math.pi * progress) ** 1.4
        elif kind.startswith("bear_"):
            phase += 2 * math.pi * (105 + 45 * math.sin(math.pi * progress)) / SAMPLE_RATE
            voice = math.sin(phase) + 0.35 * math.sin(2 * phase) + 0.15 * math.sin(3 * phase)
            value = (0.38 * voice + 0.26 * low_noise) * math.sin(math.pi * progress) ** 1.4
        elif kind == "pump":
            slide = math.sin(math.pi * progress) ** 2
            clicks = math.exp(-((t - 0.025) / 0.006) ** 2)
            clicks += math.exp(-((t - duration + 0.035) / 0.007) ** 2)
            value = 0.38 * low_noise * slide + 0.24 * noise * clicks
        elif kind.startswith(("coyote_", "raccoon_")):
            coyote = kind.startswith("coyote_")
            reaction = kind.split("_", 1)[1]
            frequency = (
                480 + 620 * math.sin(math.pi * progress) - 120 * progress
                if coyote else 730 + 210 * math.sin(2 * math.pi * progress)
            )
            if reaction == "out":
                frequency *= 1 - 0.35 * progress
            elif reaction == "idle":
                frequency *= 0.7
            phase += 2 * math.pi * frequency / SAMPLE_RATE
            harmonics = math.sin(phase) + 0.3 * math.sin(2 * phase) + 0.12 * math.sin(3 * phase)
            syllables = 2 if coyote else 4
            pulse = (0.5 + 0.5 * math.sin(2 * math.pi * syllables * progress)) ** 2
            voice = harmonics * (0.45 + 0.55 * pulse) if coyote else harmonics * pulse
            envelope = math.sin(math.pi * progress) ** 1.4
            value = (0.36 * voice + 0.12 * low_noise) * envelope
            if reaction == "hit":
                value += 0.3 * low_noise * math.exp(-t / 0.025)
        elif kind in ("splat", "tap", "swish", "tag_out"):
            phase += 2 * math.pi * (140 - 70 * progress) / SAMPLE_RATE
            if kind == "swish":
                value = low_noise * math.sin(math.pi * progress) ** 2
            elif kind == "tag_out":
                value = 0.3 * low_noise * math.sin(math.pi * progress)
            else:
                decay = 0.05 if kind == "splat" else 0.025
                value = (0.65 * low_noise + 0.2 * math.sin(phase)) * math.exp(-t / decay)
        else:
            raise ValueError(f"Unknown paintball sound kind: {kind}")
        samples.append(value * fade)
    return _encode_dmx(samples)


def sound_lumps():
    return [(name, synthesize_sound(kind, duration, seed)) for name, kind, duration, seed in SOUND_SPECS]
