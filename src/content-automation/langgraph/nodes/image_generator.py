"""
Portrait image generator for each scene.

Fallback chain:
  1. Replicate API — Flux Schnell (fast, cheap, great fruit characters)
  2. DALL-E 3 (1024x1792 portrait)
  3. DALL-E 2 (1024x1024, resized)
  4. PIL gradient slide (last resort)

Images are saved as 1080x1920 JPEG.
Requires one of: REPLICATE_API_KEY or OPENAI_API_KEY
"""
import json
import os
import re
import ssl
import time
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


def _replicate_flux(prompt: str, api_key: str, out_path: Path) -> bool:
    """
    Generate image via Replicate Flux Schnell (fast, cheap, excellent quality).
    Cost: ~$0.003 per image. Requires REPLICATE_API_KEY.
    """
    # Create prediction
    body = json.dumps({
        'version': 'black-forest-labs/flux-schnell',
        'input': {
            'prompt': prompt,
            'aspect_ratio': '9:16',
            'output_format': 'jpg',
            'output_quality': 90,
            'num_outputs': 1,
        },
    }).encode()
    req = urllib.request.Request(
        'https://api.replicate.com/v1/models/black-forest-labs/flux-schnell/predictions',
        data=body,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'Prefer': 'wait',  # wait up to 60s for result
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, context=_ssl_ctx(), timeout=90) as r:
            result = json.loads(r.read().decode())
    except Exception as e:
        print(f'[ImageGen] Replicate request failed: {e}')
        return False

    # If "prefer: wait" didn't resolve, poll
    prediction_id = result.get('id')
    output = result.get('output')
    status = result.get('status', '')

    max_polls = 20
    for _ in range(max_polls):
        if status in ('succeeded', 'failed', 'canceled'):
            break
        if not prediction_id:
            break
        time.sleep(3)
        poll_req = urllib.request.Request(
            f'https://api.replicate.com/v1/predictions/{prediction_id}',
            headers={'Authorization': f'Bearer {api_key}'},
        )
        try:
            with urllib.request.urlopen(poll_req, context=_ssl_ctx(), timeout=15) as r:
                result = json.loads(r.read().decode())
            status = result.get('status', '')
            output = result.get('output')
        except Exception:
            break

    if status != 'succeeded' or not output:
        print(f'[ImageGen] Replicate status: {status}, error: {result.get("error")}')
        return False

    image_url = output[0] if isinstance(output, list) else output
    try:
        _download_image(image_url, out_path)
        return True
    except Exception as e:
        print(f'[ImageGen] Replicate download failed: {e}')
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
      1. Replicate Flux Schnell (requires REPLICATE_API_KEY) — best for fruit characters
      2. DALL-E 3 (requires OPENAI_API_KEY with image access)
      3. DALL-E 2 (fallback)
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
        replicate_key = os.environ.get('REPLICATE_API_KEY', '')

        # ── 1. Replicate Flux Schnell — best for fruit/veggie characters ──────
        if replicate_key:
            print(f'[ImageGen] Scene {i+1}: 🍌 Replicate Flux Schnell generating...')
            raw_path = images_dir / f'scene_{i:02d}_flux.jpg'
            if _replicate_flux(image_prompt[:1500], replicate_key, raw_path):
                try:
                    img = Image.open(str(raw_path)).convert('RGB').resize((W, H), Image.LANCZOS)
                    img.save(str(out_path), 'JPEG', quality=92)
                    raw_path.unlink(missing_ok=True)
                    print(f'[ImageGen] Scene {i+1}: ✅ Replicate Flux → {out_path.name}')
                    saved = True
                except Exception as e:
                    print(f'[ImageGen] Scene {i+1}: Replicate save error: {e}')

        # ── 2. DALL-E 3 / 2 ──────────────────────────────────────────────────
        if not saved and oai:
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
        elif not saved:
            print(f'[ImageGen] Scene {i+1}: ⚠️  no REPLICATE_API_KEY or OPENAI_API_KEY')

        # ── 3. Pexels Photos ──────────────────────────────────────────────────
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
