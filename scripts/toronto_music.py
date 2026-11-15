import argparse
import math
import shutil
import struct
import subprocess
from pathlib import Path

import numpy as np


from project_paths import ROOT, MUSIC

MUSIC_DIR = MUSIC
RATE = 24000
BARS = 32
TRACKS = (
    ("E1M1", "Concourse After Dark", 96, 38, 101),
    ("E1M2", "Concrete and Glass", 88, 41, 202),
    ("E1M3", "Ravine Circuit", 102, 36, 303),
)


def _variable_length(value):
    result = [value & 127]
    while value >> 7:
        value >>= 7
        result.insert(0, (value & 127) | 128)
    return bytes(result)


def score(root, seed, *, progression=(0, -2, 3, -5), swing=0.055,
          bass_pattern=((0, 0.65, 0), (0.875, 0.3, 0), (1.75, 0.4, 7),
                        (2.5, 0.55, 0), (3.375, 0.35, 10))):
    rng = np.random.default_rng(seed)
    notes = []

    def note(beat, duration, pitch, velocity, channel):
        notes.append((beat, duration, pitch, velocity, channel))

    for bar in range(BARS):
        base = bar * 4
        transpose = progression[(bar // 2) % 4]
        breakdown = 16 <= bar < 20
        for offset in (0, 1.75, 2.5, 3.25):
            if not breakdown or offset == 0:
                note(base + offset, 0.22, 36, 108 if offset == 0 else 89, 9)
        if not breakdown:
            for offset in (1, 3):
                note(base + offset + 0.035, 0.18, 38, 96, 9)
            for step in range(8):
                note(base + step * 0.5 + (swing if step % 2 else 0),
                     0.08, 42, int(rng.integers(38, 72)), 9)
            if bar % 4 == 3:
                for offset in (3.5, 3.75):
                    note(base + offset, 0.1, 42, 48, 9)
            note(base + 2.75, 0.12, 76, 46, 9)
        for offset, duration, interval in bass_pattern[:2] if breakdown else bass_pattern:
            note(base + offset, duration, root + transpose + interval, 88, 0)
        if bar % 2 == 0:
            for interval in (0, 7, 14):
                note(base, 7.8, root + 24 + transpose + interval, 42, 1)
        if bar >= 4 and not breakdown:
            for offset, interval in ((0.75, 19), (2.25, 14), (3.5, 22)):
                if rng.random() > 0.25:
                    note(base + offset, 0.3, root + 24 + transpose + interval, 48, 2)
    return notes


def midi_bytes(notes, bpm, title, *, programs=None, beats_per_bar=4):
    ticks = 480
    title = title.encode("ascii")
    events = [
        (0, b"\xff\x03" + _variable_length(len(title)) + title),
        (0, b"\xff\x51\x03" + round(60_000_000 / bpm).to_bytes(3, "big")),
    ]
    for channel, program in (programs or {0: 38, 1: 89, 2: 14}).items():
        events.append((0, bytes((0xC0 | channel, program))))
    if beats_per_bar != 4:
        events.append((0, bytes((255, 88, 4, beats_per_bar, 2, 24, 8))))
    for beat, duration, pitch, velocity, channel in notes:
        events.append((round(beat * ticks), bytes((0x90 | channel, pitch, velocity))))
        events.append((round((beat + duration) * ticks), bytes((0x80 | channel, pitch, 0))))
    events.sort(key=lambda event: event[0])
    track = bytearray()
    previous = 0
    for tick, event in events:
        track.extend(_variable_length(tick - previous))
        track.extend(event)
        previous = tick
    track.extend(_variable_length(BARS * beats_per_bar * ticks - previous))
    track.extend(b"\xff\x2f\x00")
    return b"MThd" + struct.pack(">IHHH", 6, 0, 1, ticks) + b"MTrk" + struct.pack(">I", len(track)) + track


def _voice(pitch, duration, channel, rng, *, mellow=False):
    t = np.arange(max(2, round(duration * RATE))) / RATE
    frequency = 440 * 2 ** ((pitch - 69) / 12)
    if mellow:
        if channel == 9:
            percussion = _voice(pitch, duration, channel, rng)
            return np.convolve(percussion, np.ones(17) / 17, mode="same")[:len(t)] * .65
        phase = 2 * math.pi * frequency * t
        wave = np.sin(phase) + .12 * np.sin(phase * 2) + .03 * np.sin(phase * 3)
        attack = np.minimum(t / min(.035, duration / 3), 1)
        release = np.clip((duration - t) / min(.12, duration / 3), 0, 1)
        decay = np.exp(-t / (.8 if channel in (2, 6, 8) else 2.5))
        return .4 * wave * attack * release * decay
    if channel == 9:
        noise = rng.uniform(-1, 1, len(t))
        if pitch == 36:
            phase = 2 * math.pi * (47 * t + 6.5 * (1 - np.exp(-t / 0.025)))
            return 0.9 * np.sin(phase) * np.exp(-t / 0.07) + 0.12 * noise * np.exp(-t / 0.007)
        if pitch == 38:
            body = np.sin(2 * math.pi * 185 * t) * np.exp(-t / 0.035)
            return (0.65 * noise + 0.32 * body) * np.exp(-t / 0.055)
        if pitch == 42:
            high = noise - np.roll(noise, 1)
            return 0.18 * high * np.exp(-t / 0.019)
        if pitch in (39, 46, 49):
            high = noise - np.roll(noise, 1)
            decay = {39: 0.045, 46: 0.12, 49: 0.3}[pitch]
            return 0.18 * high * np.exp(-t / decay)
        if pitch in (41, 43, 45, 47):
            return 0.55 * np.sin(2 * math.pi * frequency * t) * np.exp(-t / 0.11)
        metal = np.sin(2 * math.pi * 1237 * t) + 0.6 * np.sin(2 * math.pi * 1921 * t)
        return 0.25 * metal * np.exp(-t / 0.03)
    if channel == 0:
        fundamental = np.sin(2 * math.pi * frequency * t)
        edge = sum(np.sin(2 * math.pi * frequency * harmonic * t) / harmonic
                   for harmonic in range(2, 7))
        wave = np.tanh(2 * (fundamental + 0.32 * edge * np.exp(-t / 0.09)))
        envelope = np.minimum(t / 0.008, 1) * np.minimum((duration - t) / 0.07, 1)
        return 0.52 * wave * envelope
    if channel == 1:
        wave = (np.sin(2 * math.pi * frequency * t)
                + 0.35 * np.sin(2 * math.pi * frequency * 1.003 * t)
                + 0.12 * np.sin(2 * math.pi * frequency * 2 * t))
        envelope = np.minimum(t / 0.6, 1) * np.minimum((duration - t) / 0.8, 1)
        return 0.2 * wave * envelope * (0.8 + 0.2 * np.sin(2 * math.pi * 0.13 * t))
    if channel in (3, 4, 5, 6, 7, 8, 10):
        phase = 2 * math.pi * frequency * t
        attack = np.minimum(t / 0.008, 1)
        release = np.clip((duration - t) / min(0.08, duration / 3), 0, 1)
        if channel == 3:
            wave = sum(np.sin(phase * harmonic) / harmonic for harmonic in range(1, 10))
            return 0.3 * np.tanh(3.2 * wave) * attack * release * np.exp(-t / 0.24)
        if channel == 4:
            wave = np.sin(phase) + 0.45 * np.sin(phase * 2) + 0.2 * np.sin(phase * 4)
            return 0.3 * wave * attack * release
        if channel == 5:
            wave = sum(np.sin(phase * harmonic) / harmonic for harmonic in range(1, 7))
            return 0.3 * wave * np.minimum(t / 0.035, 1) * release
        if channel == 6:
            return 0.4 * (np.sin(phase) + 0.35 * np.sin(phase * 3)) * attack * np.exp(-t / 0.085)
        if channel == 7:
            return 0.65 * np.sin(phase) * attack * release * np.exp(-t / 0.48)
        if channel == 8:
            wave = np.sin(phase) + 0.35 * np.sin(phase * 2) + 0.12 * np.sin(phase * 3.01)
            return 0.32 * wave * attack * release * np.exp(-t / 0.65)
        wave = np.sin(phase) + 0.18 * np.sin(phase * 3) + 0.2 * np.sin(phase * 5)
        return 0.22 * wave * np.minimum(t / 0.16, 1) * release * (0.9 + 0.1 * np.sin(2 * math.pi * 4.7 * t))
    wave = np.sin(2 * math.pi * frequency * t) + 0.22 * np.sin(2 * math.pi * frequency * 2.76 * t)
    return 0.32 * wave * np.exp(-t / 0.17) * np.minimum(t / 0.004, 1)


def render(notes, bpm, seed, *, beats_per_bar=4, drone_level=0.025, mellow=False):
    rng = np.random.default_rng(seed)
    beat_seconds = 60 / bpm
    length = round(BARS * beats_per_bar * beat_seconds * RATE)
    audio = np.zeros((length, 2), dtype=np.float64)
    for beat, duration, pitch, velocity, channel in notes:
        voice = _voice(pitch, duration * beat_seconds, channel, rng,
                       mellow=mellow) * velocity / 127
        start = round(beat * beat_seconds * RATE)
        indices = (start + np.arange(len(voice))) % length
        pan = float(rng.uniform(-0.65, 0.65)) if channel in (1, 2, 3, 5, 6, 8, 10) else (0.2 if pitch == 42 else 0)
        audio[indices, 0] += voice * math.sqrt((1 - pan) / 2)
        audio[indices, 1] += voice * math.sqrt((1 + pan) / 2)
    # Circular delay carries atmospheric tails across the loop instead of cutting them off.
    dry = audio.copy()
    for beats, gain in ((0.75, 0.16), (1.5, 0.09), (3, 0.045)):
        delay = round(beats * beat_seconds * RATE)
        audio += gain * np.roll(dry[:, ::-1], delay, axis=0)
    # A quiet, loop-periodic low drone adds space without swallowing gameplay sounds.
    t = np.arange(length) / RATE
    cycles = round(43 * length / RATE)
    drone = drone_level * np.sin(2 * math.pi * cycles * np.arange(length) / length)
    audio += drone[:, None] * (0.7 + 0.3 * np.cos(2 * math.pi * t / (length / RATE)))[:, None]
    audio = np.tanh(audio * 1.15)
    # Subtract the endpoint ramp to remove the last-to-first discontinuity.
    audio -= np.linspace(0, 1, length)[:, None] * (audio[-1] - audio[0])
    audio -= audio.mean(axis=0)
    audio *= (0.65 if mellow else 0.78) / np.max(np.abs(audio))
    return np.round(audio * 32767).astype("<i2")


def write_track(map_name, title, bpm, notes, seed, directory=MUSIC_DIR, *,
                programs=None, beats_per_bar=4, drone_level=0.025, mellow=False):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise FileNotFoundError("FFmpeg is required to encode the original soundtrack as Ogg Vorbis.")
    directory.mkdir(parents=True, exist_ok=True)
    pcm = render(notes, bpm, seed, beats_per_bar=beats_per_bar,
                 drone_level=drone_level, mellow=mellow)
    ogg = directory / f"{map_name}.ogg"
    subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
         "-f", "s16le", "-ar", str(RATE), "-ac", "2", "-i", "pipe:0",
         "-c:a", "libvorbis", "-q:a", "5", "-metadata", f"title={title}",
         "-metadata", "artist=Paint the Town - original procedural performance", str(ogg)],
        input=pcm.tobytes(), check=True,
    )
    (directory / f"{map_name}.mid").write_bytes(midi_bytes(
        notes, bpm, title, programs=programs, beats_per_bar=beats_per_bar))
    print(f"{map_name}: {title}, {bpm} BPM, {len(pcm) / RATE:.2f}s, {ogg.stat().st_size:,} bytes")


def build(tracks=TRACKS, arrangements=None):
    for map_name, title, bpm, root, seed in tracks:
        notes = score(root, seed, **(arrangements or {}).get(map_name, {}))
        write_track(map_name, title, bpm, notes, seed)


def music_lumps(tracks=TRACKS, directory=MUSIC_DIR):
    lumps = []
    for map_name, _, _, _, _ in tracks:
        ogg_path = directory / f"{map_name}.ogg"
        midi_path = directory / f"{map_name}.mid"
        ogg, midi = ogg_path.read_bytes(), midi_path.read_bytes()
        if not ogg.startswith(b"OggS") or not midi.startswith(b"MThd"):
            raise ValueError(f"{map_name}: invalid rendered soundtrack; regenerate its Ogg/MIDI pair")
        # D_ must also contain the rendered mix: a player's MIDI setting must not
        # replace the custom instruments and atmosphere with their soundfont.
        lumps.extend(((f"O_{map_name}", ogg), (f"H_{map_name}", ogg), (f"D_{map_name}", ogg)))
    return lumps


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compose and render the original Toronto Realms soundtrack.")
    parser.parse_args()
    build()
