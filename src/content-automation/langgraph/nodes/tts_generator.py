import os
import re
from pathlib import Path
from openai import OpenAI

client = OpenAI()
OUTPUT_DIR = Path(os.getenv('VIDEO_OUTPUT_DIR', '/tmp/content-automation'))

# ElevenLabs as alternative TTS
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY', '')
ELEVENLABS_VOICE_ID = os.getenv('ELEVENLABS_VOICE_ID', '21m00Tcm4TlvDq8ikWAM')  # Rachel


def generate_tts_openai(text: str, output_path: Path) -> Path:
    """Generate TTS using OpenAI's TTS API."""
    response = client.audio.speech.create(
        model='tts-1-hd',
        voice='nova',
        input=text,
        response_format='mp3',
    )
    response.stream_to_file(str(output_path))
    return output_path


def generate_tts_elevenlabs(text: str, output_path: Path) -> Path:
    """Generate TTS using ElevenLabs for higher quality."""
    import httpx

    url = f'https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}'
    headers = {
        'Accept': 'audio/mpeg',
        'Content-Type': 'application/json',
        'xi-api-key': ELEVENLABS_API_KEY,
    }
    payload = {
        'text': text,
        'model_id': 'eleven_turbo_v2',
        'voice_settings': {
            'stability': 0.5,
            'similarity_boost': 0.75,
            'style': 0.3,
            'use_speaker_boost': True,
        },
    }

    with httpx.Client() as http_client:
        response = http_client.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        output_path.write_bytes(response.content)

    return output_path


def clean_script_for_tts(script: str) -> str:
    """Remove stage directions and clean up text for TTS."""
    # Remove [SCENE X]: markers
    text = re.sub(r'\[SCENE\s*\d+\]:\s*', '', script)
    # Remove markdown formatting
    text = re.sub(r'[*_#`]', '', text)
    # Normalize whitespace
    text = ' '.join(text.split())
    return text


def generate_tts_node(state: dict) -> dict:
    """LangGraph node: generate TTS audio for the full script."""
    script: str = state.get('script', '')
    content_id: str = state.get('content_id', 'default')

    if not script:
        return {**state, 'error': 'No script for TTS'}

    audio_dir = OUTPUT_DIR / content_id / 'audio'
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_path = audio_dir / 'narration.mp3'

    clean_text = clean_script_for_tts(script)

    try:
        if ELEVENLABS_API_KEY:
            print('[TTS] Using ElevenLabs...')
            generate_tts_elevenlabs(clean_text, audio_path)
        else:
            print('[TTS] Using OpenAI TTS...')
            generate_tts_openai(clean_text, audio_path)

        print(f'[TTS] Audio saved: {audio_path}')
        return {**state, 'audio_path': str(audio_path), 'error': None}

    except Exception as e:
        print(f'[TTS] Error: {e}')
        return {**state, 'audio_path': None, 'error': str(e)}
