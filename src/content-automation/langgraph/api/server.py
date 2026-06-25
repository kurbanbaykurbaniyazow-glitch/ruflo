"""FastAPI server exposing the LangGraph video pipeline to Ruflo."""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel

from video_pipeline import run_video_pipeline, VideoPipelineState

app = FastAPI(title='Content Automation Video Pipeline', version='1.0.0')

# In-memory job store (use Redis/DB in production)
jobs: dict[str, dict] = {}


class VideoRequest(BaseModel):
    content_id: str
    title: str
    script: str


class VideoStatus(BaseModel):
    content_id: str
    status: str
    video_path: str | None = None
    thumbnail_path: str | None = None
    error: str | None = None


@app.get('/health')
def health() -> dict:
    return {'status': 'ok', 'service': 'video-pipeline'}


@app.post('/generate', response_model=VideoStatus)
async def generate_video(request: VideoRequest, background_tasks: BackgroundTasks) -> VideoStatus:
    """Start async video generation job."""
    content_id = request.content_id
    jobs[content_id] = {'status': 'processing', 'video_path': None, 'thumbnail_path': None, 'error': None}

    async def process():
        try:
            result: VideoPipelineState = await run_video_pipeline(
                content_id=content_id,
                title=request.title,
                script=request.script,
            )
            jobs[content_id] = {
                'status': 'failed' if result.get('error') else 'ready',
                'video_path': result.get('video_path'),
                'thumbnail_path': result.get('thumbnail_path'),
                'error': result.get('error'),
            }
        except Exception as e:
            jobs[content_id] = {'status': 'failed', 'video_path': None, 'thumbnail_path': None, 'error': str(e)}

    background_tasks.add_task(process)
    return VideoStatus(content_id=content_id, status='processing')


@app.get('/status/{content_id}', response_model=VideoStatus)
def get_status(content_id: str) -> VideoStatus:
    """Check video generation job status."""
    job = jobs.get(content_id)
    if not job:
        raise HTTPException(status_code=404, detail=f'Job {content_id} not found')
    return VideoStatus(content_id=content_id, **job)


@app.get('/download/{content_id}')
def download_video(content_id: str) -> FileResponse:
    """Download the generated video file."""
    job = jobs.get(content_id)
    if not job or job['status'] != 'ready':
        raise HTTPException(status_code=404, detail='Video not ready')
    video_path = job['video_path']
    if not video_path or not Path(video_path).exists():
        raise HTTPException(status_code=404, detail='Video file not found')
    return FileResponse(video_path, media_type='video/mp4', filename=f'{content_id}.mp4')


@app.get('/thumbnail/{content_id}')
def download_thumbnail(content_id: str) -> FileResponse:
    """Download the video thumbnail."""
    job = jobs.get(content_id)
    if not job or not job.get('thumbnail_path'):
        raise HTTPException(status_code=404, detail='Thumbnail not ready')
    thumb_path = job['thumbnail_path']
    if not Path(thumb_path).exists():
        raise HTTPException(status_code=404, detail='Thumbnail file not found')
    return FileResponse(thumb_path, media_type='image/jpeg', filename=f'{content_id}_thumb.jpg')


if __name__ == '__main__':
    import uvicorn
    port = int(os.getenv('VIDEO_PIPELINE_PORT', '8001'))
    uvicorn.run(app, host='0.0.0.0', port=port, log_level='info')
