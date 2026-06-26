#!/usr/bin/env python3
"""
Тест: генерация вирального видео с голосом (flite) и фоновой музыкой (numpy).
Без API ключей — полностью офлайн.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'content-automation', 'langgraph'))

from nodes.tts_generator import generate_tts_node, clean_script_for_tts, generate_tts_flite
from nodes.music_generator import generate_music_node
from nodes.video_assembler import assemble_video_node
from pathlib import Path

CONTENT_ID = 'test-viral-002'
OUTPUT_DIR = Path('/tmp/content-automation') / CONTENT_ID

SCENES = [
    {"text": "99% of people waste money every month without knowing it.", "duration": 3},
    {"text": "Every month you lose 200 dollars on subscriptions you forgot about.", "duration": 3},
    {"text": "Here is the 5-minute trick that banks do not teach you.", "duration": 3},
    {"text": "People who use this save over 2,400 dollars every single year.", "duration": 3},
    {"text": "Most people skip this step. That is exactly why they stay broke.", "duration": 3},
    {"text": "Follow now for daily money hacks that actually work.", "duration": 3},
]

FULL_SCRIPT = ' '.join(s['text'] for s in SCENES)

state = {
    'content_id': CONTENT_ID,
    'title': 'Money Hack Nobody Talks About',
    'scenes': SCENES,
    'script': FULL_SCRIPT,
}

print('=' * 50)
print('Шаг 1: Генерация голосового озвучивания (flite офлайн)...')
state = generate_tts_node(state)
if state.get('audio_path'):
    size = os.path.getsize(state['audio_path'])
    print(f'  ✅ Голос: {state["audio_path"]} ({size//1024} KB)')
else:
    print('  ⚠️ Голос недоступен, продолжаем без него')

print()
print('Шаг 2: Генерация фоновой музыки (numpy lo-fi)...')
state = generate_music_node(state)
if state.get('music_path'):
    size = os.path.getsize(state['music_path'])
    print(f'  ✅ Музыка: {state["music_path"]} ({size//1024} KB)')
else:
    print('  ⚠️ Музыка недоступна')

print()
print('Шаг 3: Сборка видео (слайды + аудио)...')
state = assemble_video_node(state)

if state.get('error'):
    print(f'  ❌ Ошибка: {state["error"]}')
    sys.exit(1)

video = state['video_path']
thumb = state.get('thumbnail_path')
size_mb = os.path.getsize(video) / 1024 / 1024

print(f'  ✅ Видео: {video}')
print(f'  ✅ Превью: {thumb}')
print()
print('=' * 50)
print(f'Готово! Размер: {size_mb:.1f} MB')
print('=' * 50)
