import re
from typing import TypedDict
from anthropic import Anthropic

client = Anthropic()


class Scene(TypedDict):
    index: int
    text: str
    image_prompt: str
    duration: int


class ScriptState(TypedDict):
    title: str
    script: str
    scenes: list[Scene]
    error: str | None


def parse_scenes(script: str) -> list[Scene]:
    """Split script into timed scenes for slideshow generation."""
    pattern = r'\[SCENE\s*(\d+)\]:\s*(.+?)(?=\[SCENE|\Z)'
    matches = re.findall(pattern, script, re.DOTALL)

    if not matches:
        # Fallback: split by sentences
        sentences = [s.strip() for s in script.split('.') if s.strip()]
        return [
            {
                'index': i,
                'text': sent + '.',
                'image_prompt': f'Professional visual for: {sent[:80]}',
                'duration': max(3, len(sent.split()) // 2),
            }
            for i, sent in enumerate(sentences[:8])
        ]

    scenes = []
    for i, (num, text) in enumerate(matches):
        text = text.strip()
        words = text.split()
        scenes.append({
            'index': int(num) - 1,
            'text': text,
            'image_prompt': f'Cinematic, high-quality visual representing: {text[:100]}',
            'duration': max(3, len(words) // 2),
        })
    return scenes


def write_script_node(state: dict) -> dict:
    """LangGraph node: parse raw script into structured scenes."""
    script: str = state.get('script', '')
    title: str = state.get('title', '')

    if not script:
        return {**state, 'scenes': [], 'error': 'No script provided'}

    # Enhance scene image prompts with AI
    scenes = parse_scenes(script)

    enhanced_prompts_msg = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=1024,
        messages=[{
            'role': 'user',
            'content': f'''For a YouTube Short about "{title}", create vivid image prompts for each scene.
Return ONLY a JSON array of strings, one per scene:

Scenes:
{chr(10).join(f'{i+1}. {s["text"][:100]}' for i, s in enumerate(scenes))}

Format: ["prompt1", "prompt2", ...]
Make prompts: photorealistic, high-quality, professional, relevant to the text.''',
        }],
    )

    response_text = enhanced_prompts_msg.content[0].text if enhanced_prompts_msg.content else '[]'
    json_match = re.search(r'\[[\s\S]*\]', response_text)

    if json_match:
        import json
        try:
            prompts = json.loads(json_match.group())
            for i, scene in enumerate(scenes):
                if i < len(prompts):
                    scene['image_prompt'] = prompts[i]
        except json.JSONDecodeError:
            pass

    return {**state, 'scenes': scenes, 'error': None}
