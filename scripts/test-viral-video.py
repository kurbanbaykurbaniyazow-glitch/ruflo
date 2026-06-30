#!/usr/bin/env python3
"""
Полный пайплайн генерации вирального видео.

Формат: Claude AI пишет историю → DALL-E рисует персонажа →
        TTS озвучивает → музыка → FFmpeg собирает финальное видео.
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
from nodes.image_generator import generate_images_node
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

has_anthropic = bool(os.environ.get('ANTHROPIC_API_KEY'))
has_openai    = bool(os.environ.get('OPENAI_API_KEY'))

print('=' * 60)
print('  Виральный видео пайплайн — AI персонажи')
print(f'  Claude AI : {"✅" if has_anthropic else "❌ нет ключа"}')
print(f'  DALL-E 3  : {"✅" if has_openai else "⚠️  нет ключа (градиент)"}')
print(f'  ID        : {CONTENT_ID}')
print('=' * 60)

# ── Шаг 1: Сценарий ─────────────────────────────────────────────────────────
print('\n[1/5] 📝 Генерация сценария (Claude AI)...')
state = generate_story_node(state)
if state.get('error'):
    print(f'  ❌  {state["error"]}')
    sys.exit(1)
char_name = state.get('character', {}).get('name', '?')
print(f'  ✅  "{state["title"]}"')
print(f'  🎭  Персонаж: {char_name}')
print(f'  📖  Тема: {state.get("theme", "")}')
print()
for s in state['scenes']:
    print(f'     Сцена {s["index"]+1}: {s["text"]}')

# ── Шаг 2: AI картинки ──────────────────────────────────────────────────────
print('\n[2/5] 🎨 Генерация AI картинок (DALL-E 3)...')
state = generate_images_node(state)
imgs_ok = sum(1 for s in state['scenes'] if s.get('image_path'))
print(f'  {"✅" if imgs_ok == len(state["scenes"]) else "⚠️"}  Картинок: {imgs_ok}/{len(state["scenes"])}')

# ── Шаг 3: Голос ────────────────────────────────────────────────────────────
print('\n[3/5] 🎙  Голос персонажа (TTS)...')
state = generate_tts_node(state)
print(f'  {"✅" if state.get("audio_path") else "⚠️"}  {state.get("audio_path", "нет")}')

# ── Шаг 4: Музыка ───────────────────────────────────────────────────────────
print('\n[4/5] 🎵 Фоновая музыка...')
state = generate_music_node(state)
print(f'  {"✅" if state.get("music_path") else "⚠️"}  {state.get("music_path", "нет")}')

# ── Шаг 5: Сборка ───────────────────────────────────────────────────────────
print('\n[5/5] 🎬 Сборка финального видео...')
state = assemble_video_node(state)

if state.get('error'):
    print(f'  ❌  {state["error"]}')
    sys.exit(1)

video = state['video_path']
sz_mb = os.path.getsize(video) / 1024 / 1024

print()
print('=' * 60)
print(f'  ✅  ГОТОВО!')
print(f'  📁  {video}')
print(f'  📦  {sz_mb:.1f} MB')
print(f'  🎭  {char_name}')
print(f'  📖  {state["title"]}')
print('=' * 60)
print()
print('  Смотри видео:')
print('  python3 -m http.server 8080 --directory /var/data/ruflo-videos')
print(f'  Открой: http://46.101.135.99:8080/{CONTENT_ID}/')
