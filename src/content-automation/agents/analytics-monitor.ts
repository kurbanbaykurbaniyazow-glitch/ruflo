import type { AnalyticsData, PublishResult, AgentConfig } from '../types/index.js';

interface YouTubeStatsResponse {
  items: Array<{
    statistics: {
      viewCount: string;
      likeCount: string;
      commentCount: string;
    };
  }>;
}

interface TikTokVideoData {
  id: string;
  statistics: {
    digg_count: number;
    comment_count: number;
    share_count: number;
    play_count: number;
  };
}

interface TikTokStatsResponse {
  data: { videos: TikTokVideoData[] };
}

export class AnalyticsMonitorAgent {
  private youtubeApiKey: string;

  constructor(private config: AgentConfig) {
    this.youtubeApiKey = process.env.YOUTUBE_API_KEY || '';
  }

  async fetchYouTubeStats(videoId: string): Promise<AnalyticsData> {
    const params = new URLSearchParams({
      part: 'statistics',
      id: videoId,
      key: this.youtubeApiKey,
    });

    const response = await fetch(`https://www.googleapis.com/youtube/v3/videos?${params}`);
    if (!response.ok) throw new Error(`YouTube stats error: ${response.status}`);

    const data = await response.json() as YouTubeStatsResponse;
    const stats = data.items[0]?.statistics;
    if (!stats) throw new Error(`Video ${videoId} not found`);

    return {
      videoId,
      platform: 'youtube',
      views: parseInt(stats.viewCount || '0', 10),
      likes: parseInt(stats.likeCount || '0', 10),
      comments: parseInt(stats.commentCount || '0', 10),
      shares: 0,
      watchTime: 0,
      fetchedAt: new Date(),
    };
  }

  async fetchTikTokStats(videoId: string): Promise<AnalyticsData> {
    const response = await fetch('https://open.tiktokapis.com/v2/video/query/', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${this.config.tiktokAccessToken}`,
        'Content-Type': 'application/json; charset=UTF-8',
      },
      body: JSON.stringify({
        filters: { video_ids: [videoId] },
        fields: ['id', 'statistics'],
      }),
    });

    if (!response.ok) throw new Error(`TikTok stats error: ${response.status}`);
    const data = await response.json() as TikTokStatsResponse;
    const video = data.data?.videos?.[0];
    if (!video) throw new Error(`TikTok video ${videoId} not found`);

    return {
      videoId,
      platform: 'tiktok',
      views: video.statistics.play_count,
      likes: video.statistics.digg_count,
      comments: video.statistics.comment_count,
      shares: video.statistics.share_count,
      watchTime: 0,
      fetchedAt: new Date(),
    };
  }

  async monitorAll(results: PublishResult[]): Promise<AnalyticsData[]> {
    console.log(`[AnalyticsMonitor] Fetching stats for ${results.length} videos...`);

    const analytics = await Promise.allSettled(
      results.map((result) => {
        if (result.platform === 'youtube') return this.fetchYouTubeStats(result.videoId);
        if (result.platform === 'tiktok') return this.fetchTikTokStats(result.videoId);
        return Promise.reject(new Error(`Unknown platform: ${result.platform}`));
      })
    );

    const data = analytics
      .filter((r): r is PromiseFulfilledResult<AnalyticsData> => r.status === 'fulfilled')
      .map((r) => r.value);

    this.logPerformance(data);
    return data;
  }

  private logPerformance(data: AnalyticsData[]): void {
    for (const stat of data) {
      console.log(
        `[AnalyticsMonitor] ${stat.platform} video ${stat.videoId}: ` +
        `${stat.views.toLocaleString()} views, ${stat.likes.toLocaleString()} likes`
      );
    }

    const topPerformers = data
      .sort((a, b) => b.views - a.views)
      .slice(0, 3);

    if (topPerformers.length > 0) {
      console.log('[AnalyticsMonitor] Top performers:', topPerformers.map((v) => v.videoId));
    }
  }
}
