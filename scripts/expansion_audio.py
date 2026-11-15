import math
import random

from expansion_cast import NEW_ENEMIES
from paintball_audio import SAMPLE_RATE, _encode_dmx


# Pitch, harmonic colour, syllables: original stylized calls, not field recordings.
VOICES = {
    "BVER": (180, 0.30, 3), "RFOX": (660, 0.22, 2),
    "GOOS": (310, 0.60, 2), "CHIP": (1150, 0.18, 5),
    "BJAY": (910, 0.32, 3), "GHOG": (210, 0.25, 2),
    "SOWL": (270, 0.12, 2), "WOLV": (130, 0.55, 3),
    "BLSQ": (1280, 0.20, 4), "STAG": (155, 0.40, 1),
    "SWAN": (420, 0.38, 2), "OTTR": (780, 0.24, 4),
}
REACTIONS = ("alert", "hit", "out", "idle")
NEW_SOUND_SPECS = tuple(
    (f"DSFRE{slot - 500:03}", f"{enemy.prefix}_{reaction}",
     {"alert": 0.42, "hit": 0.24, "out": 0.50, "idle": 0.28}[reaction],
     slot + 91)
    for enemy in NEW_ENEMIES for slot, reaction in zip(enemy.sounds, REACTIONS)
)


def synthesize_voice(kind, duration, seed):
    prefix, reaction = kind.split("_")
    pitch, colour, syllables = VOICES[prefix]
    rng = random.Random(seed)
    phase = 0.0
    low = 0.0
    samples = []
    count = round(duration * SAMPLE_RATE)
    for i in range(count):
        t = i / SAMPLE_RATE
        p = i / (count - 1)
        frequency = pitch * (1 + 0.13 * math.sin(2 * math.pi * p))
        if reaction == "out":
            frequency *= 1 - 0.32 * p
        elif reaction == "idle":
            frequency *= 0.77
        elif reaction == "hit":
            frequency *= 1.15 - 0.25 * p
        phase += 2 * math.pi * frequency / SAMPLE_RATE
        low += 0.22 * (rng.uniform(-1, 1) - low)
        voice = math.sin(phase) + colour * math.sin(2 * phase) + 0.08 * math.sin(3 * phase)
        pulse = 0.45 + 0.55 * (0.5 + 0.5 * math.sin(2 * math.pi * syllables * p)) ** 2
        value = (0.35 * voice * pulse + 0.12 * low) * math.sin(math.pi * p) ** 1.4
        if reaction == "hit":
            value += 0.3 * low * math.exp(-t / 0.028)
        samples.append(value)
    return _encode_dmx(samples)


def expansion_sound_lumps():
    return [(name, synthesize_voice(kind, duration, seed))
            for name, kind, duration, seed in NEW_SOUND_SPECS]
