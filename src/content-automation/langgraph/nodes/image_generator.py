"""
DALL-E 3 image generator — portrait 9:16 AI images for each scene.

Generates one image per scene using the character + story context.
Images are 1024x1792 (portrait TikTok/Shorts format).
Falls back to PIL gradient slide if DALL-E fails or key missing.
"""
import os
import ssl
import urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from openai import OpenAI

OUTPUT_DIR = Path(os.getenv('VIDEO_OUTPUT_DIR', '/tmp/content-automation'))
W, H = 1080, 1920


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
    """Gradient background slide as DALL-E fallback."""
    bg = (8, 8, 14)
    img = Image.new('RGB', (W, H), bg)
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        r = int(bg[0] + t * (accent[0] // 12))
        g = int(bg[1] + t * (accent[1] // 12))
        b = int(bg[2] + t * (accent[2] // 12))
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


ACCENT_COLORS = [
    (255, 230, 0),
    (0, 230, 120),
    (100, 180, 255),
    (255, 80, 120),
    (200, 120, 255),
]


def generate_images_node(state: dict) -> dict:
    """
    LangGraph node: generate one DALL-E 3 portrait image per scene.
    Adds 'image_path' to each scene dict.
    """
    scenes: list[dict] = state.get('scenes', [])
    content_id: str = state.get('content_id', 'default')
    character: dict = state.get('character', {})
    openai_key = os.environ.get('OPENAI_API_KEY', '')

    images_dir = OUTPUT_DIR / content_id / 'images'
    images_dir.mkdir(parents=True, exist_ok=True)

    accent = ACCENT_COLORS[hash(content_id) % len(ACCENT_COLORS)]
    updated_scenes = []

    for i, scene in enumerate(scenes):
        out_path = images_dir / f'scene_{i:02d}.jpg'

        # Use cached image if exists
        if out_path.exists() and out_path.stat().st_size > 10_000:
            print(f'[ImageGen] Scene {i+1}: ♻️  cached')
            updated_scenes.append({**scene, 'image_path': str(out_path)})
            continue

        if not openai_key:
            print(f'[ImageGen] Scene {i+1}: ⚠️  no OPENAI_API_KEY — using gradient slide')
            img = _make_gradient_slide(i, accent)
            img.save(str(out_path), 'JPEG', quality=90)
            updated_scenes.append({**scene, 'image_path': str(out_path)})
            continue

        try:
            oai = OpenAI(api_key=openai_key)
            prompt = scene.get('image_prompt', '')
            if not prompt:
                char_base = character.get('image_base', 'a cartoon fruit character')
                prompt = f'{char_base}, scene {i+1}, photorealistic 3D render, cinematic, vertical 9:16'

            # Ensure portrait format hint in prompt
            if '9:16' not in prompt and 'vertical' not in prompt:
                prompt += ', vertical composition, 9:16 portrait'

            # DALL-E 3 max prompt length is 4000 chars
            prompt = prompt[:3900]

            print(f'[ImageGen] Scene {i+1}: DALL-E generating...')
            response = oai.images.generate(
                model='dall-e-3',
                prompt=prompt,
                size='1024x1792',   # portrait 9:16
                quality='standard',
                n=1,
            )
            url = response.data[0].url
            if not url:
                raise ValueError('No URL returned')

            # Download and convert to JPEG at 1080x1920
            raw_path = images_dir / f'scene_{i:02d}_raw.png'
            _download_image(url, raw_path)

            # Resize to exact 1080x1920
            img = Image.open(str(raw_path)).convert('RGB')
            img = img.resize((W, H), Image.LANCZOS)
            img.save(str(out_path), 'JPEG', quality=92)
            raw_path.unlink(missing_ok=True)

            print(f'[ImageGen] Scene {i+1}: ✅ {out_path.name}')
            updated_scenes.append({**scene, 'image_path': str(out_path)})

        except Exception as e:
            print(f'[ImageGen] Scene {i+1}: ❌ DALL-E error: {type(e).__name__}: {e}')
            img = _make_gradient_slide(i, accent)
            img.save(str(out_path), 'JPEG', quality=90)
            updated_scenes.append({**scene, 'image_path': str(out_path)})

    return {**state, 'scenes': updated_scenes}
