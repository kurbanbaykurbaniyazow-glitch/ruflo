"""
Lo-fi background music generator using numpy.
Am → F → C → G progression with bass, pads, hi-hats.
No external APIs — purely offline.
"""
import os
import subprocess
import wave
from pathlib import Path

import numpy as np

OUTPUT_DIR = Path(os.getenv('VIDEO_OUTPUT_DIR', '/tmp/content-automation'))
SR = 44100


def _get_ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return 'ffmpeg'


def _t(dur: float) -> np.ndarray:
    return np.linspace(0, dur, int(SR * dur), endpoint=False)


def _env(n: int, a=0.01, d=0.12, s=0.65, r=0.35) -> np.ndarray:
    env = np.ones(n) * s
    an, dn, rn = int(a * SR), int(d * SR), int(r * SR)
    if an: env[:an] = np.linspace(0, 1, an)
    if dn and an + dn <= n: env[an:an + dn] = np.linspace(1, s, dn)
    if rn: env[-rn:] = np.linspace(s, 0, rn)
    return env


def _pad(freqs: list, dur: float, vol: float = 0.22) -> np.ndarray:
    """Warm pad chord: fundamental + harmonics + slight detuning."""
    n = int(SR * dur)
    buf = np.zeros(n)
    tv = _t(dur)
    for f in freqs:
        # Main + detuned copies for warmth
        for detune in [0, 0.5, -0.5]:
            fd = f * (2 ** (detune / 1200))  # cents detune
            wave = (
                0.5 * np.sin(2 * np.pi * fd * tv)
                + 0.25 * np.sin(2 * np.pi * fd * 2 * tv)
                + 0.1 * np.sin(2 * np.pi * fd * 3 * tv)
            )
            buf += wave[:n]
    return buf[:n] * _env(n) * vol


def _bass(freq: float, dur: float, vol: float = 0.5) -> np.ndarray:
    """Deep bass note with punch."""
    n = int(SR * dur)
    tv = _t(dur)
    note = (
        0.7 * np.sin(2 * np.pi * freq * tv)
        + 0.2 * np.sin(2 * np.pi * freq * 2 * tv)
    )
    env = np.exp(-tv * 2.5)  # quick decay for pluck feel
    return note[:n] * env * vol


def _kick(vol: float = 0.8) -> np.ndarray:
    """Lo-fi kick drum."""
    dur = 0.3
    n = int(SR * dur)
    tv = np.linspace(0, dur, n)
    pitch_env = np.exp(-tv * 30)
    wave = np.sin(2 * np.pi * (80 + 120 * pitch_env) * tv)
    amp_env = np.exp(-tv * 12)
    return wave * amp_env * vol


def _snare(vol: float = 0.5) -> np.ndarray:
    """Lo-fi snare: noise burst."""
    dur = 0.18
    n = int(SR * dur)
    noise = np.random.randn(n)
    env = np.exp(-np.linspace(0, 8, n))
    tone = 0.3 * np.sin(2 * np.pi * 200 * np.linspace(0, dur, n))
    return (noise * 0.7 + tone) * env * vol


def _hihat(vol: float = 0.18, closed: bool = True) -> np.ndarray:
    """Hi-hat (closed or open)."""
    dur = 0.04 if closed else 0.12
    n = int(SR * dur)
    noise = np.random.randn(n)
    decay = 6 if closed else 2
    env = np.exp(-np.linspace(0, decay, n))
    return noise * env * vol


def _place(buf: np.ndarray, clip: np.ndarray, onset_sec: float) -> np.ndarray:
    """Place a short clip into the buffer at onset (seconds)."""
    onset = int(onset_sec * SR)
    end = min(onset + len(clip), len(buf))
    buf[onset:end] += clip[:end - onset]
    return buf


def generate_lofi_music(duration: float, output_path: Path) -> Path:
    """
    Generate lo-fi background music: pad chords + bass + drum pattern.
    Loop-based: Am F C G at 75 BPM.
    """
    bpm = 75
    beat = 60 / bpm       # seconds per beat
    bar = beat * 4        # 4 beats per bar = 3.2s
    loop = bar * 4        # 4 bars = 12.8s

    # Chord voicings (root + 3rd + 5th, one octave up for pads)
    chords = [
        ([220.0, 261.6, 329.6], 110.0),   # Am  → bass A2
        ([174.6, 220.0, 261.6], 87.3),    # F   → bass F2
        ([130.8, 164.8, 196.0], 130.8),   # C   → bass C3
        ([196.0, 246.9, 293.7], 98.0),    # G   → bass G2
    ]

    # Build one loop
    loop_samples = int(SR * loop)
    buf = np.zeros(loop_samples)

    for i, (freqs, bass_freq) in enumerate(chords):
        t0 = i * bar
        # Pad chord
        pad = _pad(freqs, bar + 0.4)
        end = min(int(t0 * SR) + len(pad), loop_samples)
        buf[int(t0 * SR):end] += pad[:end - int(t0 * SR)]
        # Bass (plays on beats 1 and 3)
        for b_off in [0, beat * 2]:
            b = _bass(bass_freq, beat * 1.5)
            s = int((t0 + b_off) * SR)
            e = min(s + len(b), loop_samples)
            buf[s:e] += b[:e - s]

    # Drum pattern over the whole loop
    for beat_i in range(int(loop / beat)):
        t0 = beat_i * beat
        # Kick on 1, 3
        if beat_i % 4 in (0, 2):
            _place(buf, _kick(0.7), t0)
        # Snare on 2, 4
        if beat_i % 4 in (1, 3):
            _place(buf, _snare(0.4), t0)
        # 8th-note hi-hats
        for eighth in range(2):
            _place(buf, _hihat(0.15, closed=True), t0 + eighth * beat * 0.5)
        # Occasional open hat on the off-beat
        if beat_i % 4 == 2:
            _place(buf, _hihat(0.12, closed=False), t0 + beat * 0.5)

    # Tile to fill duration + fade in/out
    n_reps = int(np.ceil(duration / loop)) + 1
    full = np.tile(buf, n_reps)[:int(SR * duration)]
    fade_n = int(SR * 1.5)
    full[:fade_n] *= np.linspace(0, 1, fade_n)
    full[-fade_n:] *= np.linspace(1, 0, fade_n)

    # Normalise to -10 dBFS (louder than before)
    peak = np.max(np.abs(full))
    if peak > 0:
        full = full / peak * 0.32

    # Save WAV → MP3
    wav_path = output_path.with_suffix('.wav')
    audio_i16 = (full * 32767).clip(-32768, 32767).astype(np.int16)
    with wave.open(str(wav_path), 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(audio_i16.tobytes())

    ffmpeg = _get_ffmpeg()
    r = subprocess.run(
        [ffmpeg, '-y', '-i', str(wav_path), '-q:a', '3', str(output_path)],
        capture_output=True
    )
    if r.returncode == 0 and output_path.exists():
        wav_path.unlink(missing_ok=True)
        return output_path
    return wav_path


def generate_music_node(state: dict) -> dict:
    content_id: str = state.get('content_id', 'default')
    scenes: list = state.get('scenes', [])
    duration = sum(s.get('duration', 3) for s in scenes) + 3

    audio_dir = OUTPUT_DIR / content_id / 'audio'
    audio_dir.mkdir(parents=True, exist_ok=True)
    music_path = audio_dir / 'bgmusic.mp3'

    try:
        result = generate_lofi_music(duration, music_path)
        print(f'[Music] ✅ {result}  ({os.path.getsize(result)//1024} KB)')
        return {**state, 'music_path': str(result)}
    except Exception as e:
        print(f'[Music] ❌ {e}')
        return {**state, 'music_path': None}
