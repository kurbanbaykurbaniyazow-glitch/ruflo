import { randomUUID } from 'crypto';
import { TrendScoutAgent } from './agents/trend-scout.js';
import { ContentPlannerAgent } from './agents/content-planner.js';
import { YouTubePublisherAgent } from './agents/publisher-youtube.js';
import { TikTokPublisherAgent } from './agents/publisher-tiktok.js';
import { AnalyticsMonitorAgent } from './agents/analytics-monitor.js';
import type {
  AgentConfig, ContentPlan, VideoAsset, PublishResult, WorkflowState,
} from './types/index.js';

interface LangGraphStatusResponse {
  content_id: string;
  status: string;
  video_path: string | null;
  thumbnail_path: string | null;
  error: string | null;
}

export class ContentAutomationOrchestrator {
  private trendScout: TrendScoutAgent;
  private contentPlanner: ContentPlannerAgent;
  private youtubePublisher: YouTubePublisherAgent;
  private tiktokPublisher: TikTokPublisherAgent;
  private analyticsMonitor: AnalyticsMonitorAgent;
  private state: WorkflowState;

  constructor(private config: AgentConfig) {
    this.trendScout = new TrendScoutAgent(config);
    this.contentPlanner = new ContentPlannerAgent(config);
    this.youtubePublisher = new YouTubePublisherAgent(
      config.youtubeClientId,
      config.youtubeClientSecret,
      config.youtubeRefreshToken,
    );
    this.tiktokPublisher = new TikTokPublisherAgent(config.tiktokAccessToken);
    this.analyticsMonitor = new AnalyticsMonitorAgent(config);

    this.state = {
      trends: [], contentPlans: [], videoAssets: [],
      publishResults: [], analytics: [], errors: [],
    };
  }

  // ─── Phase 1: Discover Trends ────────────────────────────────────────────

  async discoverTrends(): Promise<void> {
    console.log('\n[Orchestrator] Phase 1: Discovering trends...');
    try {
      this.state.trends = await this.trendScout.run();
      console.log(`[Orchestrator] Found ${this.state.trends.length} trends`);
    } catch (err) {
      this.logError('trend-scout', err);
    }
  }

  // ─── Phase 2: Plan Content ────────────────────────────────────────────────

  async planContent(): Promise<void> {
    console.log('\n[Orchestrator] Phase 2: Planning content...');
    if (this.state.trends.length === 0) {
      console.warn('[Orchestrator] No trends available, skipping content planning');
      return;
    }

    try {
      this.state.contentPlans = await this.contentPlanner.generateBatch(
        this.state.trends,
        ['youtube', 'tiktok'],
      );
      console.log(`[Orchestrator] Created ${this.state.contentPlans.length} content plans`);
    } catch (err) {
      this.logError('content-planner', err);
    }
  }

  // ─── Phase 3: Generate Videos via LangGraph ───────────────────────────────

  async generateVideos(): Promise<void> {
    console.log('\n[Orchestrator] Phase 3: Generating videos via LangGraph...');

    await Promise.all(
      this.state.contentPlans.map((plan) => this.generateVideo(plan))
    );

    const ready = this.state.videoAssets.filter((a) => a.status === 'ready');
    console.log(`[Orchestrator] ${ready.length}/${this.state.contentPlans.length} videos ready`);
  }

  private async generateVideo(plan: ContentPlan): Promise<void> {
    const asset: VideoAsset = {
      id: randomUUID(),
      contentPlanId: plan.id,
      slides: [],
      audioPath: '',
      status: 'generating',
      createdAt: new Date(),
    };
    this.state.videoAssets.push(asset);

    try {
      // Trigger LangGraph pipeline
      const initResponse = await fetch(`${this.config.langGraphApiUrl}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content_id: plan.id,
          title: plan.title,
          script: plan.script,
        }),
      });

      if (!initResponse.ok) throw new Error(`LangGraph API error: ${initResponse.status}`);

      // Poll until video is ready
      await this.pollVideoStatus(plan.id, asset);
    } catch (err) {
      asset.status = 'failed';
      this.logError('video-generator', err);
    }
  }

  private async pollVideoStatus(contentId: string, asset: VideoAsset, maxWait = 300000): Promise<void> {
    const start = Date.now();
    const interval = 5000;

    while (Date.now() - start < maxWait) {
      await new Promise((r) => setTimeout(r, interval));

      try {
        const response = await fetch(`${this.config.langGraphApiUrl}/status/${contentId}`);
        const data = await response.json() as LangGraphStatusResponse;

        if (data.status === 'ready') {
          asset.videoPath = data.video_path || undefined;
          asset.thumbnailPath = data.thumbnail_path || undefined;
          asset.status = 'ready';
          console.log(`[Orchestrator] Video ready for plan ${contentId}`);
          return;
        }

        if (data.status === 'failed') {
          throw new Error(data.error || 'Video generation failed');
        }
      } catch (err) {
        console.warn(`[Orchestrator] Poll error for ${contentId}:`, (err as Error).message);
      }
    }

    throw new Error(`Video generation timeout for ${contentId}`);
  }

  // ─── Phase 4: Publish ────────────────────────────────────────────────────

  async publishVideos(): Promise<void> {
    console.log('\n[Orchestrator] Phase 4: Publishing videos...');
    const readyAssets = this.state.videoAssets.filter((a) => a.status === 'ready');

    await Promise.all(
      readyAssets.map((asset) => this.publishAsset(asset))
    );

    console.log(`[Orchestrator] Published ${this.state.publishResults.length} videos`);
  }

  private async publishAsset(asset: VideoAsset): Promise<void> {
    const plan = this.state.contentPlans.find((p) => p.id === asset.contentPlanId);
    if (!plan) return;

    await Promise.allSettled(
      plan.targetPlatforms.map(async (platform) => {
        try {
          let result: PublishResult;
          if (platform === 'youtube') {
            result = await this.youtubePublisher.upload(plan, asset);
          } else if (platform === 'tiktok') {
            result = await this.tiktokPublisher.upload(plan, asset);
          } else {
            return;
          }
          this.state.publishResults.push(result);
          console.log(`[Orchestrator] Published to ${platform}: ${result.url}`);
        } catch (err) {
          this.logError(`publisher-${platform}`, err);
        }
      })
    );
  }

  // ─── Phase 5: Collect Analytics ─────────────────────────────────────────

  async collectAnalytics(): Promise<void> {
    console.log('\n[Orchestrator] Phase 5: Collecting analytics...');
    if (this.state.publishResults.length === 0) return;

    try {
      // Wait a bit for platforms to process
      await new Promise((r) => setTimeout(r, 10000));
      this.state.analytics = await this.analyticsMonitor.monitorAll(this.state.publishResults);
    } catch (err) {
      this.logError('analytics-monitor', err);
    }
  }

  // ─── Full Run ─────────────────────────────────────────────────────────────

  async run(): Promise<WorkflowState> {
    console.log('\n=== Content Automation Workflow Starting ===\n');
    const start = Date.now();

    await this.discoverTrends();
    await this.planContent();
    await this.generateVideos();
    await this.publishVideos();
    await this.collectAnalytics();

    const elapsed = ((Date.now() - start) / 1000).toFixed(1);
    console.log(`\n=== Workflow Complete in ${elapsed}s ===`);
    console.log(`  Trends: ${this.state.trends.length}`);
    console.log(`  Plans: ${this.state.contentPlans.length}`);
    console.log(`  Videos: ${this.state.videoAssets.filter((a) => a.status === 'ready').length}`);
    console.log(`  Published: ${this.state.publishResults.length}`);
    if (this.state.errors.length > 0) {
      console.log(`  Errors: ${this.state.errors.length}`);
    }

    return this.state;
  }

  getState(): WorkflowState {
    return this.state;
  }

  private logError(agent: string, err: unknown): void {
    const message = err instanceof Error ? err.message : String(err);
    console.error(`[${agent}] Error:`, message);
    this.state.errors.push({ agent, error: message, timestamp: new Date() });
  }
}
