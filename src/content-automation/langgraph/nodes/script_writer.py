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
    'Подпишись на канал — завтра выйдет следующая история. Пиши в комментарии: ты узнал себя в этой истории?',
    'Нажми подписаться чтобы не пропустить следующее видео. Каждый день — новая история. Напиши в комментарии свою.',
    'Подпишись прямо сейчас — следующая история выйдет завтра и она ещё сильнее. Напиши в комментарии что ты думаешь.',
    'Если эта история тебя задела — подпишись на канал. Новые истории каждый день. Напиши в комментарии была ли у тебя похожая ситуация.',
    'Подписывайся чтобы не пропустить продолжение. Завтра расскажу что случилось дальше. Напиши в комментарии — ты бы так поступил?',
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


# ── Stage 1: Generate 5 concepts ─────────────────────────────────────────────

def _generate_concepts(character: dict) -> list[dict]:
    """
    Ask GPT to create 5 different story concepts for this character.
    Returns list of dicts with: theme, hook, moral, emotional_angle, viral_reason.
    """
    prompt = f"""Ты — опытный сценарист вирального контента для YouTube Shorts и TikTok.

ПЕРСОНАЖ: {character['name']}
ГОЛОС: {character['voice']}
ПРЕДЫСТОРИЯ: {character['backstory']}

Придумай 5 РАЗНЫХ концептов историй для этого персонажа. Каждый концепт должен быть:
- Эмоционально сильным (слёзы, смех, узнавание себя)
- Универсально понятным (любой зритель скажет "это про меня")
- С неожиданным поворотом или откровением
- Разным по жанру: трагедия, триумф, предательство, любовь, перерождение

ВЕРНИ ТОЛЬКО JSON:
{{
  "concepts": [
    {{
      "id": 1,
      "theme": "тема в одной фразе",
      "hook": "первая фраза которая зацепит зрителя (вопрос или шокирующий факт, до 20 слов)",
      "moral": "главный урок истории (одно предложение)",
      "emotional_angle": "главная эмоция: предательство/триумф/потеря/любовь/перерождение",
      "viral_score": 0,
      "viral_reason": "почему именно эта история наберёт просмотры"
    }},
    ... (ещё 4 концепта)
  ]
}}"""

    response = client.chat.completions.create(
        model='gpt-4o-mini',
        max_tokens=2000,
        temperature=0.9,
        messages=[{'role': 'user', 'content': prompt}],
    )
    raw = response.choices[0].message.content if response.choices else ''
    match = re.search(r'\{[\s\S]*\}', raw)
    if not match:
        return []
    try:
        data = json.loads(match.group())
        return data.get('concepts', [])
    except json.JSONDecodeError:
        return []


def _pick_best_concept(concepts: list[dict], character: dict) -> dict:
    """
    Ask GPT to score all 5 concepts and return the winner.
    Criteria: emotional impact, universal relatability, viral potential, narrative strength.
    """
    concepts_text = '\n'.join(
        f"Концепт {c['id']}: {c['theme']}\n  Хук: {c['hook']}\n  Эмоция: {c['emotional_angle']}\n  Почему вирусный: {c['viral_reason']}"
        for c in concepts
    )

    prompt = f"""Ты — редактор вирального контента с 10-летним опытом в YouTube Shorts.

ПЕРСОНАЖ: {character['name']} ({character['voice']})

Оцени эти 5 концептов историй по шкале 1-10 по критериям:
- Эмоциональный удар (насколько зритель почувствует что-то сильное)
- Универсальность (насколько многие узнают себя)
- Вирусный потенциал (насколько захотят поделиться)
- Сила нарратива (насколько история держит до конца)

{concepts_text}

ВЕРНИ ТОЛЬКО JSON:
{{
  "scores": [
    {{"id": 1, "emotional": 8, "universal": 7, "viral": 9, "narrative": 8, "total": 32, "verdict": "почему выбрал или не выбрал"}},
    ... (для всех 5)
  ],
  "winner_id": 3,
  "winner_reason": "почему именно этот концепт лучший"
}}"""

    response = client.chat.completions.create(
        model='gpt-4o-mini',
        max_tokens=1000,
        temperature=0.3,
        messages=[{'role': 'user', 'content': prompt}],
    )
    raw = response.choices[0].message.content if response.choices else ''
    match = re.search(r'\{[\s\S]*\}', raw)
    if not match:
        return concepts[0]
    try:
        data = json.loads(match.group())
        winner_id = data.get('winner_id', 1)
        winner = next((c for c in concepts if c['id'] == winner_id), concepts[0])
        print(f'[ScriptWriter] 🏆 Победитель: концепт #{winner_id} — {data.get("winner_reason", "")}')
        scores = {s['id']: s['total'] for s in data.get('scores', [])}
        for c in concepts:
            mark = '🏆' if c['id'] == winner_id else '  '
            print(f'  {mark} [{c["id"]}] {c["theme"][:55]} — {scores.get(c["id"], "?")} баллов')
        return winner
    except (json.JSONDecodeError, StopIteration):
        return concepts[0]


# ── Stage 3: Generate full script for winner ──────────────────────────────────

def _generate_full_script(character: dict, concept: dict, cta: str) -> tuple[str, list[dict]]:
    """Generate 20-scene script for the winning concept. Returns (title, scenes)."""
    prompt = f"""Ты — сценарист глубокого эмоционального контента для YouTube Shorts / TikTok.

ПЕРСОНАЖ: {character['name']}
ХАРАКТЕР: {character['voice']}
ПРЕДЫСТОРИЯ ПЕРСОНАЖА: {character['backstory']}

ВЫБРАННЫЙ КОНЦЕПТ:
- Тема: {concept['theme']}
- Хук (сцена 1): {concept['hook']}
- Мораль (сцена 19): {concept['moral']}
- Эмоциональный угол: {concept.get('emotional_angle', '')}

ПРИЗЫВ К ДЕЙСТВИЮ (сцена 20): {cta}

ЗАДАЧА: Напиши историю из РОВНО 20 сцен (~2 минуты видео). Захвати зрителя с первой секунды и не отпускай до конца.

СТРУКТУРА (строго):
- Сцена 1 (ХУК): используй хук из концепта дословно
- Сцены 2-3 (ЗНАКОМСТВО): кто я, моя жизнь до событий
- Сцены 4-6 (ПРЕДЫСТОРИЯ): как всё началось, что было поставлено на карту
- Сцены 7-9 (НАРАСТАНИЕ): тревожные знаки, что-то пошло не так
- Сцены 10-12 (КРИЗИС): самое тяжёлое — удар, предательство, самое дно
- Сцены 13-15 (ПОВОРОТ): что изменило всё, первый шаг вперёд
- Сцены 16-18 (РАЗВЯЗКА): чем закончилось, что изменилось во мне
- Сцена 19 (МОРАЛЬ): главный урок из концепта
- Сцена 20 (CTA): используй точный текст CTA — персонаж просит подписаться

ПРАВИЛА:
- Первое лицо, разговорный язык
- 25-40 слов на сцену (~6 секунд)
- Сцены 10-12: максимальная боль и эмоция
- Сцена 20: ВСЕГДА заканчивается просьбой подписаться на канал
- Без мата, оскорблений, дискриминации

ВЕРНИ ТОЛЬКО JSON:
{{
  "title": "цепляющий заголовок до 8 слов",
  "scenes": [
    {{"index": 0, "text": "...", "duration": 6}},
    {{"index": 1, "text": "...", "duration": 6}},
    {{"index": 2, "text": "...", "duration": 6}},
    {{"index": 3, "text": "...", "duration": 6}},
    {{"index": 4, "text": "...", "duration": 6}},
    {{"index": 5, "text": "...", "duration": 6}},
    {{"index": 6, "text": "...", "duration": 6}},
    {{"index": 7, "text": "...", "duration": 6}},
    {{"index": 8, "text": "...", "duration": 6}},
    {{"index": 9, "text": "...", "duration": 7}},
    {{"index": 10, "text": "...", "duration": 7}},
    {{"index": 11, "text": "...", "duration": 7}},
    {{"index": 12, "text": "...", "duration": 6}},
    {{"index": 13, "text": "...", "duration": 6}},
    {{"index": 14, "text": "...", "duration": 6}},
    {{"index": 15, "text": "...", "duration": 6}},
    {{"index": 16, "text": "...", "duration": 6}},
    {{"index": 17, "text": "...", "duration": 6}},
    {{"index": 18, "text": "...", "duration": 7}},
    {{"index": 19, "text": "...", "duration": 7}}
  ]
}}"""

    response = client.chat.completions.create(
        model='gpt-4o-mini',
        max_tokens=4000,
        temperature=0.8,
        messages=[{'role': 'user', 'content': prompt}],
    )
    raw = response.choices[0].message.content if response.choices else ''
    match = re.search(r'\{[\s\S]*\}', raw)
    if not match:
        return concept['theme'], []
    try:
        data = json.loads(match.group())
        return data.get('title', concept['theme']), data.get('scenes', [])
    except json.JSONDecodeError:
        return concept['theme'], []


# ── Main generator ────────────────────────────────────────────────────────────

def generate_story_node(state: dict) -> dict:
    """
    LangGraph node: 3-stage script generation.
    Stage 1: Generate 5 concepts → Stage 2: Pick best → Stage 3: Full 20-scene script.
    """
    character = random.choice(CHARACTERS)
    cta = random.choice(CTA_VARIANTS)

    print(f'[ScriptWriter] {character["emoji"]} {character["name"]}')

    # ── Stage 1: 5 concepts ───────────────────────────────────────────────────
    print('[ScriptWriter] 💡 Этап 1/3: Генерирую 5 концептов...')
    concepts = _generate_concepts(character)
    if not concepts:
        # Fallback to random theme if concept generation fails
        theme_data = random.choice(THEMES)
        concepts = [{'id': 1, 'theme': theme_data['theme'], 'hook': theme_data['hook'],
                     'moral': theme_data['moral'], 'emotional_angle': 'драма', 'viral_reason': ''}]

    print(f'[ScriptWriter] 📋 Получено концептов: {len(concepts)}')
    for c in concepts:
        print(f'  [{c["id"]}] {c["theme"][:65]}')

    # ── Stage 2: Score & pick best ────────────────────────────────────────────
    print('[ScriptWriter] ⚖️  Этап 2/3: Выбираю лучший концепт...')
    best = _pick_best_concept(concepts, character) if len(concepts) > 1 else concepts[0]

    theme = best['theme']
    print(f'[ScriptWriter] ✅ Выбрана тема: "{theme}"')

    # ── Stage 3: Full script ──────────────────────────────────────────────────
    print('[ScriptWriter] ✍️  Этап 3/3: Пишу полный сценарий...')
    title, scenes = _generate_full_script(character, best, cta)

    if not scenes:
        return {**state, 'scenes': [], 'error': 'Full script generation failed'}

    total_sec = sum(s.get('duration', 6) for s in scenes)

    for s in scenes:
        s['image_prompt'] = _scene_image_prompt(character, s['text'], s['index'], len(scenes))
        s['pexels_query'] = _scene_pexels_query(character, s['index'], len(scenes))
        s['character'] = character['name']

    print(f'[ScriptWriter] 🎬 "{title}" — {len(scenes)} сцен, ~{total_sec}с ({total_sec//60}м{total_sec%60}с)')
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
