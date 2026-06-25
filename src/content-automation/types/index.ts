export interface TrendData {
  keyword: string;
  score: number;
  category: string;
  relatedTopics: string[];
  platform: 'youtube' | 'tiktok' | 'google';
  fetchedAt: Date;
}

export interface ContentPlan {
  id: string;
  trend: TrendData;
  title: string;
  description: string;
  tags: string[];
  script: string;
  targetPlatforms: Platform[];
  estimatedDuration: number; // seconds
  scheduledAt?: Date;
  createdAt: Date;
}

export interface VideoAsset {
  id: string;
  contentPlanId: string;
  slides: SlideAsset[];
  audioPath: string;
  videoPath?: string;
  thumbnailPath?: string;
  status: 'pending' | 'generating' | 'ready' | 'failed';
  createdAt: Date;
}

export interface SlideAsset {
  index: number;
  text: string;
  imagePath: string;
  duration: number; // seconds
}

export interface PublishResult {
  platform: Platform;
  videoId: string;
  url: string;
  publishedAt: Date;
  status: 'published' | 'processing' | 'failed';
  error?: string;
}

export interface AnalyticsData {
  videoId: string;
  platform: Platform;
  views: number;
  likes: number;
  comments: number;
  shares: number;
  watchTime: number; // seconds
  revenue?: number; // USD
  fetchedAt: Date;
}

export type Platform = 'youtube' | 'tiktok';

export interface AgentConfig {
  anthropicApiKey: string;
  openaiApiKey: string;
  elevenLabsApiKey: string;
  youtubeClientId: string;
  youtubeClientSecret: string;
  youtubeRefreshToken: string;
  tiktokClientKey: string;
  tiktokClientSecret: string;
  tiktokAccessToken: string;
  langGraphApiUrl: string;
  trendCheckIntervalMs: number;
  publishSchedule: string; // cron expression
}

export interface WorkflowState {
  trends: TrendData[];
  contentPlans: ContentPlan[];
  videoAssets: VideoAsset[];
  publishResults: PublishResult[];
  analytics: AnalyticsData[];
  errors: Array<{ agent: string; error: string; timestamp: Date }>;
}
