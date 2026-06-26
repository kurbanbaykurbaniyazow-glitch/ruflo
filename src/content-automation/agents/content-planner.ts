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
        content: `You are a top-tier YouTube Shorts scriptwriter. Write a viral 60-second script.

Topic: "${trend.keyword}"
Video title: "${title}"

Format exactly like this — 6 scenes, each starting with [SCENE N]:

[SCENE 1]: Hook — shocking stat or question (5-7 words spoken)
[SCENE 2]: Problem setup — why viewers should care
[SCENE 3]: The reveal or solution
[SCENE 4]: Proof — stats, examples, social proof
[SCENE 5]: Deeper insight — what most people miss
[SCENE 6]: CTA — follow, comment, share

Rules:
- Each scene: 1-3 sentences max (it's 10 seconds per scene)
- Start scene 1 with a HOOK that stops the scroll
- Use "you" language — speak directly to viewer
- End with a strong reason to follow the account`,
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
