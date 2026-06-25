import { createReadStream, statSync } from 'fs';
import type { ContentPlan, VideoAsset, PublishResult } from '../types/index.js';

interface TikTokInitResponse {
  data: { publish_id: string; upload_url: string };
  error: { code: string; message: string };
}

interface TikTokStatusResponse {
  data: { status: string; video_id?: string; share_url?: string };
  error: { code: string; message: string };
}

export class TikTokPublisherAgent {
  constructor(private accessToken: string) {}

  async upload(plan: ContentPlan, asset: VideoAsset): Promise<PublishResult> {
    if (!asset.videoPath) throw new Error('Video path not set on asset');

    console.log(`[TikTokPublisher] Uploading: "${plan.title}"`);
    const fileSize = statSync(asset.videoPath).size;

    // Step 1: Initialize video upload
    const initResponse = await fetch('https://open.tiktokapis.com/v2/post/publish/video/init/', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${this.accessToken}`,
        'Content-Type': 'application/json; charset=UTF-8',
      },
      body: JSON.stringify({
        post_info: {
          title: plan.title.slice(0, 2200),
          privacy_level: 'PUBLIC_TO_EVERYONE',
          disable_duet: false,
          disable_comment: false,
          disable_stitch: false,
          video_cover_timestamp_ms: 1000,
        },
        source_info: {
          source: 'FILE_UPLOAD',
          video_size: fileSize,
          chunk_size: fileSize,
          total_chunk_count: 1,
        },
      }),
    });

    const initData = await initResponse.json() as TikTokInitResponse;
    if (initData.error?.code !== 'ok') {
      throw new Error(`TikTok init failed: ${initData.error?.message}`);
    }

    const { publish_id, upload_url } = initData.data;

    // Step 2: Upload video binary
    const fileStream = createReadStream(asset.videoPath);
    const uploadResponse = await fetch(upload_url, {
      method: 'PUT',
      headers: {
        'Content-Type': 'video/mp4',
        'Content-Length': String(fileSize),
        'Content-Range': `bytes 0-${fileSize - 1}/${fileSize}`,
      },
      body: fileStream as unknown as BodyInit,
    });

    if (!uploadResponse.ok) {
      throw new Error(`TikTok video upload failed: ${uploadResponse.status}`);
    }

    // Step 3: Poll for publish status
    const videoId = await this.pollPublishStatus(publish_id);
    console.log(`[TikTokPublisher] Uploaded successfully, publish_id: ${publish_id}`);

    return {
      platform: 'tiktok',
      videoId,
      url: `https://www.tiktok.com/@me/video/${videoId}`,
      publishedAt: new Date(),
      status: 'published',
    };
  }

  private async pollPublishStatus(publishId: string, maxAttempts = 10): Promise<string> {
    for (let i = 0; i < maxAttempts; i++) {
      await new Promise((r) => setTimeout(r, 3000));

      const response = await fetch('https://open.tiktokapis.com/v2/post/publish/status/fetch/', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${this.accessToken}`,
          'Content-Type': 'application/json; charset=UTF-8',
        },
        body: JSON.stringify({ publish_id: publishId }),
      });

      const data = await response.json() as TikTokStatusResponse;
      const status = data.data?.status;

      if (status === 'PUBLISH_COMPLETE') {
        return data.data.video_id || publishId;
      }
      if (status === 'FAILED') {
        throw new Error(`TikTok publish failed for publish_id: ${publishId}`);
      }

      console.log(`[TikTokPublisher] Status: ${status}, attempt ${i + 1}/${maxAttempts}`);
    }
    throw new Error(`TikTok publish timeout for publish_id: ${publishId}`);
  }
}
