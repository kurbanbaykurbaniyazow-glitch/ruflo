#!/usr/bin/env python3
"""
Полный пайплайн генерации вирального видео.

Формат: GPT-4o-mini пишет историю → Replicate/DALL-E генерирует персонажей →
        TTS озвучивает → музыка → FFmpeg собирает финальное видео.
Pexels видео используется только если AI-генерация недоступна.
"""
import sys, os, uuid

if '--run' not in sys.argv:
    print('⛔  Пайплайн отключён — идёт доработка.')
    print('   Когда будешь готов запустить: python3 scripts/test-viral-video.py --run')
    sys.exit(0)

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

has_openai    = bool(os.environ.get('OPENAI_API_KEY'))
has_replicate = bool(os.environ.get('REPLICATE_API_KEY'))
has_pexels    = bool(os.environ.get('PEXELS_API_KEY'))

print('=' * 60)
print('  Виральный видео пайплайн — AI персонажи')
print(f'  Replicate Flux     : {"✅ ГЛАВНЫЙ" if has_replicate else "❌ нет ключа"}')
print(f'  OpenAI (GPT + TTS) : {"✅" if has_openai else "❌ нет ключа"}')
print(f'  DALL-E (запасной)  : {"✅" if has_openai else "❌"}')
print(f'  Pexels (запасной)  : {"✅" if has_pexels else "❌"}')
print(f'  ID                 : {CONTENT_ID}')
print('=' * 60)

# ── Шаг 1: Сценарий ─────────────────────────────────────────────────────────
print('\n[1/6] 📝 Генерация сценария (GPT-4o-mini)...')
state = generate_story_node(state)
if state.get('error'):
    print(f'  ❌  {state["error"]}')
    sys.exit(1)
char_name = state.get('character', {}).get('name', '?')
char_emoji = state.get('character', {}).get('emoji', '🎭')
print(f'  ✅  "{state["title"]}"')
print(f'  {char_emoji}  Персонаж: {char_name}')
print(f'  📖  Тема: {state.get("theme", "")}')
print()
for s in state['scenes']:
    print(f'     Сцена {s["index"]+1}: {s["text"]}')

# ── Шаг 2: AI персонажи (ГЛАВНЫЙ шаг) ───────────────────────────────────────
print(f'\n[2/6] {char_emoji} Генерация AI персонажей для каждой сцены...')
if has_replicate:
    print('  🎨 Используем Replicate Flux Schnell (лучшее качество)')
elif has_openai:
    print('  🎨 Используем DALL-E (нет Replicate ключа)')
else:
    print('  ⚠️  Нет AI ключей — будет градиентный фон')
state = generate_images_node(state)
imgs_ok = sum(1 for s in state['scenes'] if s.get('image_path'))
print(f'  {"✅" if imgs_ok == len(state["scenes"]) else "⚠️"}  Персонажей: {imgs_ok}/{len(state["scenes"])}')

# ── Шаг 3: Pexels видео (запасной — только если нет AI картинок) ─────────────
scenes_without_img = sum(1 for s in state['scenes'] if not s.get('image_path'))
if scenes_without_img > 0 and has_pexels:
    print(f'\n[3/6] 🎬 Pexels для {scenes_without_img} сцен без AI картинки...')
    state = fetch_videos_node(state)
    clips_ok = sum(1 for s in state['scenes'] if s.get('clip_path'))
    print(f'  {"✅" if clips_ok else "⚠️"}  Клипов: {clips_ok}/{len(state["scenes"])}')
else:
    print('\n[3/6] 🎬 Все сцены имеют AI персонажей — Pexels не нужен')

# ── Шаг 4: Голос ────────────────────────────────────────────────────────────
print('\n[4/6] 🎙  Голос персонажа (TTS)...')
state = generate_tts_node(state)
print(f'  {"✅" if state.get("audio_path") else "⚠️"}  {state.get("audio_path", "нет")}')

# ── Шаг 5: Музыка ───────────────────────────────────────────────────────────
print('\n[5/6] 🎵 Фоновая музыка...')
state = generate_music_node(state)
print(f'  {"✅" if state.get("music_path") else "⚠️"}  {state.get("music_path", "нет")}')

# ── Шаг 6: Сборка ───────────────────────────────────────────────────────────
print('\n[6/6] 🔧 Сборка финального видео...')
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
