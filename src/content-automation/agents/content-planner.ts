import Anthropic from '@anthropic-ai/sdk';
import { randomUUID } from 'crypto';
import type { TrendData, ContentPlan, AgentConfig, Platform } from '../types/index.js';

export class ContentPlannerAgent {
  private client: Anthropic;

  constructor(private config: AgentConfig) {
    this.client = new Anthropic({ apiKey: config.anthropicApiKey });
  }

  async generatePlan(trend: TrendData, platforms: Platform[]): Promise<ContentPlan> {
    const message = await this.client.messages.create({
      model: 'claude-sonnet-4-6',
      max_tokens: 2048,
      messages: [{
        role: 'user',
        content: `You are an expert YouTube/TikTok content creator. Create a viral short-form video plan for this trend.

Trend: "${trend.keyword}"
Related topics: ${trend.relatedTopics.join(', ')}
Target platforms: ${platforms.join(', ')}

Generate a complete content plan as JSON with these exact fields:
{
  "title": "Catchy, SEO-optimized title (max 100 chars)",
  "description": "Compelling description with keywords (max 500 chars)",
  "tags": ["tag1", "tag2", ... up to 15 tags],
  "script": "Full narration script for ~60 second video, divided into 5-7 scenes. Each scene: [SCENE X]: text",
  "estimatedDuration": 60
}

Make it engaging, informative, and optimized for the algorithm. Use hooks, curiosity gaps, and CTAs.`,
      }],
    });

    const responseText = message.content[0].type === 'text' ? message.content[0].text : '';
    const jsonMatch = responseText.match(/\{[\s\S]*\}/);
    if (!jsonMatch) throw new Error('Failed to parse content plan from Claude response');

    const planData = JSON.parse(jsonMatch[0]) as {
      title: string;
      description: string;
      tags: string[];
      script: string;
      estimatedDuration: number;
    };

    return {
      id: randomUUID(),
      trend,
      title: planData.title,
      description: planData.description,
      tags: planData.tags,
      script: planData.script,
      targetPlatforms: platforms,
      estimatedDuration: planData.estimatedDuration || 60,
      createdAt: new Date(),
    };
  }

  async generateBatch(trends: TrendData[], platforms: Platform[]): Promise<ContentPlan[]> {
    console.log(`[ContentPlanner] Generating plans for ${trends.length} trends...`);

    const plans = await Promise.all(
      trends.map((trend) => this.generatePlan(trend, platforms).catch((err) => {
        console.error(`[ContentPlanner] Failed for "${trend.keyword}":`, err.message);
        return null;
      }))
    );

    const validPlans = plans.filter((p): p is ContentPlan => p !== null);
    console.log(`[ContentPlanner] Generated ${validPlans.length} content plans`);
    return validPlans;
  }
}
