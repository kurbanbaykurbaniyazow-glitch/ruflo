---
name: pipeline-check
description: Проверить здоровье всего пайплайна генерации видео (ключи, зависимости, FFmpeg)
---

# Проверка пайплайна

Полная диагностика всех компонентов content-automation системы.

## Запустить проверку

```bash
python -c "
import os, sys, importlib

sys.path.insert(0, 'src/content-automation/langgraph')

print('=== ПАЙПЛАЙН ДИАГНОСТИКА ===')
print()

# 1. Python зависимости
deps = ['numpy', 'PIL', 'imageio_ffmpeg', 'langgraph']
print('[1] Python зависимости:')
for dep in deps:
    try:
        importlib.import_module(dep.replace('PIL', 'PIL.Image'))
        print(f'  ✅ {dep}')
    except:
        print(f'  ❌ {dep} — pip install {dep}')

# 2. FFmpeg
print()
print('[2] FFmpeg:')
try:
    import imageio_ffmpeg, subprocess
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    r = subprocess.run([ff, '-version'], capture_output=True, text=True)
    ver = r.stdout.split('\n')[0]
    print(f'  ✅ {ver}')
except Exception as e:
    print(f'  ❌ {e}')

# 3. Системные шрифты
print()
print('[3] Шрифты:')
fonts = [
    '/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
]
for f in fonts:
    if os.path.exists(f):
        print(f'  ✅ {os.path.basename(f)}')
        break
else:
    print('  ⚠️  Нет жирных шрифтов (текст может выглядеть хуже)')

# 4. API ключи
print()
print('[4] API ключи:')
env_path = '.env'
env = {}
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                k, v = line.strip().split('=', 1)
                env[k.strip()] = v.strip()

keys = {
    'ANTHROPIC_API_KEY': 'Claude (сценарии)',
    'PEXELS_API_KEY': 'Pexels (видеоклипы)',
    'ELEVENLABS_API_KEY': 'ElevenLabs (голос)',
    'OPENAI_API_KEY': 'OpenAI TTS (голос)',
    'MUBERT_API_KEY': 'Mubert (музыка)',
}
for k, label in keys.items():
    val = env.get(k) or os.environ.get(k, '')
    if val and len(val) > 5:
        print(f'  ✅ {label}')
    else:
        print(f'  ⚠️  {label} — не задан')

# 5. Музыкальная библиотека
print()
print('[5] Музыка:')
music_dir = env.get('MUSIC_LIBRARY_DIR') or os.environ.get('MUSIC_LIBRARY_DIR', '/tmp/pixabay-music')
from pathlib import Path
tracks = list(Path(music_dir).glob('*.mp3')) if Path(music_dir).exists() else []
if tracks:
    print(f'  ✅ Pixabay: {len(tracks)} треков в {music_dir}')
else:
    print(f'  ℹ️  Pixabay: пусто — используется numpy lo-fi')
    print(f'     Запусти: python scripts/download-pixabay-music.py')

# 6. TTS (Flite)
print()
print('[6] Offline TTS (Flite):')
import ctypes, ctypes.util
lib = ctypes.util.find_library('flite')
if lib:
    print(f'  ✅ libflite: {lib}')
else:
    for p in ['/usr/lib/x86_64-linux-gnu/libflite.so.1']:
        if os.path.exists(p):
            print(f'  ✅ libflite: {p}')
            break
    else:
        print('  ⚠️  libflite не найден — apt install flite')

print()
print('=== ГОТОВНОСТЬ ===')
"
```

## Быстрый тест компонентов

```bash
# Тест TTS
python -c "
import sys; sys.path.insert(0, 'src/content-automation/langgraph')
from nodes.tts_generator import generate_tts_node
r = generate_tts_node({'content_id': 'test-tts', 'script': 'Hello world, this is a test.'})
print('TTS:', '✅' if r.get('audio_path') else '❌', r.get('audio_path', r.get('error', '?')))
"

# Тест музыки
python -c "
import sys; sys.path.insert(0, 'src/content-automation/langgraph')
from nodes.music_generator import generate_music_node
r = generate_music_node({'content_id': 'test-music', 'scenes': [{'duration': 3}]*3, 'title': 'Test'})
print('Music:', '✅' if r.get('music_path') else '❌', r.get('music_path', '?'))
"
```

## Что делать если что-то не работает

| Проблема | Решение |
|---------|---------|
| FFmpeg ошибка | `pip install imageio-ffmpeg` |
| Нет libflite | `apt-get install flite` |
| Нет numpy/PIL | `pip install numpy pillow` |
| Нет голоса | Добавь `ELEVENLABS_API_KEY` или `OPENAI_API_KEY` в `.env` |
| Нет видеоклипов | Добавь `PEXELS_API_KEY` в `.env` |
| Музыка тихая | Запусти `/music-library` |
