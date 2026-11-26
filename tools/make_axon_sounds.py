#!/usr/bin/env python3
"""
Generate authentic, crisp Axon Body camera OGG Vorbis sound effects for Zone Bodycam.

X-Ray Engine (S.T.A.L.K.E.R. Anomaly / GAMMA) expects mono, 44100 Hz OGG Vorbis files.
This script synthesizes clean PCM WAV audio using only the Python standard library
and encodes each file to gamedata/sounds/zbc/*.ogg using ffmpeg (libvorbis).

Usage (from repo root):
    python tools/make_axon_sounds.py
"""

import math
import os
import random
import shutil
import struct
import subprocess
import tempfile
import wave

SAMPLE_RATE = 44100
TWO_PI = 2.0 * math.pi


def _clamp(v, lo=-1.0, hi=1.0):
    return lo if v < lo else (hi if v > hi else v)


def _envelope(i, total, attack_s=0.004, release_s=0.006):
    """Smooth raised-cosine attack/release envelope to prevent clicks."""
    att = max(1, int(attack_s * SAMPLE_RATE))
    rel = max(1, int(release_s * SAMPLE_RATE))
    if i < att:
        return 0.5 * (1.0 - math.cos(math.pi * i / att))
    if i >= total - rel:
        rem = total - 1 - i
        return 0.5 * (1.0 - math.cos(math.pi * rem / rel))
    return 1.0


def _tone(freq, dur_s, amp=0.65, harmonic2=0.12, harmonic3=0.04, attack_s=0.003, release_s=0.006):
    """Generate a crisp piezo-like tone with subtle odd/even harmonics."""
    n = max(1, int(round(dur_s * SAMPLE_RATE)))
    out = []
    for i in range(n):
        t = i / SAMPLE_RATE
        env = _envelope(i, n, attack_s, release_s)
        s = (
            math.sin(TWO_PI * freq * t)
            + harmonic2 * math.sin(TWO_PI * (2.0 * freq) * t)
            + harmonic3 * math.sin(TWO_PI * (3.0 * freq) * t)
        )
        # Normalize harmonic sum slightly so peak stays predictable
        s /= (1.0 + harmonic2 + harmonic3)
        out.append(_clamp(s * amp * env))
    return out


def _silence(dur_s):
    return [0.0] * max(0, int(round(dur_s * SAMPLE_RATE)))


def build_axon_start():
    """Iconic Axon high-pitched double-beep (~2.4 kHz, two crisp ~70 ms tones)."""
    return (
        _tone(2400.0, 0.070, amp=0.72)
        + _silence(0.055)
        + _tone(2400.0, 0.072, amp=0.75)
        + _silence(0.015)
    )


def build_axon_stop():
    """Lower descending double-beep."""
    return (
        _tone(1950.0, 0.072, amp=0.68)
        + _silence(0.050)
        + _tone(1420.0, 0.090, amp=0.65)
        + _silence(0.015)
    )


def build_axon_interval():
    """Subtle, quiet single 2-minute reminder beep."""
    return (
        _tone(2200.0, 0.055, amp=0.35, harmonic2=0.06, harmonic3=0.0)
        + _silence(0.015)
    )


def build_axon_event():
    """Distinct crisp EVENT / Signal trigger chime."""
    return (
        _tone(2100.0, 0.052, amp=0.68)
        + _silence(0.032)
        + _tone(2850.0, 0.088, amp=0.74)
        + _silence(0.015)
    )


def build_axon_low_batt():
    """Urgent low-battery warning chirp (3-pulse alternating chirp)."""
    return (
        _tone(2650.0, 0.055, amp=0.74)
        + _silence(0.035)
        + _tone(1850.0, 0.055, amp=0.70)
        + _silence(0.035)
        + _tone(2650.0, 0.075, amp=0.76)
        + _silence(0.015)
    )


def build_axon_mute():
    """Short tactile mute click/tone."""
    n_click = int(0.008 * SAMPLE_RATE)
    rng = random.Random(42)
    click = []
    for i in range(n_click):
        decay = math.exp(-i / (0.002 * SAMPLE_RATE))
        click.append(_clamp((rng.uniform(-1.0, 1.0) * 0.45 + math.sin(TWO_PI * 1600.0 * i / SAMPLE_RATE) * 0.4) * decay))
    blip = _tone(1100.0, 0.032, amp=0.48, harmonic2=0.08, harmonic3=0.0, attack_s=0.002, release_s=0.008)
    return click + _silence(0.004) + blip + _silence(0.010)


def build_axon_mic_clip():
    """Subtle short chest-mic gunshot limiter pop/thump."""
    dur_s = 0.065
    n = int(dur_s * SAMPLE_RATE)
    rng = random.Random(1337)
    out = []
    lp = 0.0
    phase = 0.0
    for i in range(n):
        t = i / SAMPLE_RATE
        # Fast pitch-dropping thump (150 Hz -> 55 Hz)
        freq = 55.0 + 95.0 * math.exp(-t / 0.012)
        phase += TWO_PI * freq / SAMPLE_RATE
        thump = math.sin(phase) * math.exp(-t / 0.018) * 0.72
        # Soft low-passed limiter crackle
        raw_noise = rng.uniform(-1.0, 1.0)
        lp = lp + 0.22 * (raw_noise - lp)
        noise = lp * math.exp(-t / 0.010) * 0.35
        # Soft-clip limiter saturation
        sample = math.tanh((thump + noise) * 1.6) * 0.85
        env = _envelope(i, n, attack_s=0.0015, release_s=0.015)
        out.append(_clamp(sample * env))
    return out


SOUNDS = {
    "axon_start": build_axon_start,
    "axon_stop": build_axon_stop,
    "axon_interval": build_axon_interval,
    "axon_event": build_axon_event,
    "axon_low_batt": build_axon_low_batt,
    "axon_mute": build_axon_mute,
    "axon_mic_clip": build_axon_mic_clip,
}


def write_wav(path, samples):
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        frames = bytearray()
        for s in samples:
            val = int(round(_clamp(s) * 32767.0))
            frames.extend(struct.pack("<h", val))
        wf.writeframes(bytes(frames))


def main():
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found on PATH; cannot encode OGG Vorbis")

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(repo_root, "gamedata", "sounds", "zbc")
    os.makedirs(out_dir, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        for name, builder in SOUNDS.items():
            samples = builder()
            wav_path = os.path.join(tmpdir, f"{name}.wav")
            ogg_path = os.path.join(out_dir, f"{name}.ogg")
            write_wav(wav_path, samples)
            cmd = [
                ffmpeg,
                "-y",
                "-loglevel",
                "error",
                "-i",
                wav_path,
                "-ac",
                "1",
                "-ar",
                str(SAMPLE_RATE),
                "-c:a",
                "libvorbis",
                "-q:a",
                "5",
                ogg_path,
            ]
            subprocess.run(cmd, check=True)
            size = os.path.getsize(ogg_path)
            print(f"Generated {ogg_path} ({size} bytes, {len(samples)/SAMPLE_RATE:.3f}s)")


if __name__ == "__main__":
    main()
