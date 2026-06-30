"""
Script writer — entertainment format with fruit/vegetable characters.

Format inspired by viral TikTok AI-character videos:
- Anthropomorphic fruit/vegetable protagonist
- Comedic story with clear narrative arc (setup → conflict → resolution)
- Word-by-word subtitles
- Final scene: character breaks 4th wall with subscribe/comment CTA
"""
import json
import os
import random
import re
from anthropic import Anthropic

client = Anthropic()

# ── Character roster ──────────────────────────────────────────────────────────

CHARACTERS = [
    {
        'name': 'Банан-моряк',
        'image_base': 'a dramatic red banana character wearing a sailor uniform on a ship deck, photorealistic 3D render, cinematic lighting',
        'voice': 'эмоциональный, драматичный, говорит с надрывом',
        'emoji': '🍌',
    },
    {
        'name': 'Клубника-подруга',
        'image_base': 'a strawberry-headed girl character in stylish streetwear Tommy Hilfiger, sitting in a luxury penthouse, photorealistic 3D render',
        'voice': 'дерзкая, уверенная, говорит прямо',
        'emoji': '🍓',
    },
    {
        'name': 'Авокадо-босс',
        'image_base': 'an avocado-headed businessman in an expensive suit at a corporate office, photorealistic 3D render, dramatic lighting',
        'voice': 'важный, серьёзный, говорит официально',
        'emoji': '🥑',
    },
    {
        'name': 'Помидор-судья',
        'image_base': 'a tomato-headed judge in court robes banging a gavel in a courtroom, photorealistic 3D render',
        'voice': 'строгий, официальный, категоричный',
        'emoji': '🍅',
    },
    {
        'name': 'Ананас-король',
        'image_base': 'a pineapple-headed king in royal robes sitting on a golden throne, photorealistic 3D render, epic lighting',
        'voice': 'величественный, драматичный, говорит пафосно',
        'emoji': '🍍',
    },
    {
        'name': 'Огурец-детектив',
        'image_base': 'a cucumber-headed detective in a trench coat under rain in a noir city street, photorealistic 3D render',
        'voice': 'загадочный, спокойный, говорит с расстановкой',
        'emoji': '🥒',
    },
]

# ── Story themes (universally relatable, emotionally engaging) ────────────────

THEMES = [
    'лучший друг предал в самый важный момент',
    'уволили с работы в день рождения',
    'влюбился но не решается признаться',
    'новый начальник оказался хуже старого',
    'поехал в отпуск и всё пошло не так',
    'купил дорогую вещь и пожалел',
    'пытается произвести впечатление на девушку',
    'узнал что лучший друг за спиной говорил плохое',
    'решил изменить жизнь но ничего не вышло',
    'сделал доброе дело и пожалел об этом',
]

CTA_VARIANTS = [
    'Если узнал себя — подпишись и напиши в комментарии своя история!',
    'Подпишись чтобы не пропустить продолжение этой истории!',
    'Напиши в комментарии — ты бы так поступил? И подпишись на канал!',
    'Это только первая часть. Подпишись чтобы узнать чем всё закончилось!',
    'Ставь лайк если было смешно и подпишись — выпускаем новые серии каждый день!',
]


# ── Scene image prompt builder ────────────────────────────────────────────────

def _scene_image_prompt(character: dict, scene_text: str, scene_idx: int, total: int) -> str:
    """Build DALL-E / SD image prompt for a scene."""
    base = character['image_base']
    if scene_idx == 0:
        mood = 'calm, establishing shot, wide angle'
    elif scene_idx < total // 2:
        mood = 'tense, close-up face, emotional expression'
    elif scene_idx < total - 1:
        mood = 'dramatic, action, intense expression'
    else:
        mood = 'looking directly at camera, breaking fourth wall, friendly expression'

    return f'{base}, {mood}, vertical 9:16 format, no text'


# ── Main generator ────────────────────────────────────────────────────────────

def generate_story_node(state: dict) -> dict:
    """
    LangGraph node: generate a complete entertainment story with character.
    Produces scenes with text + image_prompt for each beat of the story.
    """
    character = random.choice(CHARACTERS)
    theme = random.choice(THEMES)
    cta = random.choice(CTA_VARIANTS)

    prompt = f"""Ты — сценарист вирального TikTok контента. Создай короткую историю для видео.

ПЕРСОНАЖ: {character['name']} ({character['voice']})
ТЕМА: {theme}
ФОРМАТ: 6 сцен, каждая 3-4 секунды (10-15 слов максимум на сцену)

СТРУКТУРА ИСТОРИИ:
- Сцена 1: Зацепи зрителя (вопрос или шокирующий факт)
- Сцена 2-3: Раскрой ситуацию (что произошло)
- Сцена 4-5: Конфликт или поворот (эмоциональный пик)
- Сцена 6: Концовка с призывом ({cta})

ПРАВИЛА:
- Пиши от первого лица (персонаж рассказывает сам)
- Короткие ударные фразы
- Эмоционально, смешно, узнаваемо
- Последняя сцена ВСЕГДА заканчивается призывом подписаться/комментировать
- Не используй оскорблений, мата, расизма

ВЕРНИ ТОЛЬКО JSON (без пояснений):
{{
  "title": "заголовок истории",
  "character": "{character['name']}",
  "scenes": [
    {{"index": 0, "text": "текст сцены 1", "duration": 3}},
    {{"index": 1, "text": "текст сцены 2", "duration": 3}},
    {{"index": 2, "text": "текст сцены 3", "duration": 3}},
    {{"index": 3, "text": "текст сцены 4", "duration": 4}},
    {{"index": 4, "text": "текст сцены 5", "duration": 3}},
    {{"index": 5, "text": "текст сцены 6 с призывом", "duration": 4}}
  ]
}}"""

    print(f'[ScriptWriter] Персонаж: {character["emoji"]} {character["name"]} | Тема: {theme}')

    response = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=1024,
        messages=[{'role': 'user', 'content': prompt}],
    )

    raw = response.content[0].text if response.content else ''
    json_match = re.search(r'\{[\s\S]*\}', raw)

    if not json_match:
        return {**state, 'scenes': [], 'error': f'Script parse failed: {raw[:200]}'}

    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError as e:
        return {**state, 'scenes': [], 'error': f'JSON decode error: {e}'}

    scenes = data.get('scenes', [])
    title = data.get('title', theme)

    # Add image prompts to each scene
    for s in scenes:
        s['image_prompt'] = _scene_image_prompt(character, s['text'], s['index'], len(scenes))
        s['character'] = character['name']

    print(f'[ScriptWriter] ✅ "{title}" — {len(scenes)} сцен')
    for s in scenes:
        print(f'  Сцена {s["index"]+1}: {s["text"][:60]}')

    return {
        **state,
        'title': title,
        'character': character,
        'theme': theme,
        'scenes': scenes,
        'script': ' '.join(s['text'] for s in scenes),
        'error': None,
    }


# ── Backwards-compatible parse-only node (used if script is pre-written) ─────

def write_script_node(state: dict) -> dict:
    """LangGraph node: if script already provided, parse it into scenes."""
    if state.get('scenes'):
        return state  # already has scenes
    if not state.get('script'):
        return generate_story_node(state)

    script: str = state['script']
    pattern = r'\[SCENE\s*(\d+)\]:\s*(.+?)(?=\[SCENE|\Z)'
    matches = re.findall(pattern, script, re.DOTALL)

    if not matches:
        sentences = [s.strip() for s in script.split('.') if s.strip()]
        scenes = [
            {
                'index': i,
                'text': sent + '.',
                'image_prompt': f'Cinematic visual: {sent[:80]}',
                'duration': max(3, len(sent.split()) // 2),
            }
            for i, sent in enumerate(sentences[:8])
        ]
    else:
        scenes = [
            {
                'index': int(num) - 1,
                'text': text.strip(),
                'image_prompt': f'Cinematic visual: {text.strip()[:80]}',
                'duration': max(3, len(text.split()) // 2),
            }
            for num, text in matches
        ]

    return {**state, 'scenes': scenes, 'error': None}
