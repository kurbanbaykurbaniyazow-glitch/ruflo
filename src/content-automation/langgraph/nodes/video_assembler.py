"""
Video assembler: composites DALL-E images into a cinematic studio-quality vertical video.
When no AI images are available, falls back to professional PIL-generated slides.
"""
import os
import random
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUTPUT_DIR = Path(os.getenv('VIDEO_OUTPUT_DIR', '/tmp/content-automation'))
BRAND_HANDLE = os.getenv('BRAND_HANDLE', '@AIInsiderDaily')
W, H = 1080, 1920


def _get_ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return 'ffmpeg'


def _font(size: int, bold: bool = True) -> ImageFont.ImageFont:
    candidates = [
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans-{'Bold' if bold else ''}.ttf",
        f"/usr/share/fonts/truetype/liberation/LiberationSans-{'Bold' if bold else 'Regular'}.ttf",
        f"/usr/share/fonts/truetype/ubuntu/Ubuntu-{'B' if bold else 'R'}.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                pass
    return ImageFont.load_default()


def _vgrad(img: Image.Image, c1: tuple, c2: tuple) -> None:
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        r, g, b = (int(c1[i] + t * (c2[i] - c1[i])) for i in range(3))
        d.line([(0, y), (W, y)], fill=(r, g, b))


def _add_vignette(img: Image.Image) -> Image.Image:
    ov = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    cx, cy = W // 2, H // 2
    for r in range(max(W, H), 0, -10):
        dist = r / max(W, H)
        a = max(0, int(150 * (dist ** 2.2)))
        d.ellipse([(cx - r, cy - r * 1.4), (cx + r, cy + r * 1.4)], fill=(0, 0, 0, a))
    return Image.alpha_composite(img.convert('RGBA'), ov).convert('RGB')


def _add_grain(img: Image.Image, intensity: int = 10) -> Image.Image:
    ov = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for _ in range(W * H // 100):
        x, y = random.randint(0, W - 1), random.randint(0, H - 1)
        a = random.randint(0, intensity)
        d.point((x, y), fill=(255, 255, 255, a))
    return Image.alpha_composite(img.convert('RGBA'), ov).convert('RGB')


def _add_scanlines(img: Image.Image, alpha: int = 14) -> Image.Image:
    ov = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for y in range(0, H, 4):
        d.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))
    return Image.alpha_composite(img.convert('RGBA'), ov).convert('RGB')


def _add_glow(img: Image.Image, color: tuple, cx: int = W // 2, cy: int = H // 2) -> Image.Image:
    ov = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for i in range(7):
        r = 550 - i * 60
        a = max(0, 40 - i * 5)
        d.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=(*color, a))
    return Image.alpha_composite(img.convert('RGBA'), ov).convert('RGB')


def _wrap(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.ImageFont, max_w: int) -> list[str]:
    lines = []
    for raw in text.split('\n'):
        words = raw.split()
        if not words:
            lines.append('')
            continue
        cur = ''
        for w in words:
            t = (cur + ' ' + w).strip()
            if draw.textlength(t, font=f) <= max_w:
                cur = t
            else:
                if cur:
                    lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def _put(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.ImageFont,
         y: int, fill: tuple, max_w: int = W - 100, shadow: bool = True) -> int:
    for line in _wrap(draw, text, f, max_w):
        if not line:
            y += int(f.size * 0.4)
            continue
        lw = draw.textlength(line, font=f)
        x = (W - lw) // 2
        if shadow:
            draw.text((x + 3, y + 3), line, fill=(0, 0, 0, 130), font=f)
        draw.text((x, y), line, fill=fill, font=f)
        y += int(f.size * 1.22)
    return y


# Cinematic color palettes — one per scene type
PALETTES = [
    {'bg': [(4, 4, 8), (14, 8, 24)],   'acc': (139, 92, 246)},   # purple
    {'bg': [(4, 12, 22), (8, 22, 44)],  'acc': (56, 189, 248)},   # cyan
    {'bg': [(4, 16, 6), (8, 28, 14)],   'acc': (16, 185, 129)},   # green
    {'bg': [(20, 8, 4), (36, 14, 6)],   'acc': (251, 146, 60)},   # orange
    {'bg': [(20, 4, 8), (36, 8, 16)],   'acc': (251, 113, 133)},  # pink
    {'bg': [(18, 16, 4), (30, 26, 8)],  'acc': (250, 204, 21)},   # gold
    {'bg': [(10, 10, 10), (20, 20, 20)],'acc': (255, 255, 255)},  # white
]

TOTAL_SCENES = 7


def make_studio_slide(
    idx: int,
    total: int,
    eyebrow: str,
    headline: str,
    body: str,
    caption: str,
    image_path: str | None = None,
    palette: dict | None = None,
) -> Image.Image:
    """Render a single cinematic studio-style slide."""
    pal = palette or PALETTES[idx % len(PALETTES)]
    acc = pal['acc']
    bg1, bg2 = pal['bg'][0], pal['bg'][1]

    # Base
    img = Image.new('RGB', (W, H), bg1)
    _vgrad(img, bg1, bg2)
    img = _add_glow(img, acc)
    img = _add_grain(img)
    img = _add_vignette(img)
    img = _add_scanlines(img)

    # If we have a DALL-E image, composite it behind the text
    if image_path and Path(image_path).exists():
        try:
            bg_img = Image.open(image_path).convert('RGB').resize((W, H), Image.LANCZOS)
            # Blend 30% image + 70% gradient for readability
            img = Image.blend(img, bg_img, alpha=0.30)
            img = _add_vignette(img)  # re-apply vignette
        except Exception:
            pass

    d = ImageDraw.Draw(img)

    # Top accent line
    d.rectangle([(0, 0), (W, 3)], fill=acc)

    # Brand handle
    d.text((44, 22), BRAND_HANDLE, fill=(*acc, 155), font=_font(30, bold=False))

    # Eyebrow pill (top-right)
    ef = _font(30)
    ew = int(d.textlength(eyebrow, font=ef))
    ex = W - ew - 80
    ey = 16
    d.rounded_rectangle([(ex - 14, ey - 4), (ex + ew + 14, ey + 40)], radius=20, fill=acc)
    d.text((ex, ey + 3), eyebrow, fill=(0, 0, 0, 230), font=ef)

    # Scene progress dots
    dot_y = 96
    step = 28
    start_x = (W - total * step) // 2
    for i in range(total):
        cx = start_x + i * step + 6
        if i == idx:
            d.ellipse([(cx - 7, dot_y - 7), (cx + 7, dot_y + 7)], fill=acc)
        else:
            d.ellipse([(cx - 4, dot_y - 4), (cx + 4, dot_y + 4)], fill=(*acc, 65))

    # Headline
    hl_size = 100 if max(len(l) for l in headline.split('\n')) < 14 else 80
    hf = _font(hl_size)
    hy = H // 2 - 320
    hy = _put(d, headline, hf, hy, (255, 255, 255))

    # Thin accent divider
    d.rounded_rectangle([(W // 2 - 90, hy + 16), (W // 2 + 90, hy + 19)], radius=2, fill=acc)
    hy += 44

    # Body
    if body:
        bf = _font(50, bold=False)
        hy = _put(d, body, bf, hy, (210, 215, 225), shadow=False)

    # Lower-third caption
    if caption:
        cf = _font(40, bold=False)
        cap_y = H - 195
        ov3 = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        d3 = ImageDraw.Draw(ov3)
        d3.rounded_rectangle([(50, cap_y - 16), (W - 50, cap_y + 58)], radius=14, fill=(0, 0, 0, 130))
        img = Image.alpha_composite(img.convert('RGBA'), ov3).convert('RGB')
        d = ImageDraw.Draw(img)
        cw = d.textlength(caption, font=cf)
        d.text(((W - cw) // 2, cap_y), caption, fill=(228, 228, 228), font=cf)

    # Progress bar
    bar_w = W - 80
    bx = 40
    bar_y = H - 44
    d.rounded_rectangle([(bx, bar_y), (bx + bar_w, bar_y + 5)], radius=3, fill=(*acc, 45))
    fill_w = int(bar_w * ((idx + 1) / total))
    if fill_w > 4:
        d.rounded_rectangle([(bx, bar_y), (bx + fill_w, bar_y + 5)], radius=3, fill=acc)
    d.ellipse([(bx + fill_w - 6, bar_y - 3), (bx + fill_w + 6, bar_y + 8)], fill=acc)

    # Bottom accent line
    d.rectangle([(0, H - 4), (W, H)], fill=acc)

    return img


def assemble_video_node(state: dict) -> dict:
    """LangGraph node: assemble studio-quality vertical video from scenes + audio."""
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

    # Build script-based scene breakdown from script text
    total = len(scenes)
    slide_entries: list[tuple[str, int]] = []

    for i, scene in enumerate(scenes):
        pal = PALETTES[i % len(PALETTES)]
        text = scene.get('text', '')
        image_path = scene.get('image_path')

        # Split scene text into headline / body
        lines = [l.strip() for l in text.split('.') if l.strip()]
        headline = lines[0] if lines else title
        body = '. '.join(lines[1:3]) if len(lines) > 1 else ''
        caption = lines[3] if len(lines) > 3 else ''

        img = make_studio_slide(
            idx=i,
            total=total,
            eyebrow=f'#{i + 1} of {total}',
            headline=headline[:80],
            body=body[:120],
            caption=caption[:80],
            image_path=image_path,
            palette=pal,
        )
        frame_path = str(frames_dir / f'frame_{i:02d}.jpg')
        img.save(frame_path, 'JPEG', quality=96)
        slide_entries.append((frame_path, scene.get('duration', 5)))

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

    # Ken Burns zoom-pan
    vf = (
        'scale=1200:2133:force_original_aspect_ratio=increase,'
        'crop=1080:1920,'
        "zoompan=z='if(lte(mod(on\\,150)\\,1)\\,1.0\\,min(zoom+0.00035\\,1.07))'"
        ':x=\'iw/2-(iw/zoom/2)\':y=\'ih/2-(ih/zoom/2)\':d=150:s=1080x1920:fps=30,'
        'setsar=1'
    )

    cmd_video = [
        ffmpeg, '-y', '-f', 'concat', '-safe', '0', '-i', str(concat_file),
        '-vf', vf,
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '17',
        '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
        '-t', str(total_sec), raw_video,
    ]
    r = subprocess.run(cmd_video, capture_output=True, text=True)
    if r.returncode != 0:
        # Fallback: simple scale
        cmd_simple = [
            ffmpeg, '-y', '-f', 'concat', '-safe', '0', '-i', str(concat_file),
            '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps=30',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '17',
            '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-t', str(total_sec), raw_video,
        ]
        r2 = subprocess.run(cmd_simple, capture_output=True, text=True)
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

    # Thumbnail
    thumbnail_path = str(video_dir / 'thumbnail.jpg')
    subprocess.run([
        ffmpeg, '-y', '-i', final_video, '-ss', '00:00:01',
        '-vframes', '1', '-vf', 'scale=1280:720', thumbnail_path,
    ], capture_output=True)

    print(f'[VideoAssembler] ✅ {final_video}')
    return {
        **state,
        'video_path': final_video,
        'thumbnail_path': thumbnail_path if Path(thumbnail_path).exists() else None,
        'error': None,
    }
