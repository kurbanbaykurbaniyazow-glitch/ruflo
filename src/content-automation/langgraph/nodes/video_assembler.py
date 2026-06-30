"""
Video assembler — professional faceless video style (2026).

Pipeline:
1. Real stock video clips from Pexels (via video_fetcher.py)
2. Word-by-word animated captions (CapCut style) via FFmpeg drawtext
3. Subtle dark overlay for text readability
4. Top progress bar + brand watermark
5. Voice narration + lo-fi background music
6. Fallback to gradient slides if no clips available
"""
import os
import re
import subprocess
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUTPUT_DIR = Path(os.getenv('VIDEO_OUTPUT_DIR', '/tmp/content-automation'))
BRAND_HANDLE = os.getenv('BRAND_HANDLE', '@AIInsiderDaily')
W, H = 1080, 1920
SCENE_DURATION = 3

ACCENT_COLORS = [
    (255, 230, 0),
    (0, 230, 120),
    (100, 180, 255),
    (255, 80, 120),
    (200, 120, 255),
]
SCENE_EMOJIS = ['🤯', '😱', '💡', '📊', '🔥', '👆']


def _get_ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return 'ffmpeg'


def _find_font(size: int, bold: bool = True) -> str:
    """Return path to best available bold font."""
    candidates = [
        '/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf',
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return ''


def _ffmpeg_escape(text: str) -> str:
    """Escape text for FFmpeg drawtext filter."""
    return (text
            .replace('\\', '\\\\')
            .replace(':', '\\:')
            .replace("'", "\\'")
            .replace('%', '\\%')
            .replace('[', '\\[')
            .replace(']', '\\]'))


def _build_caption_filter(text: str, duration: float, accent_rgb: tuple,
                           font_path: str, font_size: int = 80) -> str:
    """
    Build FFmpeg drawtext filter for word-by-word caption animation.
    Each word appears for (duration / n_words) seconds.
    Style: white bold text with thick black stroke — TikTok/CapCut style.
    """
    words = text.split()
    if not words:
        return ''

    n = len(words)
    time_per_word = duration / n
    r, g, b = accent_rgb

    filters = []
    font_arg = f":fontfile='{font_path}'" if font_path else ''

    for i, word in enumerate(words):
        t_start = i * time_per_word
        t_end = (i + 1) * time_per_word + 0.05   # slight overlap
        escaped = _ffmpeg_escape(word.upper())
        enable = f"between(t,{t_start:.3f},{t_end:.3f})"

        # Black stroke (4 directions — lighter on CPU)
        for dx, dy in [(-4,0),(4,0),(0,-4),(0,4)]:
            filters.append(
                f"drawtext=text='{escaped}'{font_arg}"
                f":fontsize={font_size}:fontcolor=black"
                f":x=(w-text_w)/2+{dx}:y=h*0.72+{dy}"
                f":enable='{enable}'"
            )
        # White fill
        filters.append(
            f"drawtext=text='{escaped}'{font_arg}"
            f":fontsize={font_size}:fontcolor=white"
            f":x=(w-text_w)/2:y=h*0.72"
            f":enable='{enable}'"
        )

    return ','.join(filters)


def _build_progress_bar_filter(scene_idx: int, total: int, accent_rgb: tuple,
                                duration: float) -> str:
    """Top progress bar filter (animated fill)."""
    r, g, b = accent_rgb
    pct = (scene_idx + 1) / total
    bar_w = int((W - 80) * pct)
    return (
        f"drawbox=x=40:y=24:w={W-80}:h=7:color={r:02x}{g:02x}{b:02x}@0.25:t=fill,"
        f"drawbox=x=40:y=24:w={bar_w}:h=7:color={r:02x}{g:02x}{b:02x}@1:t=fill"
    )


def _build_brand_filter(font_path: str, accent_rgb: tuple) -> str:
    r, g, b = accent_rgb
    escaped = _ffmpeg_escape(BRAND_HANDLE)
    font_arg = f":fontfile='{font_path}'" if font_path else ''
    return (
        f"drawtext=text='{escaped}'{font_arg}"
        f":fontsize=34:fontcolor={r:02x}{g:02x}{b:02x}@0.7"
        f":x=44:y=42"
    )


# ─── Fallback slide renderer (PIL) ───────────────────────────────────────────

def _find_pil_font(size: int) -> ImageFont.ImageFont:
    for p in [
        '/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    ]:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except: pass
    return ImageFont.load_default()


def _draw_stroked(draw, pos, text, font, fill, stroke=8):
    x, y = pos
    for dx in range(-stroke, stroke+1, 2):
        for dy in range(-stroke, stroke+1, 2):
            if dx or dy:
                draw.text((x+dx, y+dy), text, font=font, fill=(0,0,0))
    draw.text((x, y), text, font=font, fill=fill)


def _make_fallback_slide(text: str, scene_idx: int, total: int,
                          accent: tuple) -> Image.Image:
    """Gradient slide fallback when no Pexels clip available."""
    bg = (6, 6, 10)
    img = Image.new('RGB', (W, H), bg)
    d = ImageDraw.Draw(img)

    # gradient
    for y in range(H):
        t = y / H
        r = int(bg[0] + t * (accent[0]//20))
        g = int(bg[1] + t * (accent[1]//20))
        b = int(bg[2] + t * (accent[2]//20))
        d.line([(0, y), (W, y)], fill=(r, g, b))

    # Progress bar
    bw = W - 80; bx = 40; by = 24
    d.rounded_rectangle([(bx,by),(bx+bw,by+7)], radius=4, fill=(*accent,40))
    fw = max(int(bw*(scene_idx+1)/total), 7)
    d.rounded_rectangle([(bx,by),(bx+fw,by+7)], radius=4, fill=accent)

    # Brand
    bf = _find_pil_font(32)
    d.text((44, 42), BRAND_HANDLE, fill=(*accent, 130), font=bf)

    # Emoji
    emoji = SCENE_EMOJIS[scene_idx % len(SCENE_EMOJIS)]
    try:
        ef = ImageFont.truetype('/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf', 200)
        dummy = Image.new('RGB',(1,1)); dd = ImageDraw.Draw(dummy)
        ew = dd.textlength(emoji, font=ef)
        d.text(((W-ew)//2, H//2 - 440), emoji, font=ef, embedded_color=True)
    except: pass

    # Headline
    words = text.split()
    headline = ' '.join(words[:7]).upper()
    fs = 150 if len(headline) < 20 else 110 if len(headline) < 35 else 90
    hf = _find_pil_font(fs)
    lines = []
    cur = ''
    dummy2 = Image.new('RGB',(1,1)); dd2 = ImageDraw.Draw(dummy2)
    for w in headline.split():
        t2 = (cur+' '+w).strip()
        if dd2.textlength(t2, font=hf) <= W-80: cur = t2
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    lh = int(fs*1.15)
    sy = H//2 - len(lines)*lh//2 + 80
    for i, line in enumerate(lines):
        lw = dd2.textlength(line, font=hf)
        _draw_stroked(d, ((W-lw)//2, sy+i*lh), line, hf, (255,255,255), stroke=10)

    return img


# ─── Main assembler ───────────────────────────────────────────────────────────

def assemble_video_node(state: dict) -> dict:
    """LangGraph node: assemble professional vertical video."""
    scenes: list[dict] = state.get('scenes', [])
    audio_path: str | None = state.get('audio_path')
    music_path: str | None = state.get('music_path')
    content_id: str = state.get('content_id', 'default')
    title: str = state.get('title', '')

    if not scenes:
        return {**state, 'error': 'No scenes to assemble'}

    video_dir = OUTPUT_DIR / content_id
    video_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = video_dir / 'frames'
    frames_dir.mkdir(exist_ok=True)

    accent = ACCENT_COLORS[hash(content_id) % len(ACCENT_COLORS)]
    font_path = _find_font(80)
    ffmpeg = _get_ffmpeg()
    total = len(scenes)

    # Build per-scene processed clips
    scene_clips: list[tuple[str, float]] = []

    for i, scene in enumerate(scenes):
        text = scene.get('text', '').strip()
        duration = float(scene.get('duration', SCENE_DURATION))
        clip_path = scene.get('clip_path')  # from video_fetcher

        out_clip = str(video_dir / f'scene_{i:02d}.mp4')

        if clip_path and Path(clip_path).exists():
            # ── Real video clip path ──────────────────────────────────────
            # Build filter: dark overlay + captions + progress bar + brand
            overlay = 'drawbox=x=0:y=0:w=iw:h=ih:color=black@0.35:t=fill'
            captions = _build_caption_filter(text, duration, accent, font_path)
            progress = _build_progress_bar_filter(i, total, accent, duration)
            brand = _build_brand_filter(font_path, accent)

            filters = [overlay]
            if captions: filters.append(captions)
            filters.append(progress)
            filters.append(brand)
            vf = ','.join(filters)

            cmd = [
                ffmpeg, '-y', '-i', clip_path,
                '-vf', vf,
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
                '-pix_fmt', 'yuv420p', '-an', '-t', str(duration),
                out_clip,
            ]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode == 0:
                scene_clips.append((out_clip, duration))
                print(f'[Assembler] Scene {i+1}: ✅ video clip + captions')
                continue
            print(f'[Assembler] Scene {i+1}: ffmpeg error: {r.stderr[-500:]}')

            # Retry without captions (overlay too complex) — still use real clip
            cmd_nocap = [
                ffmpeg, '-y', '-i', clip_path,
                '-vf', f'{overlay},{progress},{brand}',
                '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23',
                '-pix_fmt', 'yuv420p', '-an', '-t', str(duration),
                out_clip,
            ]
            r2 = subprocess.run(cmd_nocap, capture_output=True, text=True)
            if r2.returncode == 0:
                scene_clips.append((out_clip, duration))
                print(f'[Assembler] Scene {i+1}: ✅ video clip (no captions)')
                continue
            print(f'[Assembler] Scene {i+1}: clip failed too: {r2.stderr[-200:]}')

        # ── PIL slide fallback with animated captions ────────────────────
        # Clean background slide (no text — text will be overlaid via FFmpeg)
        img = _make_fallback_slide('', i, total, accent)
        img_path = str(frames_dir / f'slide_{i:02d}.jpg')
        img.save(img_path, 'JPEG', quality=95)

        # Word-by-word captions overlaid on slide via FFmpeg drawtext (no zoompan — saves RAM)
        captions = _build_caption_filter(text, duration, accent, font_path, font_size=88)
        vf_slide = (
            f'loop=loop={int(duration*30)}:size=1:start=0,'
            'scale=1080:1920:force_original_aspect_ratio=disable,'
            'setsar=1'
        )
        if captions:
            vf_slide = vf_slide + ',' + captions

        cmd_slide = [
            ffmpeg, '-y', '-i', img_path,
            '-vf', vf_slide,
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
            '-pix_fmt', 'yuv420p', '-an', '-t', str(duration),
            out_clip,
        ]
        r2 = subprocess.run(cmd_slide, capture_output=True, text=True)
        if r2.returncode != 0:
            cmd_simple = [
                ffmpeg, '-y', '-loop', '1', '-i', img_path,
                '-c:v', 'libx264', '-t', str(duration), '-r', '30',
                '-pix_fmt', 'yuv420p', '-an', out_clip,
            ]
            subprocess.run(cmd_simple, capture_output=True)
        scene_clips.append((out_clip, duration))
        print(f'[Assembler] Scene {i+1}: 🖼 slide + animated captions')

    if not scene_clips:
        return {**state, 'error': 'No scene clips rendered'}

    # Concatenate all scenes
    concat_file = video_dir / 'concat.txt'
    with open(concat_file, 'w') as f:
        for path, _ in scene_clips:
            f.write(f"file '{path}'\n")

    total_sec = sum(d for _, d in scene_clips)
    raw_video = str(video_dir / 'slideshow_raw.mp4')
    final_video = str(video_dir / 'final.mp4')

    cmd_cat = [
        ffmpeg, '-y', '-f', 'concat', '-safe', '0', '-i', str(concat_file),
        '-c', 'copy', raw_video,
    ]
    r = subprocess.run(cmd_cat, capture_output=True, text=True)
    if r.returncode != 0:
        return {**state, 'error': f'Concat error: {r.stderr[-300:]}'}

    # Mix audio: voice + background music
    has_narration = audio_path and Path(audio_path).exists()
    has_music = music_path and Path(music_path).exists()

    # -movflags +faststart moves moov atom to start of file — required for browser/phone playback
    faststart = ['-movflags', '+faststart']

    if has_narration and has_music:
        mix_f = (
            '[1:a]aresample=44100[narr];'
            '[2:a]aresample=44100,volume=0.35[music];'
            '[narr][music]amix=inputs=2:duration=first:normalize=0[aout]'
        )
        cmd_mix = [
            ffmpeg, '-y',
            '-i', raw_video, '-i', audio_path, '-i', music_path,
            '-filter_complex', mix_f,
            '-map', '0:v', '-map', '[aout]',
            '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', '44100', '-shortest',
            *faststart, final_video,
        ]
    elif has_narration:
        cmd_mix = [
            ffmpeg, '-y', '-i', raw_video, '-i', audio_path,
            '-filter_complex', '[1:a]aresample=44100[aout]',
            '-map', '0:v', '-map', '[aout]',
            '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', '44100', '-shortest',
            *faststart, final_video,
        ]
    elif has_music:
        cmd_mix = [
            ffmpeg, '-y', '-i', raw_video, '-i', music_path,
            '-filter_complex', '[1:a]aresample=44100,volume=0.4[aout]',
            '-map', '0:v', '-map', '[aout]',
            '-c:v', 'copy', '-c:a', 'aac', '-b:a', '128k', '-ar', '44100', '-shortest',
            *faststart, final_video,
        ]
    else:
        # Re-encode without audio but with faststart so browser can play it
        cmd_mix = [
            ffmpeg, '-y', '-i', raw_video,
            '-c:v', 'copy', *faststart, final_video,
        ]

    if cmd_mix:
        r3 = subprocess.run(cmd_mix, capture_output=True, text=True)
        if r3.returncode != 0:
            print(f'[Assembler] audio mix error: {r3.stderr[-300:]}')
            import shutil; shutil.copy(raw_video, final_video)

    # Thumbnail
    thumbnail_path = str(video_dir / 'thumbnail.jpg')
    subprocess.run([
        ffmpeg, '-y', '-i', final_video,
        '-ss', '00:00:01', '-vframes', '1',
        '-vf', 'scale=1280:720', thumbnail_path,
    ], capture_output=True)

    print(f'[Assembler] ✅ {final_video}  ({total_sec:.0f}s, {len(scene_clips)} scenes)')
    return {
        **state,
        'video_path': final_video,
        'thumbnail_path': thumbnail_path if Path(thumbnail_path).exists() else None,
        'error': None,
    }
