"""
LangGraph video generation pipeline.
Graph: script_writer → image_generator → tts_generator → video_assembler
"""
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from nodes.image_generator import generate_image_node
from nodes.script_writer import write_script_node
from nodes.tts_generator import generate_tts_node
from nodes.video_assembler import assemble_video_node


class VideoPipelineState(TypedDict, total=False):
    content_id: str
    title: str
    script: str
    scenes: list[dict]
    audio_path: str | None
    video_path: str | None
    thumbnail_path: str | None
    error: str | None


def should_continue(state: VideoPipelineState) -> str:
    """Route: stop on error, continue otherwise."""
    return END if state.get('error') else 'continue'


def build_video_pipeline() -> StateGraph:
    graph = StateGraph(VideoPipelineState)

    graph.add_node('script_writer', write_script_node)
    graph.add_node('image_generator', generate_image_node)
    graph.add_node('tts_generator', generate_tts_node)
    graph.add_node('video_assembler', assemble_video_node)

    graph.add_edge(START, 'script_writer')
    graph.add_conditional_edges('script_writer', should_continue, {'continue': 'image_generator', END: END})

    # Image and TTS can run in parallel after script_writer
    graph.add_conditional_edges('image_generator', should_continue, {'continue': 'tts_generator', END: END})
    graph.add_edge('tts_generator', 'video_assembler')
    graph.add_edge('video_assembler', END)

    return graph.compile()


pipeline = build_video_pipeline()


async def run_video_pipeline(content_id: str, title: str, script: str) -> VideoPipelineState:
    """Run the full video generation pipeline."""
    initial_state: VideoPipelineState = {
        'content_id': content_id,
        'title': title,
        'script': script,
        'scenes': [],
        'audio_path': None,
        'video_path': None,
        'thumbnail_path': None,
        'error': None,
    }

    result = await pipeline.ainvoke(initial_state)
    return result  # type: ignore[return-value]
