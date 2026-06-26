#!/usr/bin/env python3
"""
Тест полного пайплайна: голос (flite+FFmpeg) + музыка (numpy lo-fi) + видео.
Полностью офлайн, без API ключей.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'content-automation', 'langgraph'))

from nodes.tts_generator import generate_tts_node
from nodes.music_generator import generate_music_node
from nodes.video_assembler import assemble_video_node
from pathlib import Path

CONTENT_ID = 'test-viral-004'

# Пример вирального сценария по теме "AI tools" — написан по правилам выше
SCENES = [
    {"text": "Your job will be replaced. By this AI tool.", "duration": 3},
    {"text": "ChatGPT can now do in 3 minutes what took your team 3 hours. And most people have no idea.", "duration": 3},
    {"text": "But here is the truth: the people who use it right are not working less. They earn 3 times more.", "duration": 3},
    {"text": "According to McKinsey, AI users already earn 40 percent more than those who ignore it.", "duration": 3},
    {"text": "The mistake everyone makes: they use AI to replace thinking, not to multiply it.", "duration": 3},
    {"text": "Follow us. We post one AI tool every day that can double your income this year.", "duration": 3},
]
FULL_SCRIPT = ' '.join(s['text'] for s in SCENES)

state = {
    'content_id': CONTENT_ID,
    'title': 'AI Tool That Replaces Your Job',
    'scenes': SCENES,
    'script': FULL_SCRIPT,
}

print('=' * 55)
print('  Тест: полный пайплайн генерации вирального видео')
print('=' * 55)

print('\n[1/3] Голос (flite + FFmpeg enhancement)...')
state = generate_tts_node(state)
if state.get('audio_path'):
    sz = os.path.getsize(state['audio_path'])
    print(f'  ✅  {state["audio_path"]}  ({sz//1024} KB)')
else:
    print('  ⚠️  Голос не сгенерирован')

print('\n[2/3] Музыка (numpy lo-fi: Am→F→C→G + drums)...')
state = generate_music_node(state)
if state.get('music_path'):
    sz = os.path.getsize(state['music_path'])
    print(f'  ✅  {state["music_path"]}  ({sz//1024} KB)')
else:
    print('  ⚠️  Музыка не сгенерирована')

print('\n[3/3] Сборка видео (слайды + аудио микс)...')
state = assemble_video_node(state)

if state.get('error'):
    print(f'  ❌  Ошибка: {state["error"]}')
    sys.exit(1)

video = state['video_path']
thumb = state.get('thumbnail_path')
sz_mb = os.path.getsize(video) / 1024 / 1024

print(f'  ✅  Видео: {video}')
print(f'  ✅  Превью: {thumb}')

# Проверяем аудио треки
try:
    import imageio_ffmpeg, subprocess
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    info = subprocess.run([ff, '-i', video], capture_output=True, text=True)
    for line in info.stderr.split('\n'):
        if 'Audio' in line or 'Duration' in line:
            print(f'  📊  {line.strip()}')
except Exception:
    pass

print()
print('=' * 55)
print(f'  Готово! Размер: {sz_mb:.1f} MB')
print('=' * 55)
