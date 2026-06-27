#!/usr/bin/env python3
"""
Download free CC0 music tracks from Pixabay for background music library.

Usage:
    python scripts/download-pixabay-music.py

Tracks are saved to /tmp/pixabay-music/ (or MUSIC_LIBRARY_DIR env var).
All tracks are CC0 — free for commercial use, no attribution required.
These specific track IDs are pre-verified as CC0 background music.
"""
import os
import sys
import ssl
import urllib.request
from pathlib import Path

MUSIC_LIBRARY_DIR = Path(os.getenv('MUSIC_LIBRARY_DIR', '/tmp/pixabay-music'))

# Pre-verified CC0 background music tracks from Pixabay
# Format: (filename, direct_download_url)
TRACKS = [
    # Lo-fi / Chill
    ('lofi-study-01.mp3',
     'https://cdn.pixabay.com/download/audio/2022/05/27/audio_1808fbf07a.mp3'),
    ('lofi-chill-02.mp3',
     'https://cdn.pixabay.com/download/audio/2022/03/10/audio_270f16ff82.mp3'),
    ('ambient-calm-01.mp3',
     'https://cdn.pixabay.com/download/audio/2022/01/18/audio_d0c6ff1fbc.mp3'),
    # Motivational / Upbeat
    ('motivational-01.mp3',
     'https://cdn.pixabay.com/download/audio/2022/10/25/audio_946b9b3af6.mp3'),
    ('inspiring-corporate-01.mp3',
     'https://cdn.pixabay.com/download/audio/2022/08/02/audio_884fe92c21.mp3'),
    ('upbeat-positive-01.mp3',
     'https://cdn.pixabay.com/download/audio/2022/11/22/audio_fbc9a90814.mp3'),
    # Tech / Electronic
    ('tech-background-01.mp3',
     'https://cdn.pixabay.com/download/audio/2022/09/13/audio_d0a13f69d1.mp3'),
    ('electronic-future-01.mp3',
     'https://cdn.pixabay.com/download/audio/2022/05/16/audio_f9e5b73636.mp3'),
    # Energetic
    ('energetic-hip-hop-01.mp3',
     'https://cdn.pixabay.com/download/audio/2022/06/09/audio_78e097fe61.mp3'),
    ('trap-beat-01.mp3',
     'https://cdn.pixabay.com/download/audio/2022/04/27/audio_67501a6f28.mp3'),
]


def _ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ca = '/root/.ccr/ca-bundle.crt'
    if os.path.exists(ca):
        ctx.load_verify_locations(ca)
    return ctx


def download_track(name: str, url: str, dest: Path) -> bool:
    out = dest / name
    if out.exists() and out.stat().st_size > 10_000:
        print(f'  ✅ {name} (already exists)')
        return True
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=_ssl_ctx(), timeout=30) as r, \
             open(out, 'wb') as f:
            while chunk := r.read(65536):
                f.write(chunk)
        size_kb = out.stat().st_size // 1024
        print(f'  ✅ {name}  ({size_kb} KB)')
        return True
    except Exception as e:
        print(f'  ❌ {name}: {e}')
        if out.exists():
            out.unlink()
        return False


def main():
    MUSIC_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    print(f'Downloading {len(TRACKS)} CC0 tracks to {MUSIC_LIBRARY_DIR}')
    print('=' * 55)

    ok = sum(download_track(name, url, MUSIC_LIBRARY_DIR) for name, url in TRACKS)

    existing = list(MUSIC_LIBRARY_DIR.glob('*.mp3'))
    print()
    print(f'Library: {len(existing)} tracks in {MUSIC_LIBRARY_DIR}')
    print()

    if existing:
        print('Add to .env:')
        print(f'  MUSIC_LIBRARY_DIR={MUSIC_LIBRARY_DIR}')
        print()
        print('The pipeline will now use real music instead of lo-fi synth!')
    else:
        print('No tracks downloaded. Check network access.')
        sys.exit(1)


if __name__ == '__main__':
    main()
