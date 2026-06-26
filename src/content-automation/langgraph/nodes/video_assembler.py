"""
Viral 2026 TikTok/Shorts video assembler.
Design: giant bold text with black stroke, emoji anchors, clean gradient, top progress bar.
Target: 15-25s, hook in 1.3s, TikTok-native caption style.
"""
import os
import subprocess
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUTPUT_DIR = Path(os.getenv('VIDEO_OUTPUT_DIR', '/tmp/content-automation'))
BRAND_HANDLE = os.getenv('BRAND_HANDLE', '@AIInsiderDaily')
W, H = 1080, 1920
SCENE_DURATION = 3  # seconds per slide — 6 slides = 18s total

# Accent colors: one per theme, cycling per-video
ACCENT_COLORS = [
    (255, 230, 0),    # yellow — curiosity/money
    (0, 230, 120),    # green — health/growth
    (100, 180, 255),  # blue — tech/info
    (255, 80, 120),   # red-pink — shocking/drama
    (200, 120, 255),  # purple — mystery
]

# Scene emojis mapped by position (hook, problem, reveal, proof, insight, cta)
SCENE_EMOJIS = ['🤯', '😱', '💡', '📊', '🔥', '👆']


def _get_ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return 'ffmpeg'


def _find_bold_font(size: int) -> ImageFont.ImageFont:
    """Find largest available bold/condensed font."""
    candidates = [
        '/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf',
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _find_emoji_font(size: int) -> ImageFont.ImageFont:
    """Find emoji font."""
    candidates = [
        '/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf',
        '/usr/share/fonts/noto/NotoColorEmoji.ttf',
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return _find_bold_font(size)


def _vgrad(img: Image.Image, c1: tuple, c2: tuple) -> None:
    """Clean vertical gradient — no effects, just colors."""
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        r = int(c1[0] + t * (c2[0] - c1[0]))
        g = int(c1[1] + t * (c2[1] - c1[1]))
        b = int(c1[2] + t * (c2[2] - c1[2]))
        d.line([(0, y), (W, y)], fill=(r, g, b))


def _draw_stroked_text(draw: ImageDraw.ImageDraw, pos: tuple, text: str,
                        font: ImageFont.ImageFont, fill: tuple,
                        stroke_width: int = 8) -> None:
    """Draw text with thick black stroke — TikTok viral caption style."""
    x, y = pos
    stroke_color = (0, 0, 0)
    # 8-direction stroke
    for dx in range(-stroke_width, stroke_width + 1, 2):
        for dy in range(-stroke_width, stroke_width + 1, 2):
            if dx == 0 and dy == 0:
                continue
            draw.text((x + dx, y + dy), text, font=font, fill=stroke_color)
    draw.text((x, y), text, font=font, fill=fill)


def _wrap_tight(text: str, font: ImageFont.ImageFont, max_w: int) -> list[str]:
    """Wrap text to fit within max_w, respecting natural breaks."""
    words = text.split()
    lines = []
    cur = ''
    dummy = Image.new('RGB', (1, 1))
    d = ImageDraw.Draw(dummy)
    for word in words:
        test = (cur + ' ' + word).strip() if cur else word
        if d.textlength(test, font=font) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def make_viral_slide(
    scene_idx: int,
    total_scenes: int,
    headline: str,
    subtext: str,
    emoji: str,
    accent: tuple,
    is_hook: bool = False,
) -> Image.Image:
    """
    Render a single 2026-viral-style slide:
    - Clean dark gradient background
    - Top progress bar
    - Large emoji anchor
    - Giant stroked headline
    - Small caption subtext at bottom
    - Brand watermark
    """
    # Background: near-black gradient with faint accent tint
    bg_dark = (6, 6, 10)
    bg_hint = (
        min(6 + accent[0] // 20, 30),
        min(6 + accent[1] // 20, 30),
        min(6 + accent[2] // 20, 30),
    )
    img = Image.new('RGB', (W, H), bg_dark)
    _vgrad(img, bg_dark, bg_hint)

    d = ImageDraw.Draw(img)

    # ── TOP PROGRESS BAR ─────────────────────────────────────────────────────
    bar_h = 7
    bar_w = W - 80
    bx = 40
    by = 28
    # track
    d.rounded_rectangle([(bx, by), (bx + bar_w, by + bar_h)],
                         radius=4, fill=(*accent, 40))
    # fill
    fill_w = max(int(bar_w * (scene_idx + 1) / total_scenes), bar_h)
    d.rounded_rectangle([(bx, by), (bx + fill_w, by + bar_h)],
                         radius=4, fill=accent)
    # dot
    dot_cx = bx + fill_w
    d.ellipse([(dot_cx - 6, by - 3), (dot_cx + 6, by + bar_h + 3)], fill=accent)

    # ── BRAND HANDLE (subtle, top-left under bar) ─────────────────────────────
    brand_f = _find_bold_font(32)
    d.text((bx, by + bar_h + 14), BRAND_HANDLE, fill=(*accent, 130), font=brand_f)

    # ── EMOJI ANCHOR (center) ─────────────────────────────────────────────────
    emoji_size = 260 if is_hook else 200
    try:
        ef = _find_emoji_font(emoji_size)
        # Measure emoji width
        dummy = Image.new('RGB', (1, 1))
        dd = ImageDraw.Draw(dummy)
        ew = dd.textlength(emoji, font=ef)
        ex = (W - ew) // 2
        ey = H // 2 - 520 if is_hook else H // 2 - 440
        d.text((ex, ey), emoji, font=ef, embedded_color=True)
    except Exception:
        pass  # emoji rendering is optional

    # ── HEADLINE TEXT ─────────────────────────────────────────────────────────
    # Scale font size based on text length — shorter = bigger
    if len(headline) <= 14:
        font_size = 180 if is_hook else 160
    elif len(headline) <= 24:
        font_size = 150 if is_hook else 130
    else:
        font_size = 120 if is_hook else 100

    hf = _find_bold_font(font_size)
    lines = _wrap_tight(headline.upper(), hf, W - 80)

    # Compute total text block height
    line_h = int(font_size * 1.15)
    total_h = len(lines) * line_h
    start_y = H // 2 - total_h // 2 + (80 if not is_hook else 120)

    for i, line in enumerate(lines):
        dummy = Image.new('RGB', (1, 1))
        dd = ImageDraw.Draw(dummy)
        lw = dd.textlength(line, font=hf)
        x = (W - lw) // 2
        y = start_y + i * line_h
        stroke = 10 if is_hook else 8
        _draw_stroked_text(d, (x, y), line, hf, (255, 255, 255), stroke_width=stroke)

    # ── ACCENT LINE UNDER HEADLINE ────────────────────────────────────────────
    line_y = start_y + total_h + 24
    aw = min(int(W * 0.35), 300)
    ax = (W - aw) // 2
    d.rounded_rectangle([(ax, line_y), (ax + aw, line_y + 5)], radius=3, fill=accent)

    # ── SUBTEXT CAPTION (TikTok pill style) ────────────────────────────────────
    if subtext:
        sf = _find_bold_font(46)
        cap_lines = _wrap_tight(subtext, sf, W - 140)
        cap_line_h = int(46 * 1.25)
        cap_total_h = len(cap_lines) * cap_line_h + 20
        cap_y_start = H - 200 - cap_total_h

        # dark pill background
        ov = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        dv = ImageDraw.Draw(ov)
        pill_pad = 20
        dv.rounded_rectangle(
            [(50, cap_y_start - pill_pad),
             (W - 50, cap_y_start + cap_total_h + pill_pad)],
            radius=18, fill=(0, 0, 0, 170)
        )
        img = Image.alpha_composite(img.convert('RGBA'), ov).convert('RGB')
        d = ImageDraw.Draw(img)

        for i, line in enumerate(cap_lines):
            dummy = Image.new('RGB', (1, 1))
            dd = ImageDraw.Draw(dummy)
            lw = dd.textlength(line, font=sf)
            x = (W - lw) // 2
            y = cap_y_start + i * cap_line_h
            _draw_stroked_text(d, (x, y), line, sf, (240, 240, 240), stroke_width=4)

    # ── SCENE NUMBER (small, bottom-right) ──────────────────────────────────
    num_f = _find_bold_font(36)
    num_text = f'{scene_idx + 1}/{total_scenes}'
    dummy = Image.new('RGB', (1, 1))
    dd = ImageDraw.Draw(dummy)
    nw = dd.textlength(num_text, font=num_f)
    d.text((W - nw - 44, H - 58), num_text, fill=(*accent, 100), font=num_f)

    return img


def assemble_video_node(state: dict) -> dict:
    """LangGraph node: assemble viral short-form vertical video."""
    scenes: list[dict] = state.get('scenes', [])
    audio_path: str | None = state.get('audio_path')
    content_id: str = state.get('content_id', 'default')
    title: str = state.get('title', '')

    if not scenes:
        return {**state, 'error': 'No scenes to assemble'}

    video_dir = OUTPUT_DIR / content_id
    video_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = video_dir / 'frames'
    frames_dir.mkdir(exist_ok=True)

    # Pick accent color based on content_id hash
    accent = ACCENT_COLORS[hash(content_id) % len(ACCENT_COLORS)]
    total = len(scenes)

    slide_entries: list[tuple[str, int]] = []

    for i, scene in enumerate(scenes):
        text = scene.get('text', '').strip()
        if not text:
            continue

        # Split into headline + subtext (≤7 words for headline)
        sentences = [s.strip() for s in text.replace('. ', '.\n').split('\n') if s.strip()]
        first = sentences[0] if sentences else title
        rest = ' '.join(sentences[1:3]) if len(sentences) > 1 else ''

        # Trim headline to ≤7 words
        words = first.split()
        if len(words) > 7:
            headline = ' '.join(words[:7])
            sub_extra = ' '.join(words[7:])
            subtext = (sub_extra + ' ' + rest).strip()
        else:
            headline = first
            subtext = rest

        emoji = SCENE_EMOJIS[i % len(SCENE_EMOJIS)]

        img = make_viral_slide(
            scene_idx=i,
            total_scenes=total,
            headline=headline,
            subtext=subtext[:120],
            emoji=emoji,
            accent=accent,
            is_hook=(i == 0),
        )

        frame_path = str(frames_dir / f'frame_{i:02d}.jpg')
        img.save(frame_path, 'JPEG', quality=95)
        slide_entries.append((frame_path, scene.get('duration', SCENE_DURATION)))

    if not slide_entries:
        return {**state, 'error': 'No frames rendered'}

    # Write FFmpeg concat file
    concat_file = video_dir / 'concat.txt'
    with open(str(concat_file), 'w') as f:
        for path, dur in slide_entries:
            f.write(f"file '{path}'\nduration {dur}\n")
        f.write(f"file '{slide_entries[-1][0]}'\n")

    total_sec = sum(d for _, d in slide_entries)
    raw_video = str(video_dir / 'slideshow_raw.mp4')
    final_video = str(video_dir / 'final.mp4')
    ffmpeg = _get_ffmpeg()

    # Subtle zoom-in per slide (Ken Burns lite — fast enough for short clips)
    vf = (
        'scale=1200:2133:force_original_aspect_ratio=increase,'
        'crop=1080:1920,'
        "zoompan=z='if(lte(mod(on,90),1),1.0,min(zoom+0.0004,1.06))'"
        ":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=90:s=1080x1920:fps=30,"
        'setsar=1'
    )

    cmd = [
        ffmpeg, '-y', '-f', 'concat', '-safe', '0', '-i', str(concat_file),
        '-vf', vf,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
        '-t', str(total_sec), raw_video,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)

    if r.returncode != 0:
        # Simple scale fallback
        cmd2 = [
            ffmpeg, '-y', '-f', 'concat', '-safe', '0', '-i', str(concat_file),
            '-vf', (
                'scale=1080:1920:force_original_aspect_ratio=decrease,'
                'pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps=30'
            ),
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
            '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
            '-t', str(total_sec), raw_video,
        ]
        r2 = subprocess.run(cmd2, capture_output=True, text=True)
        if r2.returncode != 0:
            return {**state, 'error': f'FFmpeg error: {r2.stderr[-400:]}'}

    # Mix audio
    if audio_path and Path(audio_path).exists():
        cmd_mix = [
            ffmpeg, '-y',
            '-i', raw_video,
            '-i', audio_path,
            '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest',
            final_video,
        ]
        r3 = subprocess.run(cmd_mix, capture_output=True, text=True)
        if r3.returncode != 0:
            import shutil
            shutil.copy(raw_video, final_video)
    else:
        import shutil
        shutil.copy(raw_video, final_video)

    # Thumbnail from frame 0
    thumbnail_path = str(video_dir / 'thumbnail.jpg')
    subprocess.run([
        ffmpeg, '-y', '-i', final_video,
        '-ss', '00:00:00.5', '-vframes', '1',
        '-vf', 'scale=1280:720', thumbnail_path,
    ], capture_output=True)

    print(f'[VideoAssembler] ✅ {final_video}  ({total_sec}s, {len(slide_entries)} slides)')
    return {
        **state,
        'video_path': final_video,
        'thumbnail_path': thumbnail_path if Path(thumbnail_path).exists() else None,
        'error': None,
    }
