#!/usr/bin/env python3
"""Standalone test: generate a viral-style video with no API calls."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'content-automation', 'langgraph'))

from nodes.video_assembler import assemble_video_node

SCENES = [
    {"text": "99% of people waste their money on this. Are you one of them?", "duration": 3},
    {"text": "Every single month you lose $200 without even knowing it.", "duration": 3},
    {"text": "The trick banks don't want you to know. It takes 5 minutes.", "duration": 3},
    {"text": "People who use this save $2,400 per year on average.", "duration": 3},
    {"text": "Most people skip this step. That's exactly why they stay broke.", "duration": 3},
    {"text": "Follow for daily money hacks that actually work.", "duration": 3},
]

state = {
    "content_id": "test-viral-001",
    "title": "Money Hack Nobody Talks About",
    "scenes": SCENES,
    "audio_path": None,
}

print("Generating viral video...")
result = assemble_video_node(state)

if result.get("error"):
    print(f"ERROR: {result['error']}")
    sys.exit(1)

video = result["video_path"]
thumb = result.get("thumbnail_path")
print(f"\nVideo:     {video}")
print(f"Thumbnail: {thumb}")

size = os.path.getsize(video) / 1024
print(f"Size:      {size:.0f} KB")
print("\nDone!")
