#!/usr/bin/env python3
"""
Полный пайплайн генерации вирального видео.

Формат: AI-персонаж (фрукт/овощ) + история со смыслом + субтитры + CTA в конце.
"""
import sys, os, uuid
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

from nodes.script_writer import generate_story_node
from nodes.video_fetcher import fetch_videos_node
from nodes.tts_generator import generate_tts_node
from nodes.music_generator import generate_music_node
from nodes.video_assembler import assemble_video_node

CONTENT_ID = f'story-{uuid.uuid4().hex[:8]}'

state = {
    'content_id': CONTENT_ID,
    'title': '',
    'scenes': [],
    'script': '',
}

has_pexels = bool(os.environ.get('PEXELS_API_KEY'))
has_anthropic = bool(os.environ.get('ANTHROPIC_API_KEY'))

print('=' * 60)
print('  Виральный видео пайплайн — AI персонажи')
print(f'  Claude AI: {"✅" if has_anthropic else "❌"}  |  Pexels: {"✅" if has_pexels else "❌ (слайды)"}')
print('=' * 60)

print('\n[1/5] Генерация сценария...')
state = generate_story_node(state)
if state.get('error'):
    print(f'  ❌  {state["error"]}')
    sys.exit(1)
print(f'  ✅  "{state["title"]}" — {len(state["scenes"])} сцен')

print('\n[2/5] Загрузка видеоклипов (Pexels)...')
state = fetch_videos_node(state)
clips_ok = sum(1 for s in state['scenes'] if s.get('clip_path'))
print(f'  {"✅" if clips_ok else "⚠️"}  Клипов: {clips_ok}/{len(state["scenes"])}')

print('\n[3/5] Голос персонажа (TTS)...')
state = generate_tts_node(state)
print(f'  {"✅" if state.get("audio_path") else "⚠️"}  {state.get("audio_path", "нет")}')

print('\n[4/5] Фоновая музыка...')
state = generate_music_node(state)
print(f'  {"✅" if state.get("music_path") else "⚠️"}  {state.get("music_path", "нет")}')

print('\n[5/5] Сборка финального видео...')
state = assemble_video_node(state)

if state.get('error'):
    print(f'  ❌  {state["error"]}')
    sys.exit(1)

video = state['video_path']
sz_mb = os.path.getsize(video) / 1024 / 1024

print()
print('=' * 60)
print(f'  ✅  Готово!')
print(f'  📁  {video}')
print(f'  📦  Размер: {sz_mb:.1f} MB')
print(f'  🎭  Персонаж: {state.get("character", {}).get("name", "?")}')
print(f'  📖  История: {state["title"]}')
print('=' * 60)
print()
print('  Смотри видео:')
print('  python3 -m http.server 8080 --directory /var/data/ruflo-videos')
print(f'  http://46.101.135.99:8080/{CONTENT_ID}/')
