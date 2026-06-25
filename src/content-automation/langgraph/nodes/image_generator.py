import os
import httpx
from pathlib import Path
from openai import OpenAI

client = OpenAI()
OUTPUT_DIR = Path(os.getenv('VIDEO_OUTPUT_DIR', '/tmp/content-automation'))


def generate_image_node(state: dict) -> dict:
    """LangGraph node: generate images for each scene using DALL-E 3."""
    scenes: list[dict] = state.get('scenes', [])
    content_id: str = state.get('content_id', 'default')

    if not scenes:
        return {**state, 'error': 'No scenes to generate images for'}

    images_dir = OUTPUT_DIR / content_id / 'images'
    images_dir.mkdir(parents=True, exist_ok=True)

    updated_scenes = []
    for scene in scenes:
        image_path = images_dir / f"scene_{scene['index']:02d}.png"

        if image_path.exists():
            # Reuse cached image
            updated_scenes.append({**scene, 'image_path': str(image_path)})
            continue

        try:
            response = client.images.generate(
                model='dall-e-3',
                prompt=f"{scene['image_prompt']}\nStyle: cinematic, 16:9 aspect ratio, high quality, professional",
                size='1792x1024',
                quality='standard',
                n=1,
            )

            image_url = response.data[0].url
            if not image_url:
                raise ValueError('No image URL returned from DALL-E')

            # Download image
            with httpx.Client() as http_client:
                img_response = http_client.get(image_url, timeout=30)
                img_response.raise_for_status()
                image_path.write_bytes(img_response.content)

            print(f'[ImageGen] Generated scene {scene["index"]}: {image_path.name}')
            updated_scenes.append({**scene, 'image_path': str(image_path)})

        except Exception as e:
            print(f'[ImageGen] Failed scene {scene["index"]}: {e}')
            # Use placeholder image
            placeholder = _create_placeholder(scene['text'], image_path)
            updated_scenes.append({**scene, 'image_path': str(placeholder)})

    return {**state, 'scenes': updated_scenes, 'error': None}


def _create_placeholder(text: str, output_path: Path) -> Path:
    """Create a simple text-on-dark-background placeholder image."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new('RGB', (1792, 1024), color=(20, 20, 20))
    draw = ImageDraw.Draw(img)

    # Try to load a font, fall back to default
    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 48)
    except OSError:
        font = ImageFont.load_default()

    # Word wrap text
    words = text.split()
    lines = []
    current_line = []
    for word in words:
        current_line.append(word)
        if len(' '.join(current_line)) > 50:
            lines.append(' '.join(current_line[:-1]))
            current_line = [word]
    if current_line:
        lines.append(' '.join(current_line))

    y = 1024 // 2 - len(lines) * 30
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        draw.text(((1792 - w) // 2, y), line, fill='white', font=font)
        y += 70

    img.save(str(output_path))
    return output_path
