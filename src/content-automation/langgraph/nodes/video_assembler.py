import os
import subprocess
from pathlib import Path
from PIL import Image

OUTPUT_DIR = Path(os.getenv('VIDEO_OUTPUT_DIR', '/tmp/content-automation'))


def resize_image_for_video(image_path: str, output_path: str, target_size: tuple[int, int] = (1080, 1920)) -> str:
    """Resize/crop image to vertical 9:16 format for Shorts/TikTok."""
    with Image.open(image_path) as img:
        img = img.convert('RGB')
        target_w, target_h = target_size
        img_w, img_h = img.size
        target_ratio = target_w / target_h
        img_ratio = img_w / img_h

        if img_ratio > target_ratio:
            # Image is wider - crop sides
            new_w = int(img_h * target_ratio)
            left = (img_w - new_w) // 2
            img = img.crop((left, 0, left + new_w, img_h))
        else:
            # Image is taller - crop top/bottom
            new_h = int(img_w / target_ratio)
            top = (img_h - new_h) // 2
            img = img.crop((0, top, img_w, top + new_h))

        img = img.resize(target_size, Image.LANCZOS)
        img.save(output_path, 'JPEG', quality=95)

    return output_path


def assemble_video_node(state: dict) -> dict:
    """LangGraph node: assemble slideshow video using FFmpeg."""
    scenes: list[dict] = state.get('scenes', [])
    audio_path: str | None = state.get('audio_path')
    content_id: str = state.get('content_id', 'default')

    if not scenes:
        return {**state, 'error': 'No scenes to assemble'}

    video_dir = OUTPUT_DIR / content_id
    video_dir.mkdir(parents=True, exist_ok=True)
    resized_dir = video_dir / 'resized'
    resized_dir.mkdir(exist_ok=True)

    # Resize all images to vertical format
    ffmpeg_inputs = []
    for scene in scenes:
        if not scene.get('image_path'):
            continue
        resized_path = str(resized_dir / f"scene_{scene['index']:02d}.jpg")
        resize_image_for_video(scene['image_path'], resized_path)
        ffmpeg_inputs.append({
            'path': resized_path,
            'duration': scene.get('duration', 5),
        })

    if not ffmpeg_inputs:
        return {**state, 'error': 'No valid images to assemble'}

    # Build FFmpeg concat file
    concat_file = video_dir / 'concat.txt'
    with open(str(concat_file), 'w') as f:
        for inp in ffmpeg_inputs:
            f.write(f"file '{inp['path']}'\n")
            f.write(f"duration {inp['duration']}\n")
        # Repeat last frame to avoid ffmpeg cut-off
        f.write(f"file '{ffmpeg_inputs[-1]['path']}'\n")

    raw_video = str(video_dir / 'slideshow_raw.mp4')
    final_video = str(video_dir / 'final.mp4')

    # Step 1: Create slideshow from images
    cmd_slideshow = [
        'ffmpeg', '-y',
        '-f', 'concat', '-safe', '0', '-i', str(concat_file),
        '-vf', 'fps=30,scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
        '-pix_fmt', 'yuv420p',
        raw_video,
    ]

    result = subprocess.run(cmd_slideshow, capture_output=True, text=True)
    if result.returncode != 0:
        return {**state, 'error': f'FFmpeg slideshow error: {result.stderr[-500:]}'}

    # Step 2: Add audio (if available)
    if audio_path and Path(audio_path).exists():
        cmd_audio = [
            'ffmpeg', '-y',
            '-i', raw_video,
            '-i', audio_path,
            '-c:v', 'copy',
            '-c:a', 'aac', '-b:a', '192k',
            '-shortest',
            final_video,
        ]
        result = subprocess.run(cmd_audio, capture_output=True, text=True)
        if result.returncode != 0:
            print(f'[VideoAssembler] Audio merge warning: {result.stderr[-200:]}')
            # Use video without audio
            import shutil
            shutil.copy(raw_video, final_video)
    else:
        import shutil
        shutil.copy(raw_video, final_video)

    # Generate thumbnail from first frame
    thumbnail_path = str(video_dir / 'thumbnail.jpg')
    cmd_thumb = [
        'ffmpeg', '-y', '-i', final_video,
        '-ss', '00:00:01', '-vframes', '1',
        '-vf', 'scale=1280:720',
        thumbnail_path,
    ]
    subprocess.run(cmd_thumb, capture_output=True)

    print(f'[VideoAssembler] Video ready: {final_video}')
    return {
        **state,
        'video_path': final_video,
        'thumbnail_path': thumbnail_path if Path(thumbnail_path).exists() else None,
        'error': None,
    }
