import type { AgentConfig } from '../types/index.js';

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`Missing required environment variable: ${name}`);
  return value;
}

function optionalEnv(name: string, fallback = ''): string {
  return process.env[name] || fallback;
}

export function loadConfig(): AgentConfig {
  const youtubeApiKey = optionalEnv('YOUTUBE_API_KEY');

  return {
    anthropicApiKey: optionalEnv('ANTHROPIC_API_KEY'),
    openaiApiKey: optionalEnv('OPENAI_API_KEY'),
    elevenLabsApiKey: optionalEnv('ELEVENLABS_API_KEY'),
    // YouTube publish credentials — optional, needed only for uploading
    youtubeClientId: optionalEnv('YOUTUBE_CLIENT_ID'),
    youtubeClientSecret: optionalEnv('YOUTUBE_CLIENT_SECRET'),
    youtubeRefreshToken: optionalEnv('YOUTUBE_REFRESH_TOKEN'),
    // TikTok — optional
    tiktokClientKey: optionalEnv('TIKTOK_CLIENT_KEY'),
    tiktokClientSecret: optionalEnv('TIKTOK_CLIENT_SECRET'),
    tiktokAccessToken: optionalEnv('TIKTOK_ACCESS_TOKEN'),
    langGraphApiUrl: optionalEnv('LANGGRAPH_API_URL', 'http://localhost:8001'),
    trendCheckIntervalMs: parseInt(optionalEnv('TREND_CHECK_INTERVAL_MS', '3600000'), 10),
    publishSchedule: optionalEnv('PUBLISH_SCHEDULE', '0 9,15,21 * * *'),
  };
}

export function getCapabilities(config: AgentConfig): {
  canFetchTrends: boolean;
  canPlanContent: boolean;
  canGenerateVideos: boolean;
  canPublishYouTube: boolean;
  canPublishTikTok: boolean;
} {
  return {
    canFetchTrends: !!process.env.YOUTUBE_API_KEY,
    canPlanContent: !!(config.anthropicApiKey || config.openaiApiKey),
    canGenerateVideos: !!config.openaiApiKey,
    canPublishYouTube: !!(config.youtubeClientId && config.youtubeClientSecret && config.youtubeRefreshToken),
    canPublishTikTok: !!config.tiktokAccessToken,
  };
}

export const EXAMPLE_ENV = `
# Step 1 — YouTube trends (you have this already)
YOUTUBE_API_KEY=AIzaSy...

# Step 2 — AI content generation (optional for now)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Step 3 — Video voice (optional)
ELEVENLABS_API_KEY=...

# Step 4 — Publish to YouTube (OAuth, needed for upload)
YOUTUBE_CLIENT_ID=...
YOUTUBE_CLIENT_SECRET=...
YOUTUBE_REFRESH_TOKEN=...

# Step 5 — Publish to TikTok (optional)
TIKTOK_ACCESS_TOKEN=...

# Config
LANGGRAPH_API_URL=http://localhost:8001
VIDEO_OUTPUT_DIR=/tmp/content-automation
`.trim();
