import Anthropic from '@anthropic-ai/sdk';
import type { TrendData, AgentConfig } from '../types/index.js';

const YOUTUBE_TRENDING_URL = 'https://www.googleapis.com/youtube/v3/videos';
const GOOGLE_TRENDS_URL = 'https://trends.google.com/trends/api/dailytrends';

export class TrendScoutAgent {
  private client: Anthropic;
  private config: AgentConfig;

  constructor(config: AgentConfig) {
    this.config = config;
    this.client = new Anthropic({ apiKey: config.anthropicApiKey });
  }

  async fetchYouTubeTrends(): Promise<TrendData[]> {
    const apiKey = process.env.YOUTUBE_API_KEY;
    if (!apiKey) throw new Error('YOUTUBE_API_KEY not set');

    const params = new URLSearchParams({
      part: 'snippet,statistics',
      chart: 'mostPopular',
      maxResults: '20',
      regionCode: 'US',
      key: apiKey,
    });

    const response = await fetch(`${YOUTUBE_TRENDING_URL}?${params}`);
    if (!response.ok) throw new Error(`YouTube API error: ${response.status}`);

    const data = await response.json() as { items: Array<{
      snippet: { title: string; categoryId: string; tags?: string[] };
      statistics: { viewCount: string };
    }> };

    return data.items.map((item) => ({
      keyword: item.snippet.title,
      score: parseInt(item.statistics.viewCount || '0', 10),
      category: item.snippet.categoryId,
      relatedTopics: item.snippet.tags?.slice(0, 5) || [],
      platform: 'youtube' as const,
      fetchedAt: new Date(),
    }));
  }

  async fetchGoogleTrends(geo = 'US'): Promise<TrendData[]> {
    const params = new URLSearchParams({ hl: 'en-US', tz: '-480', geo, ns: '15' });
    const response = await fetch(`${GOOGLE_TRENDS_URL}?${params}`);
    if (!response.ok) throw new Error(`Google Trends error: ${response.status}`);

    const text = await response.text();
    // Google Trends returns JSON with )]}' prefix
    const json = JSON.parse(text.replace(/^\)\]\}',?/, '')) as {
      default: { trendingSearchesDays: Array<{
        trendingSearches: Array<{
          title: { query: string };
          formattedTraffic: string;
          relatedQueries: Array<{ query: string }>;
        }>;
      }> };
    };

    const searches = json.default.trendingSearchesDays[0]?.trendingSearches || [];
    return searches.slice(0, 10).map((item) => ({
      keyword: item.title.query,
      score: parseInt(item.formattedTraffic.replace(/[^0-9]/g, ''), 10) || 0,
      category: 'trending',
      relatedTopics: item.relatedQueries.map((q) => q.query).slice(0, 5),
      platform: 'google' as const,
      fetchedAt: new Date(),
    }));
  }

  async rankAndFilterTrends(trends: TrendData[]): Promise<TrendData[]> {
    const trendList = trends.map((t) => `- "${t.keyword}" (score: ${t.score})`).join('\n');

    const message = await this.client.messages.create({
      model: 'claude-haiku-4-5-20251001',
      max_tokens: 1024,
      messages: [{
        role: 'user',
        content: `You are a viral content strategist. Rank these trending topics by their potential for short-form video content (YouTube Shorts / TikTok). Consider: entertainment value, broad appeal, easy to explain visually, monetization-friendly.

Trends:
${trendList}

Return ONLY a JSON array of the top 5 keywords in order of potential, like: ["keyword1", "keyword2", ...]`,
      }],
    });

    const responseText = message.content[0].type === 'text' ? message.content[0].text : '';
    const jsonMatch = responseText.match(/\[[\s\S]*\]/);
    if (!jsonMatch) return trends.slice(0, 5);

    const rankedKeywords: string[] = JSON.parse(jsonMatch[0]);
    const ranked = rankedKeywords
      .map((kw) => trends.find((t) => t.keyword === kw))
      .filter((t): t is TrendData => t !== undefined);

    return ranked.length > 0 ? ranked : trends.slice(0, 5);
  }

  async run(): Promise<TrendData[]> {
    console.log('[TrendScout] Fetching trends...');

    const [youtubeTrends, googleTrends] = await Promise.allSettled([
      this.fetchYouTubeTrends(),
      this.fetchGoogleTrends(),
    ]);

    const allTrends: TrendData[] = [];
    if (youtubeTrends.status === 'fulfilled') allTrends.push(...youtubeTrends.value);
    if (googleTrends.status === 'fulfilled') allTrends.push(...googleTrends.value);

    if (allTrends.length === 0) {
      console.warn('[TrendScout] No trends fetched, using fallback');
      return this.getFallbackTrends();
    }

    const ranked = await this.rankAndFilterTrends(allTrends);
    console.log(`[TrendScout] Found ${ranked.length} top trends`);
    return ranked;
  }

  private getFallbackTrends(): TrendData[] {
    return [
      { keyword: 'AI tools 2026', score: 1000000, category: 'Tech', relatedTopics: ['ChatGPT', 'Claude', 'automation'], platform: 'youtube', fetchedAt: new Date() },
      { keyword: 'Money making tips', score: 800000, category: 'Finance', relatedTopics: ['passive income', 'investing'], platform: 'youtube', fetchedAt: new Date() },
    ];
  }
}
