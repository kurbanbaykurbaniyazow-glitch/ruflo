#!/usr/bin/env python3
"""
Тест полного пайплайна.
Использует Pexels видеоклипы (если ключ доступен) или слайды как fallback.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'content-automation', 'langgraph'))

# Загружаем .env
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())

from nodes.video_fetcher import fetch_videos_node
from nodes.tts_generator import generate_tts_node
from nodes.music_generator import generate_music_node
from nodes.video_assembler import assemble_video_node

CONTENT_ID = 'test-viral-005'

SCENES = [
    {"text": "Your job will be replaced by this AI tool.", "duration": 3},
    {"text": "ChatGPT can now do in 3 minutes what took your team 3 hours.", "duration": 3},
    {"text": "But here is the truth: people who use it right earn 3 times more.", "duration": 3},
    {"text": "McKinsey says AI users already earn 40 percent more than those who ignore it.", "duration": 3},
    {"text": "The mistake everyone makes: using AI to replace thinking, not multiply it.", "duration": 3},
    {"text": "Follow us. We post one AI tool every day that can double your income.", "duration": 3},
]
FULL_SCRIPT = ' '.join(s['text'] for s in SCENES)

state = {
    'content_id': CONTENT_ID,
    'title': 'AI Tool That Changes Everything',
    'scenes': SCENES,
    'script': FULL_SCRIPT,
}

has_pexels = bool(os.environ.get('PEXELS_API_KEY'))
print('=' * 55)
print('  Полный пайплайн генерации вирального видео')
print(f'  Pexels: {"✅ АКТИВЕН" if has_pexels else "❌ заблокирован (sandbox)"} | Режим: {"видеоклипы" if has_pexels else "слайды"}')
print('=' * 55)

print('\n[1/4] Загрузка видеоклипов (Pexels)...')
state = fetch_videos_node(state)
clips_ok = sum(1 for s in state['scenes'] if s.get('clip_path'))
print(f'  {"✅" if clips_ok else "⚠️"}  Клипов: {clips_ok}/{len(state["scenes"])}')

print('\n[2/4] Голос (flite offline)...')
state = generate_tts_node(state)
print(f'  {"✅" if state.get("audio_path") else "⚠️"}  {state.get("audio_path", "нет")}')

print('\n[3/4] Музыка (numpy lo-fi)...')
state = generate_music_node(state)
print(f'  {"✅" if state.get("music_path") else "⚠️"}  {state.get("music_path", "нет")}')

print('\n[4/4] Сборка видео...')
state = assemble_video_node(state)

if state.get('error'):
    print(f'  ❌  {state["error"]}')
    sys.exit(1)

video = state['video_path']
sz_mb = os.path.getsize(video) / 1024 / 1024

# Показываем аудио-трек
try:
    import imageio_ffmpeg, subprocess
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    info = subprocess.run([ff, '-i', video], capture_output=True, text=True)
    for line in info.stderr.split('\n'):
        if 'Audio' in line or 'Duration' in line:
            print(f'  📊  {line.strip()}')
except: pass

print()
print('=' * 55)
print(f'  ✅  Готово!  {video}  ({sz_mb:.1f} MB)')
print('=' * 55)
