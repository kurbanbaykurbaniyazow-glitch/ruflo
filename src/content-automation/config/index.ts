import type { AgentConfig } from '../types/index.js';

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`Missing required environment variable: ${name}`);
  return value;
}

export function loadConfig(): AgentConfig {
  return {
    anthropicApiKey: requireEnv('ANTHROPIC_API_KEY'),
    openaiApiKey: requireEnv('OPENAI_API_KEY'),
    elevenLabsApiKey: process.env.ELEVENLABS_API_KEY || '',
    youtubeClientId: requireEnv('YOUTUBE_CLIENT_ID'),
    youtubeClientSecret: requireEnv('YOUTUBE_CLIENT_SECRET'),
    youtubeRefreshToken: requireEnv('YOUTUBE_REFRESH_TOKEN'),
    tiktokClientKey: process.env.TIKTOK_CLIENT_KEY || '',
    tiktokClientSecret: process.env.TIKTOK_CLIENT_SECRET || '',
    tiktokAccessToken: requireEnv('TIKTOK_ACCESS_TOKEN'),
    langGraphApiUrl: process.env.LANGGRAPH_API_URL || 'http://localhost:8001',
    trendCheckIntervalMs: parseInt(process.env.TREND_CHECK_INTERVAL_MS || '3600000', 10), // 1 hour
    publishSchedule: process.env.PUBLISH_SCHEDULE || '0 9,15,21 * * *', // 3x per day
  };
}

export const EXAMPLE_ENV = `
# Required
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
YOUTUBE_API_KEY=AIza...
YOUTUBE_CLIENT_ID=...
YOUTUBE_CLIENT_SECRET=...
YOUTUBE_REFRESH_TOKEN=...
TIKTOK_ACCESS_TOKEN=...

# Optional
ELEVENLABS_API_KEY=...
TIKTOK_CLIENT_KEY=...
TIKTOK_CLIENT_SECRET=...
LANGGRAPH_API_URL=http://localhost:8001
VIDEO_OUTPUT_DIR=/tmp/content-automation
TREND_CHECK_INTERVAL_MS=3600000
PUBLISH_SCHEDULE=0 9,15,21 * * *
`.trim();
