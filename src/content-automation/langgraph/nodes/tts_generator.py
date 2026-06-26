"""
TTS generator node for LangGraph video pipeline.

Priority order:
1. ElevenLabs (cloud, best quality) — needs ELEVENLABS_API_KEY
2. OpenAI TTS-1-HD (cloud, great) — needs OPENAI_API_KEY
3. edge-tts / Microsoft Edge TTS (cloud, free) — needs network
4. Flite (offline, robotic but works always) — bundled via libflite1

In production: use ElevenLabs or OpenAI.
In this demo environment (blocked APIs): flite is used automatically.
"""
import ctypes
import os
import re
import subprocess
from pathlib import Path

OUTPUT_DIR = Path(os.getenv('VIDEO_OUTPUT_DIR', '/tmp/content-automation'))
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY', '')
ELEVENLABS_VOICE_ID = os.getenv('ELEVENLABS_VOICE_ID', '21m00Tcm4TlvDq8ikWAM')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')


def clean_script_for_tts(script: str) -> str:
    text = re.sub(r'\[SCENE\s*\d+\]:\s*', '', script)
    text = re.sub(r'[*_#`]', '', text)
    text = re.sub(r'[^\w\s.,!?\'"-]', ' ', text)
    return ' '.join(text.split())


def _get_ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return 'ffmpeg'


# ─── Flite offline TTS (always available) ────────────────────────────────────

_flite_lib = None
_flite_voice = None


def _init_flite():
    global _flite_lib, _flite_voice
    if _flite_lib is not None:
        return True
    try:
        lib = ctypes.CDLL('/usr/lib/x86_64-linux-gnu/libflite.so.2.2')
        # Use SLT voice (female, clearer)
        voice_lib = ctypes.CDLL('/usr/lib/x86_64-linux-gnu/libflite_cmu_us_slt.so.2.2')
        lib.flite_init.restype = ctypes.c_int
        lib.flite_init()
        voice_lib.register_cmu_us_slt.restype = ctypes.c_void_p
        voice = voice_lib.register_cmu_us_slt(None)
        lib.flite_text_to_speech.argtypes = [
            ctypes.c_char_p, ctypes.c_void_p, ctypes.c_char_p
        ]
        lib.flite_text_to_speech.restype = ctypes.c_float
        _flite_lib = lib
        _flite_voice = ctypes.c_void_p(voice)
        return True
    except Exception as e:
        print(f'[TTS/flite] Init failed: {e}')
        return False


def generate_tts_flite(text: str, output_path: Path) -> Path:
    """
    Offline TTS using libflite + FFmpeg audio enhancement.
    Pipeline: flite raw WAV → resample 44100Hz → EQ boost → reverb → loudnorm → MP3
    """
    if not _init_flite():
        raise RuntimeError('flite not available')
    wav_path = output_path.with_suffix('.wav')
    dur = _flite_lib.flite_text_to_speech(
        text.encode('ascii', errors='replace'),
        _flite_voice,
        str(wav_path).encode(),
    )
    if dur <= 0:
        raise RuntimeError('flite returned 0 duration')

    ffmpeg = _get_ffmpeg()
    # Audio enhancement chain:
    # aresample=44100 → boost 200Hz (warmth) + 3kHz (clarity)
    # → subtle echo/reverb → loudness normalisation
    af = (
        'aresample=44100,'
        'equalizer=f=200:width_type=o:width=2:g=3,'
        'equalizer=f=3000:width_type=o:width=2:g=2,'
        'aecho=0.5:0.7:50:0.3,'
        'loudnorm=I=-16:TP=-1.5:LRA=11'
    )
    r = subprocess.run(
        [ffmpeg, '-y', '-i', str(wav_path), '-af', af, '-ar', '44100', '-q:a', '3', str(output_path)],
        capture_output=True
    )
    wav_path.unlink(missing_ok=True)
    if r.returncode == 0 and output_path.exists():
        return output_path
    raise RuntimeError(f'ffmpeg enhancement failed: {r.stderr[-200:]}')


# ─── ElevenLabs (cloud, blocked in demo env) ──────────────────────────────────

def generate_tts_elevenlabs(text: str, output_path: Path) -> Path:
    import httpx
    url = f'https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}'
    payload = {
        'text': text,
        'model_id': 'eleven_turbo_v2',
        'voice_settings': {'stability': 0.5, 'similarity_boost': 0.75},
    }
    with httpx.Client(timeout=60) as c:
        r = c.post(url, json=payload, headers={
            'Accept': 'audio/mpeg',
            'Content-Type': 'application/json',
            'xi-api-key': ELEVENLABS_API_KEY,
        })
        r.raise_for_status()
        output_path.write_bytes(r.content)
    return output_path


# ─── OpenAI TTS (cloud, blocked in demo env) ──────────────────────────────────

def generate_tts_openai(text: str, output_path: Path) -> Path:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.audio.speech.create(
        model='tts-1-hd', voice='nova', input=text, response_format='mp3'
    )
    response.stream_to_file(str(output_path))
    return output_path


# ─── LangGraph Node ───────────────────────────────────────────────────────────

def generate_tts_node(state: dict) -> dict:
    """LangGraph node: generate TTS narration audio."""
    script: str = state.get('script', '')
    content_id: str = state.get('content_id', 'default')

    if not script:
        return {**state, 'audio_path': None, 'error': None}

    audio_dir = OUTPUT_DIR / content_id / 'audio'
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_path = audio_dir / 'narration.mp3'
    clean_text = clean_script_for_tts(script)

    # Try providers in order
    providers = []
    if ELEVENLABS_API_KEY:
        providers.append(('ElevenLabs', lambda: generate_tts_elevenlabs(clean_text, audio_path)))
    if OPENAI_API_KEY:
        providers.append(('OpenAI', lambda: generate_tts_openai(clean_text, audio_path)))
    providers.append(('Flite (offline)', lambda: generate_tts_flite(clean_text, audio_path)))

    for name, fn in providers:
        try:
            print(f'[TTS] Trying {name}...')
            result = fn()
            print(f'[TTS] ✅ {name} → {result}')
            return {**state, 'audio_path': str(result), 'error': None}
        except Exception as e:
            print(f'[TTS] ❌ {name}: {e}')

    print('[TTS] All providers failed, continuing without audio')
    return {**state, 'audio_path': None, 'error': None}
