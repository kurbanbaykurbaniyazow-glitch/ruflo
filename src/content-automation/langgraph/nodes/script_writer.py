"""
Script writer — глубокий сторителлинг с фруктовыми персонажами.

Формат: 20 сцен × 6 секунд = ~2 минуты
Структура: хук → знакомство → предыстория → нарастание → конфликт →
           кризис → поворот → развязка → мораль → CTA
"""
import json
import os
import random
import re
from openai import OpenAI

client = OpenAI()

# ── Character roster ──────────────────────────────────────────────────────────

CHARACTERS = [
    {
        'name': 'Банан-моряк',
        'image_base': 'anthropomorphic banana character with a yellow banana head and human body, wearing a white sailor uniform with a captain hat, standing on a ship deck with ocean waves behind, highly detailed 3D cartoon render, Pixar style, expressive face, cinematic lighting',
        'voice': 'эмоциональный, драматичный, говорит с надрывом',
        'emoji': '🍌',
        'backstory': 'моряк который видел весь мир но потерял самое важное дома',
    },
    {
        'name': 'Клубника-подруга',
        'image_base': 'anthropomorphic strawberry character with a red strawberry head with green leaves on top, human female body wearing stylish Tommy Hilfiger streetwear, standing in a luxury penthouse with city view, highly detailed 3D cartoon render, Pixar style, confident expression',
        'voice': 'дерзкая, уверенная, говорит прямо',
        'emoji': '🍓',
        'backstory': 'девушка которая добилась всего сама но за это заплатила высокую цену',
    },
    {
        'name': 'Авокадо-босс',
        'image_base': 'anthropomorphic avocado character with a green avocado head, human body in expensive business suit and tie, sitting at executive office desk with city skyline behind, highly detailed 3D cartoon render, Pixar style, serious expression, dramatic office lighting',
        'voice': 'важный, серьёзный, говорит официально',
        'emoji': '🥑',
        'backstory': 'бизнесмен который построил империю но остался один',
    },
    {
        'name': 'Помидор-судья',
        'image_base': 'anthropomorphic tomato character with a red round tomato head, human body wearing black judge robes, sitting at courtroom bench with gavel, highly detailed 3D cartoon render, Pixar style, stern authoritative expression, dramatic courtroom lighting',
        'voice': 'строгий, официальный, категоричный',
        'emoji': '🍅',
        'backstory': 'судья который всю жизнь судил других и однажды сам оказался на скамье подсудимых',
    },
    {
        'name': 'Ананас-король',
        'image_base': 'anthropomorphic pineapple character with a golden pineapple head with crown on top, human body in royal purple velvet robes with golden trim, sitting on magnificent golden throne in palace hall, highly detailed 3D cartoon render, Pixar style, regal majestic expression, epic golden lighting',
        'voice': 'величественный, драматичный, говорит пафосно',
        'emoji': '🍍',
        'backstory': 'король у которого есть всё кроме того единственного что он хочет',
    },
    {
        'name': 'Огурец-детектив',
        'image_base': 'anthropomorphic cucumber character with a long green cucumber head, human body wearing brown trench coat and fedora hat, standing in rainy noir city street at night with neon lights reflecting on wet pavement, highly detailed 3D cartoon render, Pixar style, mysterious brooding expression',
        'voice': 'загадочный, спокойный, говорит с расстановкой',
        'emoji': '🥒',
        'backstory': 'детектив который раскрыл тысячи дел но не может раскрыть тайну собственной жизни',
    },
]

# ── Story themes — глубокие, эмоционально насыщенные ─────────────────────────

THEMES = [
    {
        'theme': 'лучший друг предал в самый важный момент жизни',
        'hook': 'Ты когда-нибудь терял лучшего друга не потому что он умер а потому что он выбрал деньги?',
        'moral': 'Настоящая дружба проверяется не в праздники а в кризис. Кто остался рядом — тот и есть твой человек.',
    },
    {
        'theme': 'работал 10 лет ради мечты и всё потерял за один день',
        'hook': 'Десять лет. Десять лет я строил это. И всё рухнуло за один звонок.',
        'moral': 'Падение — это не конец. Это перезагрузка. Я понял это только потеряв всё.',
    },
    {
        'theme': 'влюбился в человека который любил другого',
        'hook': 'Я три года ждал пока он заметит меня. А он всё это время смотрел в другую сторону.',
        'moral': 'Нельзя заставить человека полюбить тебя. Можно только найти того кто полюбит сам.',
    },
    {
        'theme': 'ушёл с высокооплачиваемой работы ради мечты и не пожалел',
        'hook': 'Все говорили что я схожу с ума. Стабильная зарплата, карьера, перспективы. Я уволился в пятницу.',
        'moral': 'Безопасность — это иллюзия. Настоящая безопасность это когда ты живёшь своей жизнью а не чужой.',
    },
    {
        'theme': 'родители не верили в меня но я доказал им что они ошибались',
        'hook': 'Мне было 15 когда отец сказал: из тебя ничего не выйдет. Сегодня мне 32 и я хочу рассказать что было дальше.',
        'moral': 'Чужие слова могут ранить. Но только ты решаешь позволить им остановить тебя или стать топливом.',
    },
    {
        'theme': 'узнал правду о себе которая изменила всё',
        'hook': 'Одно письмо. Я нашёл его случайно. И после этого я уже никогда не был прежним.',
        'moral': 'Правда болит. Но жить во лжи больнее. Знание о себе — это не приговор, это свобода.',
    },
    {
        'theme': 'простил человека который сломал мою жизнь',
        'hook': 'Он разрушил всё что у меня было. И я решил его простить. Не ради него. Ради себя.',
        'moral': 'Прощение — это не оправдание плохого поступка. Это освобождение себя от груза чужой вины.',
    },
    {
        'theme': 'начал всё с нуля в 40 лет и стал счастливее чем был в 20',
        'hook': 'В 40 лет у меня не было ничего. Ни денег, ни семьи, ни планов. И это оказалось лучшим что со мной случалось.',
        'moral': 'Никогда не поздно начать заново. Поздно только когда ты перестаёшь верить что это возможно.',
    },
]

CTA_VARIANTS = [
    'Если эта история тебя задела — напиши в комментарии своё имя. Ты не один. И подпишись — я выпускаю новые истории каждый день.',
    'У тебя была похожая ситуация? Напиши в комментарии. Это важно — знать что ты не один. Подпишись чтобы не пропустить продолжение.',
    'Эта история реальная. Если она тебя тронула — поставь лайк и подпишись. Завтра будет следующая часть.',
    'Ты дочитал до конца — значит это тебя задело. Напиши в комментарии что ты думаешь. Подпишись — таких историй будет ещё много.',
    'Если в твоей жизни было что-то похожее — ты сильнее чем думаешь. Подпишись и напиши свою историю в комментариях.',
]


# ── Moods for 20-scene arc ────────────────────────────────────────────────────

_MOOD_QUERIES = [
    'calm wide establishing shot',          # 0  — хук
    'close emotional face tense',           # 1  — знакомство
    'warm nostalgic portrait',              # 2  — кто я
    'contemplative window light',           # 3  — предыстория начало
    'hopeful determined face',              # 4  — предыстория развитие
    'warm memory nostalgic',               # 5  — лучший момент
    'worried anxious expression',           # 6  — первый знак
    'tense dramatic close face',            # 7  — нарастание
    'conflict confrontation intense',       # 8  — конфликт
    'shocked betrayed expression',          # 9  — удар
    'breaking down emotional peak',         # 10 — кризис
    'alone dark room dramatic',             # 11 — самое дно
    'turning point realization face',       # 12 — поворот
    'determined rising action',             # 13 — подъём
    'confrontation resolution face',        # 14 — развязка
    'relief emotional tears',              # 15 — освобождение
    'reflective calm after storm',          # 16 — итог
    'wise knowing subtle smile',            # 17 — мораль
    'looking at camera direct warm',        # 18 — к зрителю
    'breaking fourth wall friendly camera', # 19 — CTA
]

_CHARACTER_PEXELS = {
    'Банан-моряк': {
        'setting': [
            'ocean horizon ship', 'sailor portrait dramatic', 'stormy sea waves', 'harbor sunset ship',
            'ship deck dramatic', 'ocean storm waves', 'lighthouse dramatic', 'sailor contemplative sea',
            'ship cabin emotional', 'ocean night stars', 'port farewell dramatic', 'sea fog mysterious',
            'sailor letter reading', 'ocean sunrise hope', 'ship steering wheel', 'storm survival dramatic',
            'calm sea reflection', 'sailor homecoming port', 'ocean vast lonely', 'ship sunset journey',
        ],
    },
    'Клубника-подруга': {
        'setting': [
            'luxury penthouse city', 'confident woman portrait', 'city rooftop night', 'fashion street style',
            'woman office determined', 'luxury apartment alone', 'city lights emotional', 'woman mirror reflection',
            'successful woman thinking', 'cafe window thoughtful', 'woman phone call tense', 'city rain window',
            'woman crying emotional', 'luxury empty feeling', 'woman walking city night', 'fashion show dramatic',
            'woman reading letter', 'city park contemplative', 'woman smiling genuine', 'woman camera direct',
        ],
    },
    'Авокадо-босс': {
        'setting': [
            'corporate office dramatic', 'businessman portrait serious', 'boardroom meeting tense', 'executive desk alone',
            'business handshake dramatic', 'office night overtime', 'businessman contemplative window', 'deal signing dramatic',
            'office conflict dramatic', 'businessman shocked face', 'office empty fired', 'businessman walking street',
            'business failure dramatic', 'businessman park bench', 'office rebuilding determined', 'business meeting success',
            'executive calm wisdom', 'businessman family reunion', 'business casual warm', 'businessman direct camera',
        ],
    },
    'Помидор-судья': {
        'setting': [
            'courtroom dramatic gavel', 'judge portrait serious', 'legal trial tense', 'courthouse steps dramatic',
            'judge reading papers', 'courtroom empty night', 'judge contemplative window', 'legal documents dramatic',
            'courtroom conflict dramatic', 'judge shocked revelation', 'empty courtroom alone', 'judge walking corridor',
            'trial turning point', 'judge outside courthouse', 'legal victory dramatic', 'judge emotional moment',
            'courthouse reflection pond', 'judge wise portrait', 'legal justice warm', 'judge direct camera',
        ],
    },
    'Ананас-король': {
        'setting': [
            'throne room palace epic', 'royal portrait dramatic', 'palace corridor lonely', 'golden hall ceremony',
            'king reading scroll', 'palace window alone', 'royal garden contemplative', 'throne empty dramatic',
            'palace conflict dramatic', 'king shocked revelation', 'king alone throne', 'palace night walking',
            'royal crisis dramatic', 'king outside walls', 'palace reunion joyful', 'king emotional tears',
            'palace garden peace', 'king wise portrait', 'royal warm casual', 'king direct camera',
        ],
    },
    'Огурец-детектив': {
        'setting': [
            'noir city rain night', 'detective portrait mysterious', 'dark alley investigation', 'city lights reflection',
            'detective reading files', 'office noir lamp dramatic', 'detective window thinking', 'crime scene dramatic',
            'detective confrontation tense', 'shocked detective face', 'detective alone bar', 'city walking night rain',
            'investigation turning point', 'detective outside city', 'case solved dramatic', 'detective emotional moment',
            'city sunrise after rain', 'detective wise portrait', 'detective casual warm', 'detective direct camera',
        ],
    },
}


def _scene_image_prompt(character: dict, scene_text: str, scene_idx: int, total: int) -> str:
    """Build DALL-E / Flux image prompt based on story arc position."""
    base = character['image_base']
    ratio = scene_idx / max(total - 1, 1)

    if scene_idx == 0:
        mood = 'dramatic establishing shot, wide angle, intense atmosphere'
    elif ratio < 0.15:
        mood = 'close-up portrait, introducing character, calm but determined expression'
    elif ratio < 0.30:
        mood = 'warm nostalgic lighting, thoughtful expression, backstory mood'
    elif ratio < 0.45:
        mood = 'tense expression, worried, something is wrong'
    elif ratio < 0.55:
        mood = 'intense dramatic, conflict, angry or shocked expression, high contrast lighting'
    elif ratio < 0.65:
        mood = 'broken, emotional, lowest point, tears or despair expression'
    elif ratio < 0.75:
        mood = 'turning point, realization, determined expression rising from darkness'
    elif ratio < 0.85:
        mood = 'resolution, calm after storm, subtle smile, relief expression'
    elif ratio < 0.95:
        mood = 'wise, reflective, looking into distance, peaceful expression'
    else:
        mood = 'looking directly at camera, breaking fourth wall, warm inviting expression'

    return f'{base}, {mood}, vertical 9:16 format, no text'


def _scene_pexels_query(character: dict, scene_idx: int, total: int) -> str:
    """Build a unique Pexels search query per scene."""
    name = character.get('name', '')
    pexels = _CHARACTER_PEXELS.get(name, {})
    settings = pexels.get('setting', ['dramatic cinematic portrait'])
    setting = settings[scene_idx % len(settings)]
    mood = _MOOD_QUERIES[min(scene_idx, len(_MOOD_QUERIES) - 1)]
    return f'{setting} {mood}'


# ── Main generator ────────────────────────────────────────────────────────────

def generate_story_node(state: dict) -> dict:
    """
    LangGraph node: generate a deep 2-minute story with character.
    20 scenes × ~6 seconds = ~2 minutes total.
    """
    character = random.choice(CHARACTERS)
    theme_data = random.choice(THEMES)
    theme = theme_data['theme']
    hook = theme_data['hook']
    moral = theme_data['moral']
    cta = random.choice(CTA_VARIANTS)

    prompt = f"""Ты — сценарист глубокого эмоционального контента для коротких видео (формат YouTube Shorts / TikTok).

ПЕРСОНАЖ: {character['name']}
ХАРАКТЕР: {character['voice']}
ПРЕДЫСТОРИЯ ПЕРСОНАЖА: {character['backstory']}
ТЕМА: {theme}
ОТКРЫВАЮЩИЙ ХУКИ: {hook}
МОРАЛЬ ИСТОРИИ: {moral}
ПРИЗЫВ К ДЕЙСТВИЮ: {cta}

ЗАДАЧА: Напиши историю из РОВНО 20 сцен. Это полноценная 2-минутная история которая захватит зрителя с первой секунды и не отпустит до конца.

СТРУКТУРА (строго соблюдай):
- Сцена 1 (ХУК): Используй точный текст хука выше — шокирующий вопрос или факт
- Сцены 2-3 (ЗНАКОМСТВО): Кто я, моя ситуация до событий, чем жил
- Сцены 4-6 (ПРЕДЫСТОРИЯ): Как всё началось, лучший период, что было поставлено на карту
- Сцены 7-9 (НАРАСТАНИЕ): Первые тревожные знаки, что-то пошло не так
- Сцены 10-12 (КОНФЛИКТ/КРИЗИС): Самый тяжёлый момент, удар, самое дно
- Сцены 13-15 (ПОВОРОТ): Что изменило всё, решение, первый шаг вперёд
- Сцены 16-18 (РАЗВЯЗКА): Чем закончилось, что изменилось во мне
- Сцена 19 (МОРАЛЬ): Главный урок — используй текст морали выше
- Сцена 20 (CTA): Обращение к зрителю — используй текст CTA выше

ПРАВИЛА НАПИСАНИЯ:
- Пиши от ПЕРВОГО ЛИЦА (персонаж рассказывает сам о себе)
- Каждая сцена: 25-40 слов (это ~6 секунд речи)
- Разговорный живой язык — как будто друг рассказывает за чашкой чая
- Эмоционально, честно, без пафоса
- Каждая сцена должна либо раскрывать что-то новое либо усиливать эмоцию
- Сцены 10-12 должны быть самыми драматичными — читатель должен почувствовать боль
- Сцены 16-19 должны давать надежду и смысл
- НЕ используй оскорблений, мата, расизма, дискриминации

ВЕРНИ ТОЛЬКО JSON без пояснений:
{{
  "title": "цепляющий заголовок истории (до 8 слов)",
  "character": "{character['name']}",
  "scenes": [
    {{"index": 0, "text": "текст сцены 1 (хук)", "duration": 6}},
    {{"index": 1, "text": "текст сцены 2", "duration": 6}},
    {{"index": 2, "text": "текст сцены 3", "duration": 6}},
    {{"index": 3, "text": "текст сцены 4", "duration": 6}},
    {{"index": 4, "text": "текст сцены 5", "duration": 6}},
    {{"index": 5, "text": "текст сцены 6", "duration": 6}},
    {{"index": 6, "text": "текст сцены 7", "duration": 6}},
    {{"index": 7, "text": "текст сцены 8", "duration": 6}},
    {{"index": 8, "text": "текст сцены 9", "duration": 6}},
    {{"index": 9, "text": "текст сцены 10", "duration": 7}},
    {{"index": 10, "text": "текст сцены 11", "duration": 7}},
    {{"index": 11, "text": "текст сцены 12", "duration": 7}},
    {{"index": 12, "text": "текст сцены 13", "duration": 6}},
    {{"index": 13, "text": "текст сцены 14", "duration": 6}},
    {{"index": 14, "text": "текст сцены 15", "duration": 6}},
    {{"index": 15, "text": "текст сцены 16", "duration": 6}},
    {{"index": 16, "text": "текст сцены 17", "duration": 6}},
    {{"index": 17, "text": "текст сцены 18", "duration": 6}},
    {{"index": 18, "text": "текст сцены 19 (мораль)", "duration": 7}},
    {{"index": 19, "text": "текст сцены 20 (CTA)", "duration": 7}}
  ]
}}"""

    print(f'[ScriptWriter] {character["emoji"]} {character["name"]} | Тема: {theme}')

    response = client.chat.completions.create(
        model='gpt-4o-mini',
        max_tokens=4000,
        temperature=0.85,
        messages=[{'role': 'user', 'content': prompt}],
    )

    raw = response.choices[0].message.content if response.choices else ''
    json_match = re.search(r'\{[\s\S]*\}', raw)

    if not json_match:
        return {**state, 'scenes': [], 'error': f'Script parse failed: {raw[:200]}'}

    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError as e:
        return {**state, 'scenes': [], 'error': f'JSON decode error: {e}'}

    scenes = data.get('scenes', [])
    title = data.get('title', theme)

    total_sec = sum(s.get('duration', 6) for s in scenes)

    for s in scenes:
        s['image_prompt'] = _scene_image_prompt(character, s['text'], s['index'], len(scenes))
        s['pexels_query'] = _scene_pexels_query(character, s['index'], len(scenes))
        s['character'] = character['name']

    print(f'[ScriptWriter] ✅ "{title}" — {len(scenes)} сцен, ~{total_sec}с ({total_sec//60}м{total_sec%60}с)')
    for s in scenes:
        print(f'  [{s["index"]+1:02d}] {s["text"][:70]}')

    return {
        **state,
        'title': title,
        'character': character,
        'theme': theme,
        'scenes': scenes,
        'script': ' '.join(s['text'] for s in scenes),
        'error': None,
    }


# ── Backwards-compatible parse-only node ─────────────────────────────────────

def write_script_node(state: dict) -> dict:
    """LangGraph node: if script already provided, parse it into scenes."""
    if state.get('scenes'):
        return state
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
                'duration': max(5, len(sent.split()) // 2),
            }
            for i, sent in enumerate(sentences[:20])
        ]
    else:
        scenes = [
            {
                'index': int(num) - 1,
                'text': text.strip(),
                'image_prompt': f'Cinematic visual: {text.strip()[:80]}',
                'duration': max(5, len(text.split()) // 2),
            }
            for num, text in matches
        ]

    return {**state, 'scenes': scenes, 'error': None}
