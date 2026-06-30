"""
Pexels video fetcher — downloads stock video clips for each scene.
Searches by scene keywords, downloads portrait HD clips, trims to scene duration.
"""
import json
import os
import subprocess
import urllib.request
import urllib.parse
import ssl
from pathlib import Path

OUTPUT_DIR = Path(os.getenv('VIDEO_OUTPUT_DIR', '/tmp/content-automation'))
PEXELS_API_KEY = os.getenv('PEXELS_API_KEY', '')
PEXELS_API = 'https://api.pexels.com/videos/search'


def _get_ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return 'ffmpeg'


def _ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ca = '/root/.ccr/ca-bundle.crt'
    if os.path.exists(ca):
        ctx.load_verify_locations(ca)
    return ctx


def search_pexels_video(query: str, duration_min: int = 5, duration_max: int = 15) -> dict | None:
    """
    Search Pexels for a portrait HD video matching the query.
    Returns the best matching video file dict or None.
    """
    if not PEXELS_API_KEY:
        raise RuntimeError('PEXELS_API_KEY not set in .env')

    params = urllib.parse.urlencode({
        'query': query,
        'per_page': 10,
        'orientation': 'portrait',
        'size': 'medium',
    })
    url = f'{PEXELS_API}?{params}'
    req = urllib.request.Request(url, headers={
        'Authorization': PEXELS_API_KEY,
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
    })

    with urllib.request.urlopen(req, context=_ssl_ctx(), timeout=15) as r:
        data = json.loads(r.read())

    videos = data.get('videos', [])
    if not videos:
        return None

    # Filter by duration and prefer portrait clips
    candidates = [
        v for v in videos
        if duration_min <= v['duration'] <= duration_max
    ]
    if not candidates:
        candidates = videos  # fallback: use any

    # Pick first with HD portrait file
    for v in candidates:
        files = v.get('video_files', [])
        # Prefer portrait (height > width) HD files
        portrait = [f for f in files if f.get('height', 0) > f.get('width', 0) and f.get('quality') in ('hd', 'sd')]
        if portrait:
            return {'video_id': v['id'], 'duration': v['duration'], 'file': portrait[0]}
        # Fallback: any file
        if files:
            return {'video_id': v['id'], 'duration': v['duration'], 'file': files[0]}

    return None


def download_clip(url: str, output_path: Path) -> Path:
    """Download video file from Pexels CDN."""
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0',
        'Authorization': PEXELS_API_KEY,
    })
    with urllib.request.urlopen(req, context=_ssl_ctx(), timeout=60) as r, open(output_path, 'wb') as f:
        while chunk := r.read(65536):
            f.write(chunk)
    return output_path


def prepare_clip(raw_path: Path, output_path: Path, duration: int, scene_idx: int) -> Path:
    """
    Trim clip to exact duration + crop/scale to 1080x1920 (TikTok portrait).
    Applies subtle Ken Burns effect.
    """
    ffmpeg = _get_ffmpeg()

    # Crop to portrait 9:16, scale to 1080x1920, trim — no zoompan (saves RAM)
    vf = (
        'scale=iw*max(1080/iw\\,1920/ih):ih*max(1080/iw\\,1920/ih),'
        'crop=1080:1920,'
        'setsar=1'
    )

    cmd = [
        ffmpeg, '-y',
        '-ss', str(scene_idx % 3),
        '-i', str(raw_path),
        '-t', str(duration),
        '-vf', vf,
        '-r', '30',
        '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23',
        '-an',
        '-pix_fmt', 'yuv420p',
        str(output_path),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f'ffmpeg clip prep failed: {r.stderr[-300:]}')
    return output_path


def fetch_videos_node(state: dict) -> dict:
    """
    LangGraph node: fetch one Pexels video clip per scene.
    Adds 'clip_path' to each scene dict.
    """
    scenes: list[dict] = state.get('scenes', [])
    content_id: str = state.get('content_id', 'default')
    title: str = state.get('title', '')

    clips_dir = OUTPUT_DIR / content_id / 'clips'
    clips_dir.mkdir(parents=True, exist_ok=True)

    updated_scenes = []
    for i, scene in enumerate(scenes):
        text = scene.get('text', '')
        duration = scene.get('duration', 3)

        # Build search query from scene text (first 4-5 keywords)
        words = [w for w in text.split() if len(w) > 3 and w.isalpha()][:5]
        query = ' '.join(words) if words else title

        clip_path = None
        try:
            print(f'[VideoFetcher] Scene {i+1}: searching "{query}"...')
            result = search_pexels_video(query, duration_min=duration, duration_max=30)

            if result:
                raw = clips_dir / f'raw_{i:02d}.mp4'
                prepared = clips_dir / f'clip_{i:02d}.mp4'

                print(f'[VideoFetcher]   Downloading {result["video_id"]}...')
                download_clip(result['file']['link'], raw)
                prepare_clip(raw, prepared, duration, i)
                raw.unlink(missing_ok=True)  # save space

                clip_path = str(prepared)
                print(f'[VideoFetcher]   ✅ {prepared.name}')
            else:
                print(f'[VideoFetcher]   ⚠️ No clip found for "{query}"')

        except Exception as e:
            print(f'[VideoFetcher]   ❌ Scene {i+1}: {e}')

        updated_scenes.append({**scene, 'clip_path': clip_path})

    return {**state, 'scenes': updated_scenes}
