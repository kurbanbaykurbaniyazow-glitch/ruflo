---
name: video-status
description: Показать все сгенерированные видео с размерами и продолжительностью
---

# Статус видео

Показывает все готовые видео в папке вывода.

## Список всех видео

```bash
python -c "
import os, subprocess
from pathlib import Path

output_dir = Path(os.environ.get('VIDEO_OUTPUT_DIR', '/tmp/content-automation'))

if not output_dir.exists():
    print('Нет видео. Запусти /generate-video')
    exit()

videos = list(output_dir.rglob('final.mp4'))
if not videos:
    print('Нет готовых видео. Запусти /generate-video')
    exit()

try:
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
except:
    ff = 'ffmpeg'

print(f'Найдено видео: {len(videos)}')
print('=' * 55)
for v in sorted(videos):
    sz = v.stat().st_size / 1024 / 1024
    content_id = v.parent.name
    r = subprocess.run([ff, '-i', str(v)], capture_output=True, text=True)
    dur = '?'
    for line in r.stderr.split('\n'):
        if 'Duration' in line:
            dur = line.strip().split(',')[0].replace('Duration: ', '')
            break
    thumb = '✅' if (v.parent / 'thumbnail.jpg').exists() else '❌'
    print(f'{content_id}')
    print(f'  📹 {v}')
    print(f'  ⏱  {dur}  |  💾 {sz:.1f} MB  |  🖼 thumbnail: {thumb}')
    print()
"
```

## Показать аудио-дорожки видео

```bash
python -c "
import sys, os, subprocess
from pathlib import Path

video_file = sys.argv[1] if len(sys.argv) > 1 else None
if not video_file:
    # Найти последнее видео
    output_dir = Path(os.environ.get('VIDEO_OUTPUT_DIR', '/tmp/content-automation'))
    videos = sorted(output_dir.rglob('final.mp4'))
    if not videos:
        print('Нет видео')
        exit()
    video_file = str(videos[-1])

try:
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
except:
    ff = 'ffmpeg'

print(f'Файл: {video_file}')
r = subprocess.run([ff, '-i', video_file], capture_output=True, text=True)
for line in r.stderr.split('\n'):
    if any(x in line for x in ['Duration', 'Video:', 'Audio:', 'Stream']):
        print(' ', line.strip())
"
```

## Открыть папку с видео

```bash
# Показать путь
echo "VIDEO_OUTPUT_DIR: ${VIDEO_OUTPUT_DIR:-/tmp/content-automation}"
ls -lh ${VIDEO_OUTPUT_DIR:-/tmp/content-automation}/*/final.mp4 2>/dev/null || echo "Нет видео"
```

## Очистить старые видео

```bash
# Удалить все временные файлы, оставить только final.mp4 и thumbnail.jpg
find ${VIDEO_OUTPUT_DIR:-/tmp/content-automation} -name "scene_*.mp4" -delete
find ${VIDEO_OUTPUT_DIR:-/tmp/content-automation} -name "raw_*.mp4" -delete
find ${VIDEO_OUTPUT_DIR:-/tmp/content-automation} -name "slideshow_raw.mp4" -delete
find ${VIDEO_OUTPUT_DIR:-/tmp/content-automation} -name "slide_*.jpg" -delete
echo "Очищено. Остались только final.mp4 и thumbnail.jpg"
```
