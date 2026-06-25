import { createReadStream, statSync } from 'fs';
import type { ContentPlan, VideoAsset, PublishResult } from '../types/index.js';

interface YouTubeTokenResponse {
  access_token: string;
  expires_in: number;
  token_type: string;
}

interface YouTubeUploadResponse {
  id: string;
  status?: { uploadStatus: string };
}

export class YouTubePublisherAgent {
  private accessToken: string | null = null;
  private tokenExpiresAt = 0;

  constructor(
    private clientId: string,
    private clientSecret: string,
    private refreshToken: string,
  ) {}

  private async getAccessToken(): Promise<string> {
    if (this.accessToken && Date.now() < this.tokenExpiresAt - 60000) {
      return this.accessToken;
    }

    const response = await fetch('https://oauth2.googleapis.com/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        client_id: this.clientId,
        client_secret: this.clientSecret,
        refresh_token: this.refreshToken,
        grant_type: 'refresh_token',
      }),
    });

    if (!response.ok) throw new Error(`OAuth token refresh failed: ${response.status}`);
    const data = await response.json() as YouTubeTokenResponse;
    this.accessToken = data.access_token;
    this.tokenExpiresAt = Date.now() + data.expires_in * 1000;
    return this.accessToken;
  }

  async upload(plan: ContentPlan, asset: VideoAsset): Promise<PublishResult> {
    if (!asset.videoPath) throw new Error('Video path not set on asset');

    console.log(`[YouTubePublisher] Uploading: "${plan.title}"`);
    const token = await this.getAccessToken();

    const metadata = {
      snippet: {
        title: plan.title.slice(0, 100),
        description: plan.description.slice(0, 5000),
        tags: plan.tags.slice(0, 15),
        categoryId: '22', // People & Blogs
        defaultLanguage: 'en',
      },
      status: {
        privacyStatus: 'public',
        selfDeclaredMadeForKids: false,
        madeForKids: false,
      },
    };

    // Step 1: Initialize resumable upload
    const initResponse = await fetch(
      'https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status',
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
          'X-Upload-Content-Type': 'video/*',
          'X-Upload-Content-Length': String(statSync(asset.videoPath).size),
        },
        body: JSON.stringify(metadata),
      }
    );

    if (!initResponse.ok) {
      const err = await initResponse.text();
      throw new Error(`YouTube upload init failed: ${err}`);
    }

    const uploadUrl = initResponse.headers.get('Location');
    if (!uploadUrl) throw new Error('No upload URL returned from YouTube');

    // Step 2: Upload video file
    const fileStream = createReadStream(asset.videoPath);
    const fileSize = statSync(asset.videoPath).size;

    const uploadResponse = await fetch(uploadUrl, {
      method: 'PUT',
      headers: {
        'Content-Type': 'video/mp4',
        'Content-Length': String(fileSize),
      },
      body: fileStream as unknown as BodyInit,
    });

    if (!uploadResponse.ok) {
      const err = await uploadResponse.text();
      throw new Error(`YouTube video upload failed: ${err}`);
    }

    const data = await uploadResponse.json() as YouTubeUploadResponse;
    const videoId = data.id;

    // Step 3: Set thumbnail if available
    if (asset.thumbnailPath) {
      await this.setThumbnail(token, videoId, asset.thumbnailPath).catch((e) =>
        console.warn('[YouTubePublisher] Thumbnail upload failed:', e.message)
      );
    }

    console.log(`[YouTubePublisher] Uploaded successfully: https://youtube.com/watch?v=${videoId}`);
    return {
      platform: 'youtube',
      videoId,
      url: `https://www.youtube.com/watch?v=${videoId}`,
      publishedAt: new Date(),
      status: 'published',
    };
  }

  private async setThumbnail(token: string, videoId: string, thumbnailPath: string): Promise<void> {
    const { createReadStream: rs, statSync: ss } = await import('fs');
    const stream = rs(thumbnailPath);
    const size = ss(thumbnailPath).size;

    const response = await fetch(
      `https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId=${videoId}&uploadType=media`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'image/jpeg',
          'Content-Length': String(size),
        },
        body: stream as unknown as BodyInit,
      }
    );
    if (!response.ok) throw new Error(`Thumbnail set failed: ${response.status}`);
  }
}
