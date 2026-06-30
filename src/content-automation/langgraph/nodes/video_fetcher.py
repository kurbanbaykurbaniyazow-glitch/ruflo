"""
Pexels video fetcher — downloads portrait stock video clips for each scene.

Searches by English keywords extracted from scene image_prompt,
downloads portrait HD clips, trims to exact scene duration.
"""
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
import ssl
from pathlib import Path

OUTPUT_DIR = Path(os.getenv('VIDEO_OUTPUT_DIR', '/tmp/content-automation'))
PEXELS_API = 'https://api.pexels.com/videos/search'

# Words to skip when building search queries from DALL-E style prompts
_SKIP = {
    'a', 'an', 'the', 'in', 'on', 'at', 'with', 'and', 'of', 'for', 'by',
    'is', 'its', 'it', 'or', 'as', 'to', 'into', 'wearing', 'sitting',
    'vertical', '9:16', 'format', 'no', 'text', 'render', '3d',
    'photorealistic', 'cinematic', 'lighting', 'shot',
    'establishing', 'wide', 'angle', 'action', 'intense',
    'expression', 'directly', 'camera', 'breaking', 'fourth', 'wall',
    'friendly', 'tense', 'face', 'emotional', 'calm', 'looking',
    'portrait', 'composition', 'epic', 'close-up',
    # Fruit/veggie character words — Pexels won't have these
    'banana', 'strawberry', 'avocado', 'tomato', 'pineapple', 'cucumber',
    'character', 'headed', 'anthropomorphic', 'dramatic', 'red', 'cartoon',
}


def _ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ca = '/root/.ccr/ca-bundle.crt'
    if os.path.exists(ca):
        ctx.load_verify_locations(ca)
    return ctx


def _get_ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return 'ffmpeg'


def _build_query(scene: dict) -> str:
    """Extract English search terms from scene's image_prompt (avoids Russian text)."""
    image_prompt = scene.get('image_prompt', '')
    if image_prompt:
        clean = re.sub(r'[,.\-\/]', ' ', image_prompt.lower())
        words = [w for w in clean.split() if w not in _SKIP and len(w) > 2 and w.isalpha()]
        if words:
            return ' '.join(words[:4])
    # Fallback: generic cinematic queries per scene position
    idx = scene.get('index', 0)
    fallbacks = ['cinematic dramatic', 'city night', 'luxury office', 'dramatic confrontation', 'emotional moment', 'subscribe notification']
    return fallbacks[idx % len(fallbacks)]


def _search_pexels(query: str, api_key: str) -> dict | None:
    """Search Pexels Videos API. Returns best portrait clip file dict or None."""
    params = urllib.parse.urlencode({
        'query': query,
        'per_page': 10,
        'orientation': 'portrait',
        'size': 'medium',
    })
    req = urllib.request.Request(
        f'{PEXELS_API}?{params}',
        headers={
            'Authorization': api_key,
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
        },
    )
    try:
        with urllib.request.urlopen(req, context=_ssl_ctx(), timeout=15) as r:
            data = json.loads(r.read())
    except Exception as e:
        print(f'[VideoFetcher] Pexels API error: {e}')
        return None

    videos = data.get('videos', [])
    if not videos:
        return None

    for v in videos:
        files = v.get('video_files', [])
        # Prefer portrait (height > width) HD/SD files
        portrait = [
            f for f in files
            if f.get('height', 0) > f.get('width', 0)
            and f.get('quality') in ('hd', 'sd')
        ]
        chosen = portrait[0] if portrait else (files[0] if files else None)
        if chosen:
            return {'video_id': v['id'], 'duration': v['duration'], 'file': chosen}

    return None


def _download(url: str, out: Path, api_key: str) -> None:
    req = urllib.request.Request(
        url,
        headers={
            'Authorization': api_key,
            'User-Agent': 'Mozilla/5.0',
        },
    )
    with urllib.request.urlopen(req, context=_ssl_ctx(), timeout=120) as r, open(out, 'wb') as f:
        while chunk := r.read(65536):
            f.write(chunk)


def _prepare_clip(raw: Path, out: Path, duration: int, scene_idx: int, ffmpeg: str) -> None:
    """Trim, scale and crop clip to 1080x1920 portrait, exact duration."""
    vf = (
        'scale=iw*max(1080/iw\\,1920/ih):ih*max(1080/iw\\,1920/ih),'
        'crop=1080:1920,'
        'setsar=1'
    )
    cmd = [
        ffmpeg, '-y',
        '-ss', str(scene_idx % 3),   # start a few seconds in for variety
        '-i', str(raw),
        '-t', str(duration),
        '-vf', vf,
        '-r', '30',
        '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23',
        '-an', '-pix_fmt', 'yuv420p',
        str(out),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f'clip prep failed: {r.stderr[-200:]}')


def fetch_videos_node(state: dict) -> dict:
    """
    LangGraph node: download one Pexels portrait video clip per scene.
    Sets clip_path on each scene dict. Skips scenes where clip already cached.
    """
    scenes: list[dict] = state.get('scenes', [])
    content_id: str = state.get('content_id', 'default')
    api_key: str = os.environ.get('PEXELS_API_KEY', '')

    if not api_key:
        print('[VideoFetcher] ⚠️  PEXELS_API_KEY not set — skipping video fetch')
        return {**state, 'scenes': [{**s, 'clip_path': None} for s in scenes]}

    clips_dir = OUTPUT_DIR / content_id / 'clips'
    clips_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg = _get_ffmpeg()

    updated_scenes = []
    for i, scene in enumerate(scenes):
        duration = int(scene.get('duration', 3))
        prepared = clips_dir / f'clip_{i:02d}.mp4'

        # Use cached clip
        if prepared.exists() and prepared.stat().st_size > 50_000:
            print(f'[VideoFetcher] Scene {i+1}: ♻️  cached')
            updated_scenes.append({**scene, 'clip_path': str(prepared)})
            continue

        query = _build_query(scene)
        print(f'[VideoFetcher] Scene {i+1}: 🔍 "{query}"')

        clip_path = None
        try:
            result = _search_pexels(query, api_key)
            if result:
                raw = clips_dir / f'raw_{i:02d}.mp4'
                print(f'[VideoFetcher] Scene {i+1}: ⬇️  downloading video {result["video_id"]}...')
                _download(result['file']['link'], raw, api_key)
                _prepare_clip(raw, prepared, duration, i, ffmpeg)
                raw.unlink(missing_ok=True)
                clip_path = str(prepared)
                print(f'[VideoFetcher] Scene {i+1}: ✅ {prepared.name}')
            else:
                print(f'[VideoFetcher] Scene {i+1}: ⚠️  no results for "{query}"')
        except Exception as e:
            print(f'[VideoFetcher] Scene {i+1}: ❌ {e}')

        updated_scenes.append({**scene, 'clip_path': clip_path})

    return {**state, 'scenes': updated_scenes}
