#!/usr/bin/env node
/**
 * Autonomous AI Content Automation System
 * Trend Scout → Content Planner → LangGraph Video Pipeline → YouTube/TikTok Publisher
 *
 * Usage:
 *   npx tsx src/content-automation/index.ts          # Run once
 *   npx tsx src/content-automation/index.ts --daemon  # Run on schedule
 */
import { ContentAutomationOrchestrator } from './orchestrator.js';
import { loadConfig, EXAMPLE_ENV } from './config/index.js';

async function main() {
  const args = process.argv.slice(2);
  const isDaemon = args.includes('--daemon');

  let config;
  try {
    config = loadConfig();
  } catch (err) {
    console.error('Configuration error:', (err as Error).message);
    console.error('\nRequired environment variables:\n');
    console.error(EXAMPLE_ENV);
    process.exit(1);
  }

  const orchestrator = new ContentAutomationOrchestrator(config);

  if (isDaemon) {
    console.log('[Main] Running in daemon mode, interval:', config.trendCheckIntervalMs, 'ms');
    // Run immediately, then on interval
    await runCycle(orchestrator);
    setInterval(() => runCycle(orchestrator), config.trendCheckIntervalMs);
  } else {
    await runCycle(orchestrator);
  }
}

async function runCycle(orchestrator: ContentAutomationOrchestrator): Promise<void> {
  try {
    const state = await orchestrator.run();
    if (state.errors.length > 0) {
      console.warn(`[Main] Completed with ${state.errors.length} errors`);
    }
  } catch (err) {
    console.error('[Main] Fatal error:', (err as Error).message);
  }
}

main().catch(console.error);
