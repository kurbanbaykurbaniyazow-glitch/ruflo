---
name: generate-video
description: Запустить полный пайплайн генерации видео (Pexels + TTS + Music + Assembly)
---

# Генерация видео

Запускает полный пайплайн: видеоклипы → голос → музыка → сборка финального MP4.

## Шаги

1. Проверь `.env` файл — нужны ключи:
   - `PEXELS_API_KEY` — для видеоклипов (без него работают слайды)
   - `ANTHROPIC_API_KEY` — для сценария (Claude Haiku/Sonnet)
   - Опционально: `ELEVENLABS_API_KEY`, `OPENAI_API_KEY` — для голоса
   - Опционально: `MUBERT_API_KEY` или `MUSIC_LIBRARY_DIR` — для музыки

2. Запусти тестовый пайплайн:
```bash
cd /home/user/ruflo
python scripts/test-viral-video.py
```

3. Проверь результат:
```bash
ls -lh /tmp/content-automation/test-viral-005/
# final.mp4 — готовое видео
# thumbnail.jpg — превью
# audio/voice.mp3 — голос
# audio/bgmusic.mp3 — музыка
```

4. Покажи информацию о видео:
```bash
python -c "
import imageio_ffmpeg, subprocess, os
ff = imageio_ffmpeg.get_ffmpeg_exe()
v = '/tmp/content-automation/test-viral-005/final.mp4'
r = subprocess.run([ff, '-i', v], capture_output=True, text=True)
for line in r.stderr.split('\n'):
    if any(x in line for x in ['Duration', 'Video', 'Audio']):
        print(line.strip())
sz = os.path.getsize(v)/1024/1024
print(f'Size: {sz:.1f} MB')
"
```

## Кастомный контент

Чтобы изменить тему видео, отредактируй `scripts/test-viral-video.py`:
- `CONTENT_ID` — уникальный ID (папка сохранения)
- `SCENES` — список сцен с текстом и длительностью
- `FULL_SCRIPT` — полный текст для голоса

## Проблемы

- **Нет Pexels клипов** → используются градиентные слайды (нормально)
- **Нет голоса** → используется Flite offline TTS
- **Нет музыки** → генерируется lo-fi синтез numpy
- **FFmpeg ошибка** → проверь `pip install imageio-ffmpeg`
