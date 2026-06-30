"""
Portrait image generator for each scene.

Fallback chain:
  1. DALL-E 3 (1024x1792 portrait)
  2. DALL-E 2 (1024x1024, resized)
  3. Pexels Photos API (keyword search, portrait orientation)
  4. PIL gradient slide (last resort)

Images are saved as 1080x1920 JPEG.
"""
import json
import os
import re
import ssl
import urllib.parse
import urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from openai import OpenAI

OUTPUT_DIR = Path(os.getenv('VIDEO_OUTPUT_DIR', '/tmp/content-automation'))
W, H = 1080, 1920

ACCENT_COLORS = [
    (255, 230, 0),
    (0, 230, 120),
    (100, 180, 255),
    (255, 80, 120),
    (200, 120, 255),
]

# Words to ignore when building Pexels search queries
_PEXELS_SKIP = {
    'a', 'an', 'the', 'in', 'on', 'at', 'with', 'and', 'of', 'for', 'by',
    'is', 'its', 'it', 'or', 'as', 'to', 'into',
    # Render / format descriptors
    'vertical', '9:16', 'format', 'no', 'text', 'render', '3d',
    'photorealistic', 'cinematic', 'lighting', 'shot',
    'establishing', 'wide', 'angle', 'action', 'intense',
    'expression', 'directly', 'camera', 'breaking', 'fourth', 'wall',
    'friendly', 'tense', 'face', 'emotional', 'calm', 'looking',
    'portrait', 'composition', 'epic', 'close-up',
    # Fruit/vegetable character words — Pexels won't have these
    'banana', 'strawberry', 'avocado', 'tomato', 'pineapple', 'cucumber',
    'character', 'headed', 'anthropomorphic',
}


def _ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ca = '/root/.ccr/ca-bundle.crt'
    if os.path.exists(ca):
        ctx.load_verify_locations(ca)
    return ctx


def _find_font(size: int) -> ImageFont.ImageFont:
    for p in [
        '/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    ]:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _make_gradient_slide(scene_idx: int, accent: tuple) -> Image.Image:
    """Vibrant purple→accent gradient — final fallback when all APIs fail."""
    top = (40, 0, 80)
    bot = (max(accent[0], 80), max(accent[1], 0), max(accent[2], 80))
    img = Image.new('RGB', (W, H), top)
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        r = int(top[0] + t * (bot[0] - top[0]))
        g = int(top[1] + t * (bot[1] - top[1]))
        b = int(top[2] + t * (bot[2] - top[2]))
        d.line([(0, y), (W, y)], fill=(r, g, b))
    return img


def _download_image(url: str, out_path: Path) -> None:
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'},
    )
    with urllib.request.urlopen(req, context=_ssl_ctx(), timeout=60) as r:
        data = r.read()
    out_path.write_bytes(data)


def _pexels_search_query(image_prompt: str) -> str:
    """Build a concise Pexels search query from the DALL-E scene prompt."""
    # Clean up and tokenize
    text = re.sub(r'[,.\-\/]', ' ', image_prompt.lower())
    words = text.split()
    # Keep meaningful English words not in the skip list
    kept = [w for w in words if w not in _PEXELS_SKIP and len(w) > 2 and w.isalpha()]
    # Take first 4 relevant words
    query = ' '.join(kept[:4])
    return query or 'dramatic portrait'


def _fetch_pexels_photo(query: str, out_path: Path, api_key: str) -> bool:
    """Download a portrait photo from Pexels Photos API. Returns True on success."""
    params = urllib.parse.urlencode({
        'query': query,
        'orientation': 'portrait',
        'size': 'large',
        'per_page': 5,
    })
    req = urllib.request.Request(
        f'https://api.pexels.com/v1/search?{params}',
        headers={
            'Authorization': api_key,
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
        },
    )
    try:
        with urllib.request.urlopen(req, context=_ssl_ctx(), timeout=20) as r:
            data = json.loads(r.read().decode())
        photos = data.get('photos', [])
        if not photos:
            print(f'[ImageGen] Pexels: no photos for "{query}"')
            return False
        src = photos[0].get('src', {})
        photo_url = src.get('large2x') or src.get('large') or src.get('original')
        if not photo_url:
            return False
        _download_image(photo_url, out_path)
        return True
    except Exception as e:
        print(f'[ImageGen] Pexels Photos error: {type(e).__name__}: {e}')
        return False


def _dalle_generate(oai: OpenAI, prompt: str) -> str | None:
    """Try DALL-E 3 then DALL-E 2. Returns image URL or None."""
    try:
        resp = oai.images.generate(
            model='dall-e-3',
            prompt=prompt,
            size='1024x1792',
            quality='standard',
            n=1,
        )
        return resp.data[0].url or None
    except Exception as e3:
        print(f'[ImageGen] DALL-E 3 failed ({type(e3).__name__}): {str(e3)[:100]}')

    try:
        resp = oai.images.generate(
            model='dall-e-2',
            prompt=prompt[:999],
            size='1024x1024',
            n=1,
        )
        return resp.data[0].url or None
    except Exception as e2:
        print(f'[ImageGen] DALL-E 2 failed ({type(e2).__name__}): {str(e2)[:100]}')
        return None


def generate_images_node(state: dict) -> dict:
    """
    LangGraph node: generate one portrait image per scene.

    Priority per scene:
      1. DALL-E 3 (requires OPENAI_API_KEY with image access)
      2. DALL-E 2 (fallback if DALL-E 3 unavailable)
      3. Pexels Photos (requires PEXELS_API_KEY)
      4. PIL gradient slide (always works)
    """
    scenes: list[dict] = state.get('scenes', [])
    content_id: str = state.get('content_id', 'default')
    character: dict = state.get('character', {})
    openai_key = os.environ.get('OPENAI_API_KEY', '')
    pexels_key = os.environ.get('PEXELS_API_KEY', '')

    images_dir = OUTPUT_DIR / content_id / 'images'
    images_dir.mkdir(parents=True, exist_ok=True)

    accent = ACCENT_COLORS[hash(content_id) % len(ACCENT_COLORS)]
    oai = OpenAI(api_key=openai_key) if openai_key else None

    updated_scenes = []

    for i, scene in enumerate(scenes):
        out_path = images_dir / f'scene_{i:02d}.jpg'

        # Use cached image if it looks real (>10 KB)
        if out_path.exists() and out_path.stat().st_size > 10_000:
            print(f'[ImageGen] Scene {i+1}: ♻️  cached')
            updated_scenes.append({**scene, 'image_path': str(out_path)})
            continue

        image_prompt: str = scene.get('image_prompt', '')
        if not image_prompt:
            char_base = character.get('image_base', 'a cartoon fruit character')
            image_prompt = f'{char_base}, scene {i+1}, photorealistic 3D render, cinematic, vertical 9:16'

        if '9:16' not in image_prompt and 'vertical' not in image_prompt:
            image_prompt += ', vertical composition, 9:16 portrait'

        saved = False

        # ── 1. DALL-E ─────────────────────────────────────────────────────────
        if oai:
            print(f'[ImageGen] Scene {i+1}: DALL-E generating...')
            url = _dalle_generate(oai, image_prompt[:3900])
            if url:
                try:
                    raw_path = images_dir / f'scene_{i:02d}_raw.png'
                    _download_image(url, raw_path)
                    img = Image.open(str(raw_path)).convert('RGB').resize((W, H), Image.LANCZOS)
                    img.save(str(out_path), 'JPEG', quality=92)
                    raw_path.unlink(missing_ok=True)
                    print(f'[ImageGen] Scene {i+1}: ✅ DALL-E → {out_path.name}')
                    saved = True
                except Exception as e:
                    print(f'[ImageGen] Scene {i+1}: DALL-E download/save error: {e}')
        else:
            print(f'[ImageGen] Scene {i+1}: ⚠️  no OPENAI_API_KEY — skipping DALL-E')

        # ── 2. Pexels Photos ──────────────────────────────────────────────────
        if not saved and pexels_key:
            query = _pexels_search_query(image_prompt)
            print(f'[ImageGen] Scene {i+1}: 📷 Pexels Photos "{query}"')
            raw_path = images_dir / f'scene_{i:02d}_pexels.jpg'
            if _fetch_pexels_photo(query, raw_path, pexels_key):
                try:
                    img = Image.open(str(raw_path)).convert('RGB').resize((W, H), Image.LANCZOS)
                    img.save(str(out_path), 'JPEG', quality=92)
                    raw_path.unlink(missing_ok=True)
                    print(f'[ImageGen] Scene {i+1}: ✅ Pexels photo → {out_path.name}')
                    saved = True
                except Exception as e:
                    print(f'[ImageGen] Scene {i+1}: Pexels photo error: {e}')
        elif not saved:
            print(f'[ImageGen] Scene {i+1}: ⚠️  no PEXELS_API_KEY')

        # ── 3. Gradient slide (last resort) ───────────────────────────────────
        if not saved:
            print(f'[ImageGen] Scene {i+1}: 🖼 gradient slide (no APIs available)')
            img = _make_gradient_slide(i, accent)
            img.save(str(out_path), 'JPEG', quality=90)

        updated_scenes.append({**scene, 'image_path': str(out_path)})

    return {**state, 'scenes': updated_scenes}
