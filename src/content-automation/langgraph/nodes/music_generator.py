"""
Background music generator — three-tier fallback:
  1. Mubert API (MUBERT_API_KEY set)   — AI-generated unique track per video
  2. Pixabay library (local folder)    — CC0 pre-downloaded tracks, rotated
  3. Numpy lo-fi (offline fallback)    — Am→F→C→G, 75 BPM, always works

Set MUSIC_LIBRARY_DIR to a folder with .mp3 files downloaded from Pixabay.
"""
import os
import random
import subprocess
import wave
from pathlib import Path

import numpy as np

OUTPUT_DIR = Path(os.getenv('VIDEO_OUTPUT_DIR', '/tmp/content-automation'))
MUSIC_LIBRARY_DIR = Path(os.getenv('MUSIC_LIBRARY_DIR', '/tmp/pixabay-music'))
MUBERT_API_KEY = os.getenv('MUBERT_API_KEY', '')
SR = 44100


def _get_ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return 'ffmpeg'


# ─── Tier 1: Mubert API ──────────────────────────────────────────────────────

def _generate_mubert(duration: int, mood: str, output_path: Path) -> Path:
    """
    Generate a unique AI track via Mubert API.
    Requires: pip install mubert  (MUBERT_API_KEY in .env)
    """
    import json
    import urllib.request
    import ssl

    ctx = ssl.create_default_context()
    ca = '/root/.ccr/ca-bundle.crt'
    if os.path.exists(ca):
        ctx.load_verify_locations(ca)

    # Step 1: get access token
    auth_url = 'https://api.mubert.com/v2/TTM'
    payload = json.dumps({
        'method': 'GetServiceAccess',
        'params': {'email': 'user@example.com', 'license': 'ttm', 'token': MUBERT_API_KEY}
    }).encode()

    req = urllib.request.Request(auth_url, data=payload,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, context=ctx, timeout=20) as r:
        resp = json.loads(r.read())

    pat = resp['data']['pat']

    # Step 2: request track generation
    gen_payload = json.dumps({
        'method': 'RecordTrackTTM',
        'params': {
            'pat': pat,
            'duration': duration,
            'mood': mood,
            'format': 'mp3',
            'intensity': 'medium',
        }
    }).encode()

    req2 = urllib.request.Request(auth_url, data=gen_payload,
                                  headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req2, context=ctx, timeout=60) as r:
        resp2 = json.loads(r.read())

    track_url = resp2['data']['tasks'][0]['download_link']
    print(f'[Music] Mubert track: {track_url}')

    # Step 3: download the MP3
    dl_req = urllib.request.Request(track_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(dl_req, context=ctx, timeout=60) as r, \
         open(output_path, 'wb') as f:
        while chunk := r.read(65536):
            f.write(chunk)

    return output_path


# ─── Tier 2: Pixabay library ─────────────────────────────────────────────────

def _pick_library_track(duration: float, output_path: Path) -> Path | None:
    """
    Pick a random MP3 from local Pixabay library, trim to duration.
    Returns None if library is empty.
    """
    if not MUSIC_LIBRARY_DIR.exists():
        return None

    tracks = list(MUSIC_LIBRARY_DIR.glob('*.mp3')) + list(MUSIC_LIBRARY_DIR.glob('*.wav'))
    if not tracks:
        return None

    track = random.choice(tracks)
    ffmpeg = _get_ffmpeg()

    # Trim to video duration with fade-in/fade-out
    fade_out = min(2.0, duration * 0.1)
    r = subprocess.run([
        ffmpeg, '-y', '-i', str(track),
        '-t', str(duration),
        '-af', f'afade=t=in:st=0:d=1.5,afade=t=out:st={duration - fade_out}:d={fade_out},'
               f'volume=0.9,aresample=44100',
        '-c:a', 'libmp3lame', '-q:a', '3',
        str(output_path),
    ], capture_output=True)

    if r.returncode == 0 and output_path.exists() and output_path.stat().st_size > 1000:
        print(f'[Music] Pixabay library: {track.name}')
        return output_path
    return None


# ─── Tier 3: Numpy lo-fi ─────────────────────────────────────────────────────

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
    n = int(SR * dur)
    buf = np.zeros(n)
    tv = _t(dur)
    for f in freqs:
        for detune in [0, 0.5, -0.5]:
            fd = f * (2 ** (detune / 1200))
            wave = (
                0.5 * np.sin(2 * np.pi * fd * tv)
                + 0.25 * np.sin(2 * np.pi * fd * 2 * tv)
                + 0.1 * np.sin(2 * np.pi * fd * 3 * tv)
            )
            buf += wave[:n]
    return buf[:n] * _env(n) * vol


def _bass(freq: float, dur: float, vol: float = 0.5) -> np.ndarray:
    n = int(SR * dur)
    tv = _t(dur)
    note = (
        0.7 * np.sin(2 * np.pi * freq * tv)
        + 0.2 * np.sin(2 * np.pi * freq * 2 * tv)
    )
    env = np.exp(-tv * 2.5)
    return note[:n] * env * vol


def _kick(vol: float = 0.8) -> np.ndarray:
    dur = 0.3
    n = int(SR * dur)
    tv = np.linspace(0, dur, n)
    pitch_env = np.exp(-tv * 30)
    wave = np.sin(2 * np.pi * (80 + 120 * pitch_env) * tv)
    amp_env = np.exp(-tv * 12)
    return wave * amp_env * vol


def _snare(vol: float = 0.5) -> np.ndarray:
    dur = 0.18
    n = int(SR * dur)
    noise = np.random.randn(n)
    env = np.exp(-np.linspace(0, 8, n))
    tone = 0.3 * np.sin(2 * np.pi * 200 * np.linspace(0, dur, n))
    return (noise * 0.7 + tone) * env * vol


def _hihat(vol: float = 0.18, closed: bool = True) -> np.ndarray:
    dur = 0.04 if closed else 0.12
    n = int(SR * dur)
    noise = np.random.randn(n)
    decay = 6 if closed else 2
    env = np.exp(-np.linspace(0, decay, n))
    return noise * env * vol


def _place(buf: np.ndarray, clip: np.ndarray, onset_sec: float) -> np.ndarray:
    onset = int(onset_sec * SR)
    end = min(onset + len(clip), len(buf))
    buf[onset:end] += clip[:end - onset]
    return buf


def generate_lofi_music(duration: float, output_path: Path) -> Path:
    """Generate lo-fi background music: pad chords + bass + drum pattern."""
    bpm = 75
    beat = 60 / bpm
    bar = beat * 4
    loop = bar * 4

    chords = [
        ([220.0, 261.6, 329.6], 110.0),
        ([174.6, 220.0, 261.6], 87.3),
        ([130.8, 164.8, 196.0], 130.8),
        ([196.0, 246.9, 293.7], 98.0),
    ]

    loop_samples = int(SR * loop)
    buf = np.zeros(loop_samples)

    for i, (freqs, bass_freq) in enumerate(chords):
        t0 = i * bar
        pad = _pad(freqs, bar + 0.4)
        end = min(int(t0 * SR) + len(pad), loop_samples)
        buf[int(t0 * SR):end] += pad[:end - int(t0 * SR)]
        for b_off in [0, beat * 2]:
            b = _bass(bass_freq, beat * 1.5)
            s = int((t0 + b_off) * SR)
            e = min(s + len(b), loop_samples)
            buf[s:e] += b[:e - s]

    for beat_i in range(int(loop / beat)):
        t0 = beat_i * beat
        if beat_i % 4 in (0, 2):
            _place(buf, _kick(0.7), t0)
        if beat_i % 4 in (1, 3):
            _place(buf, _snare(0.4), t0)
        for eighth in range(2):
            _place(buf, _hihat(0.15, closed=True), t0 + eighth * beat * 0.5)
        if beat_i % 4 == 2:
            _place(buf, _hihat(0.12, closed=False), t0 + beat * 0.5)

    n_reps = int(np.ceil(duration / loop)) + 1
    full = np.tile(buf, n_reps)[:int(SR * duration)]
    fade_n = int(SR * 1.5)
    full[:fade_n] *= np.linspace(0, 1, fade_n)
    full[-fade_n:] *= np.linspace(1, 0, fade_n)

    peak = np.max(np.abs(full))
    if peak > 0:
        full = full / peak * 0.32

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


# ─── Main node ───────────────────────────────────────────────────────────────

def _infer_mood(title: str, script: str = '') -> str:
    """Map content topic to Mubert mood tag."""
    text = (title + ' ' + script).lower()
    if any(w in text for w in ['money', 'income', 'earn', 'rich', 'profit', 'деньг']):
        return 'inspiring'
    if any(w in text for w in ['ai', 'tech', 'future', 'robot', 'digital']):
        return 'focused'
    if any(w in text for w in ['health', 'fitness', 'sleep', 'mind', 'calm']):
        return 'calm'
    if any(w in text for w in ['viral', 'trend', 'shock', 'crazy', 'insane']):
        return 'energetic'
    return 'motivational'


def generate_music_node(state: dict) -> dict:
    content_id: str = state.get('content_id', 'default')
    scenes: list = state.get('scenes', [])
    title: str = state.get('title', '')
    script: str = state.get('script', '')
    duration = sum(s.get('duration', 3) for s in scenes) + 3

    audio_dir = OUTPUT_DIR / content_id / 'audio'
    audio_dir.mkdir(parents=True, exist_ok=True)
    music_path = audio_dir / 'bgmusic.mp3'

    # Tier 1: Mubert API
    if MUBERT_API_KEY:
        try:
            mood = _infer_mood(title, script)
            print(f'[Music] Mubert API ({mood})...')
            result = _generate_mubert(int(duration), mood, music_path)
            print(f'[Music] ✅ Mubert  ({os.path.getsize(result)//1024} KB)')
            return {**state, 'music_path': str(result)}
        except Exception as e:
            print(f'[Music] Mubert failed: {e} — trying library...')

    # Tier 2: Pixabay local library
    try:
        result = _pick_library_track(duration, music_path)
        if result:
            print(f'[Music] ✅ Pixabay library  ({os.path.getsize(result)//1024} KB)')
            return {**state, 'music_path': str(result)}
    except Exception as e:
        print(f'[Music] Library failed: {e} — generating offline...')

    # Tier 3: Numpy lo-fi (always works)
    try:
        print('[Music] Generating offline lo-fi...')
        result = generate_lofi_music(duration, music_path)
        print(f'[Music] ✅ Lo-fi  ({os.path.getsize(result)//1024} KB)')
        return {**state, 'music_path': str(result)}
    except Exception as e:
        print(f'[Music] ❌ {e}')
        return {**state, 'music_path': None}
