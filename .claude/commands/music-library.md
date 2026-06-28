---
name: music-library
description: Управление библиотекой фоновой музыки (Pixabay CC0 / Mubert API / lo-fi synth)
---

# Библиотека музыки

Система поддерживает 3 источника фоновой музыки (приоритет по убыванию):

| Уровень | Источник | Цена | Статус |
|---------|---------|------|--------|
| 1 | Mubert API | $14/мес | `MUBERT_API_KEY` в .env |
| 2 | Pixabay Library | Бесплатно | Треки в `MUSIC_LIBRARY_DIR` |
| 3 | Numpy lo-fi | Бесплатно | Всегда работает |

## Скачать Pixabay треки (рекомендуется)

```bash
# Скачать 10 CC0 треков в /tmp/pixabay-music/
python scripts/download-pixabay-music.py

# Добавить в .env:
echo 'MUSIC_LIBRARY_DIR=/tmp/pixabay-music' >> .env
```

## Проверить библиотеку

```bash
# Посмотреть треки
ls -lh ${MUSIC_LIBRARY_DIR:-/tmp/pixabay-music}/ 2>/dev/null || echo "Библиотека пуста"

# Сколько треков
ls ${MUSIC_LIBRARY_DIR:-/tmp/pixabay-music}/*.mp3 2>/dev/null | wc -l
```

## Подключить Mubert API ($14/мес)

1. Зарегистрироваться: https://mubert.com/render/pricing
2. Получить API ключ в личном кабинете
3. Добавить в `.env`:
```bash
MUBERT_API_KEY=ваш_ключ_здесь
```

Mubert автоматически подбирает настроение музыки под тему видео:
- Деньги/доход → `inspiring`
- AI/технологии → `focused`
- Вирал/шок → `energetic`
- Здоровье/спокойствие → `calm`

## Добавить свои треки в библиотеку

```bash
# Скопировать MP3 файлы в библиотеку
cp ~/Downloads/my-track.mp3 /tmp/pixabay-music/

# Требования к трекам:
# - Формат: MP3 или WAV
# - Лицензия: CC0, Royalty-Free или собственная
# - НЕ Spotify / Apple Music / YouTube Music (ContentID блокировка)
```

## Тест музыки

```bash
python -c "
import sys; sys.path.insert(0, 'src/content-automation/langgraph')
from nodes.music_generator import generate_music_node
state = {'content_id': 'music-test', 'scenes': [{'duration': 3}]*6, 'title': 'AI Tools'}
result = generate_music_node(state)
print('Music:', result.get('music_path', 'ОШИБКА'))
"
```
