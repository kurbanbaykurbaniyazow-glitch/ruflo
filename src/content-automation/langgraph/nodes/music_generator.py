"""
Lo-fi background music generator using numpy.
Generates a simple chord progression that loops for video duration.
No external APIs needed — purely offline.
"""
import os
import subprocess
import struct
import wave
from pathlib import Path

import numpy as np

OUTPUT_DIR = Path(os.getenv('VIDEO_OUTPUT_DIR', '/tmp/content-automation'))
SR = 44100  # sample rate


def _get_ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return 'ffmpeg'


def _sine(freq: float, duration: float, amp: float = 1.0) -> np.ndarray:
    t = np.linspace(0, duration, int(SR * duration), endpoint=False)
    return amp * np.sin(2 * np.pi * freq * t)


def _adsr(n: int, a: float = 0.02, d: float = 0.1, s: float = 0.7, r: float = 0.3) -> np.ndarray:
    """Attack-Decay-Sustain-Release envelope."""
    env = np.ones(n) * s
    a_n = int(a * SR)
    d_n = int(d * SR)
    r_n = int(r * SR)
    if a_n > 0:
        env[:a_n] = np.linspace(0, 1, a_n)
    if d_n > 0 and a_n + d_n <= n:
        env[a_n:a_n + d_n] = np.linspace(1, s, d_n)
    if r_n > 0:
        env[-r_n:] = np.linspace(s, 0, r_n)
    return env


def _chord(freqs: list[float], dur: float, amp: float = 0.18) -> np.ndarray:
    """Generate a chord with harmonics and ADSR envelope."""
    samples = int(SR * dur)
    buf = np.zeros(samples)
    for f in freqs:
        note = (
            _sine(f, dur, 0.5)         # fundamental
            + _sine(f * 2, dur, 0.25)  # 2nd harmonic
            + _sine(f * 3, dur, 0.1)   # 3rd harmonic
        )
        buf += note[:samples]
    env = _adsr(samples, a=0.02, d=0.15, s=0.6, r=0.4)
    return buf * env * amp


def _lofi_beat(dur: float, bpm: float = 70) -> np.ndarray:
    """Simple lo-fi kick + snare pattern."""
    samples = int(SR * dur)
    beat = np.zeros(samples)
    beat_dur = 60 / bpm
    n_beats = int(dur / beat_dur)

    for i in range(n_beats):
        onset = int(i * beat_dur * SR)
        # Kick on 1 and 3
        if i % 4 in (0, 2):
            kick_len = int(0.25 * SR)
            t = np.linspace(0, 1, kick_len)
            kick = 0.6 * np.sin(2 * np.pi * 60 * np.exp(-5 * t) * t)
            kick *= np.exp(-8 * t)
            end = min(onset + kick_len, samples)
            beat[onset:end] += kick[:end - onset]
        # Hi-hat on every beat
        hat_len = int(0.05 * SR)
        noise = np.random.randn(hat_len) * 0.06
        env = np.exp(-np.linspace(0, 8, hat_len))
        hat = noise * env
        end = min(onset + hat_len, samples)
        beat[onset:end] += hat[:end - onset]

    return beat


def generate_lofi_music(duration: float, output_path: Path) -> Path:
    """
    Generate lo-fi background music for given duration.
    Chord progression: Am → F → C → G (loop)
    """
    # Chord frequencies (root + 3rd + 5th)
    chord_defs = {
        'Am': [220.0, 261.6, 329.6],   # A3, C4, E4
        'F':  [174.6, 220.0, 261.6],   # F3, A3, C4
        'C':  [130.8, 164.8, 196.0],   # C3, E3, G3
        'G':  [196.0, 246.9, 293.7],   # G3, B3, D4
    }
    progression = ['Am', 'F', 'C', 'G']
    chord_dur = 4.5  # seconds per chord
    loop_dur = chord_dur * len(progression)  # 18s loop

    # Build one loop
    loop_samples = int(SR * loop_dur)
    loop_buf = np.zeros(loop_samples)

    for i, name in enumerate(progression):
        start = int(i * chord_dur * SR)
        chunk = _chord(chord_defs[name], chord_dur + 0.5)  # slight overlap
        end = min(start + len(chunk), loop_samples)
        loop_buf[start:end] += chunk[:end - start]

    # Add lo-fi beat
    loop_buf += _lofi_beat(loop_dur)

    # Tile to full duration
    n_repeats = int(np.ceil(duration / loop_dur)) + 1
    full = np.tile(loop_buf, n_repeats)[:int(SR * duration)]

    # Soft fade in/out
    fade = int(SR * 1.5)
    full[:fade] *= np.linspace(0, 1, fade)
    full[-fade:] *= np.linspace(1, 0, fade)

    # Normalise to -12 dBFS
    peak = np.max(np.abs(full))
    if peak > 0:
        full = full / peak * 0.25

    # Save as 16-bit WAV
    wav_path = output_path.with_suffix('.wav')
    audio_int16 = (full * 32767).clip(-32768, 32767).astype(np.int16)

    with wave.open(str(wav_path), 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(audio_int16.tobytes())

    # Convert to MP3
    ffmpeg = _get_ffmpeg()
    r = subprocess.run(
        [ffmpeg, '-y', '-i', str(wav_path), '-q:a', '4', str(output_path)],
        capture_output=True
    )
    if r.returncode == 0 and output_path.exists():
        wav_path.unlink(missing_ok=True)
        return output_path
    return wav_path


def generate_music_node(state: dict) -> dict:
    """LangGraph node: generate background music."""
    content_id: str = state.get('content_id', 'default')
    scenes: list[dict] = state.get('scenes', [])
    duration = sum(s.get('duration', 3) for s in scenes) + 2

    audio_dir = OUTPUT_DIR / content_id / 'audio'
    audio_dir.mkdir(parents=True, exist_ok=True)
    music_path = audio_dir / 'bgmusic.mp3'

    try:
        result = generate_lofi_music(duration, music_path)
        print(f'[Music] ✅ {result}')
        return {**state, 'music_path': str(result)}
    except Exception as e:
        print(f'[Music] ❌ {e}')
        return {**state, 'music_path': None}
