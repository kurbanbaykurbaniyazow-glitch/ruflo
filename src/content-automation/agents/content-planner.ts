import Anthropic from '@anthropic-ai/sdk';
import { randomUUID } from 'crypto';
import type { TrendData, ContentPlan, AgentConfig, Platform } from '../types/index.js';

// Cost-optimised: Haiku for analysis, Sonnet only for final script
const MODEL_FAST = 'claude-haiku-4-5-20251001';   // $0.00025/1K in
const MODEL_QUALITY = 'claude-sonnet-4-6';          // $0.003/1K in

export class ContentPlannerAgent {
  private client: Anthropic;

  constructor(private config: AgentConfig) {
    this.client = new Anthropic({ apiKey: config.anthropicApiKey });
  }

  // Step 1 (Haiku — cheap): score and filter trends
  private async scoreTrends(trends: TrendData[]): Promise<TrendData[]> {
    const list = trends.map((t, i) => `${i}. "${t.keyword}" (views: ${t.score})`).join('\n');

    const msg = await this.client.messages.create({
      model: MODEL_FAST,
      max_tokens: 256,
      messages: [{
        role: 'user',
        content: `Rate these trends 0-10 for short-form video potential (broad appeal, visual, monetization-safe).
Return ONLY a JSON array of indices in order of score, best first. Max 3 items.

${list}

Format: [0, 3, 1]`,
      }],
    });

    const text = msg.content[0].type === 'text' ? msg.content[0].text : '';
    const match = text.match(/\[[\d,\s]+\]/);
    if (!match) return trends.slice(0, 3);

    const indices: number[] = JSON.parse(match[0]);
    return indices.slice(0, 3).map((i) => trends[i]).filter(Boolean);
  }

  // Step 2 (Haiku — cheap): generate title, description, tags
  private async generateMeta(trend: TrendData, platforms: Platform[]): Promise<{
    title: string; description: string; tags: string[];
  }> {
    const msg = await this.client.messages.create({
      model: MODEL_FAST,
      max_tokens: 512,
      messages: [{
        role: 'user',
        content: `Create metadata for a short-form video about: "${trend.keyword}"
Platforms: ${platforms.join(', ')}

Return ONLY valid JSON:
{
  "title": "hook-driven title under 90 chars",
  "description": "2-3 sentence description with keywords, max 400 chars",
  "tags": ["tag1","tag2",...] (10-12 tags)
}`,
      }],
    });

    const text = msg.content[0].type === 'text' ? msg.content[0].text : '';
    const match = text.match(/\{[\s\S]*\}/);
    if (!match) return { title: trend.keyword, description: '', tags: trend.relatedTopics };
    return JSON.parse(match[0]);
  }

  // Step 3 (Sonnet — quality): write the actual video script
  private async writeScript(trend: TrendData, title: string): Promise<string> {
    const msg = await this.client.messages.create({
      model: MODEL_QUALITY,
      max_tokens: 1500,
      messages: [{
        role: 'user',
        content: `You are a viral TikTok/YouTube Shorts scriptwriter for 2026. Write a 20-second script that hooks in 1.3 seconds.

Topic: "${trend.keyword}"
Title: "${title}"

Write EXACTLY 6 scenes. Each scene = what the narrator SAYS OUT LOUD (not descriptions).

Format:
[SCENE 1]: 5-8 words MAX — shocking hook, number or question
[SCENE 2]: 10-15 words — the painful problem or surprising fact
[SCENE 3]: 10-15 words — the secret/reveal (start with "But here's the truth:" or similar)
[SCENE 4]: 10-15 words — real proof: specific number, example, or name
[SCENE 5]: 10-15 words — the insight nobody talks about
[SCENE 6]: 8-12 words — CTA with a REASON ("Follow us — we post this daily")

Rules (CRITICAL):
- Scene 1 MUST be a jaw-drop: use a shocking number, "You're doing X wrong", or a question
- Speak directly: "you", "your", never "people" or "they"
- ZERO filler words: no "basically", "actually", "so", "well"
- Each sentence: short, punchy, spoken word — like you're whispering a secret
- Include ONE real specific example or statistic with a source name (even approximate)
- Scene 6: give a compelling reason to follow, not just "follow me"`,
      }],
    });

    return msg.content[0].type === 'text' ? msg.content[0].text : '';
  }

  async generatePlan(trend: TrendData, platforms: Platform[]): Promise<ContentPlan> {
    // Run meta generation while script is writing
    const [meta, script] = await Promise.all([
      this.generateMeta(trend, platforms),
      this.writeScript(trend, trend.keyword),
    ]);

    return {
      id: randomUUID(),
      trend,
      title: meta.title,
      description: meta.description,
      tags: meta.tags,
      script,
      targetPlatforms: platforms,
      estimatedDuration: 60,
      createdAt: new Date(),
    };
  }

  async generateBatch(trends: TrendData[], platforms: Platform[]): Promise<ContentPlan[]> {
    console.log(`[ContentPlanner] Scoring ${trends.length} trends with Haiku...`);
    const top = await this.scoreTrends(trends);
    console.log(`[ContentPlanner] Top trends: ${top.map((t) => t.keyword).join(', ')}`);

    const plans = await Promise.all(
      top.map((trend) =>
        this.generatePlan(trend, platforms).catch((err) => {
          console.error(`[ContentPlanner] Failed for "${trend.keyword}":`, err.message);
          return null;
        })
      )
    );

    return plans.filter((p): p is ContentPlan => p !== null);
  }
}
