#!/usr/bin/env node
/**
 * Mineflayer Bridge for crew tasks.
 * 默认 dry-run：解析任务 JSON 并输出动作；apply 模式通过 mineflayer 连接 MC 服务器执行。
 */

const fs = require('fs');
const path = require('path');
const { once } = require('events');

const ALLOWED_ACTIONS = new Set(['setblock', 'clear', 'travel', 'npc_summon']);

function loadJson(filePath) {
  const resolved = path.resolve(filePath);
  const raw = fs.readFileSync(resolved, 'utf-8');
  return JSON.parse(raw);
}

function printUsage() {
  console.log('Usage: node system/taskcrew/bridge.js [--mode dry-run|apply] --task-file <path> [--mc-host 127.0.0.1 --mc-port 25565 --username bot --version 1.20.1 --stay-online]');
  console.log('Legacy: node system/taskcrew/bridge.js --dry-run <task_json>');
}

function validateAction(action) {
  if (!ALLOWED_ACTIONS.has(action.action)) {
    throw new Error(`Unsupported action: ${action.action}`);
  }
  if ((action.action === 'setblock' || action.action === 'travel') && !action.position) {
    throw new Error(`${action.action} requires position`);
  }
  if (action.action === 'npc_summon' && (!action.position || action.position.length !== 3)) {
    throw new Error('npc_summon requires position [x,y,z]');
  }
  if (action.action === 'setblock' && !action.block) {
    throw new Error('setblock requires block');
  }
  if (action.action === 'clear' && !action.region) {
    throw new Error('clear requires region');
  }
  if (action.action === 'clear' && action.region && action.region.length !== 6) {
    throw new Error('clear region must be [x1,y1,z1,x2,y2,z2]');
  }
  if (action.action === 'npc_summon' && !action.name) {
    throw new Error('npc_summon requires name');
  }
}

function parseArgs(argv) {
  // backward compatibility: --dry-run <file>
  if (argv.length === 2 && argv[0] === '--dry-run') {
    return { mode: 'dry-run', taskFile: argv[1] };
  }

  const opts = {
    mode: 'dry-run',
    taskFile: null,
    host: '127.0.0.1',
    port: 25565,
    username: 'crew_bot',
    version: undefined,
      stayOnline: false,
  };

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    switch (arg) {
      case '--mode':
        opts.mode = argv[++i];
        break;
      case '--task-file':
        opts.taskFile = argv[++i];
        break;
      case '--mc-host':
        opts.host = argv[++i];
        break;
      case '--mc-port':
        opts.port = Number(argv[++i]);
        break;
      case '--username':
        opts.username = argv[++i];
        break;
      case '--version':
        opts.version = argv[++i];
        break;
      case '--stay-online':
        opts.stayOnline = true;
        break;
      default:
        console.warn(`Unknown arg: ${arg}`);
    }
  }

  if (!opts.taskFile) {
    throw new Error('task-file is required');
  }
  if (!['dry-run', 'apply'].includes(opts.mode)) {
    throw new Error(`mode must be dry-run or apply, got ${opts.mode}`);
  }
  return opts;
}

function renderDryRun(task) {
  console.log(`[dry-run] task_id=${task.task_id} level_id=${task.level_id} assigned_to=${task.assigned_to}`);
  if (!Array.isArray(task.actions)) {
    throw new Error('actions must be an array');
  }
  task.actions.forEach((action, idx) => {
    validateAction(action);
    const prefix = `[action ${idx + 1}/${task.actions.length}] ${action.action}`;
    if (action.action === 'setblock') {
      console.log(`${prefix} place ${action.block} at ${action.position}`);
    } else if (action.action === 'clear') {
      console.log(`${prefix} clear region ${action.region}`);
    } else if (action.action === 'travel') {
      console.log(`${prefix} travel to ${action.position}`);
    } else if (action.action === 'npc_summon') {
      console.log(`${prefix} summon npc name=${action.name} at ${action.position}`);
    }
    if (action.note) {
      console.log(`  note: ${action.note}`);
    }
  });
  console.log('[dry-run] completed (no commands sent)');
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function applyTask(task, opts) {
  const mineflayer = require('mineflayer');
  const bot = mineflayer.createBot({
    host: opts.host,
    port: opts.port,
    username: opts.username,
    version: opts.version,
  });

  bot.on('error', (err) => {
    console.error(`[bot error] ${err.message}`);
  });

  bot.once('spawn', async () => {
    console.log(`[apply] connected to ${opts.host}:${opts.port} as ${opts.username}`);
    try {
      if (!Array.isArray(task.actions)) {
        throw new Error('actions must be an array');
      }
      for (let idx = 0; idx < task.actions.length; idx++) {
        const action = task.actions[idx];
        validateAction(action);
        const prefix = `[action ${idx + 1}/${task.actions.length}] ${action.action}`;
        if (action.action === 'setblock') {
          const [x, y, z] = action.position;
          console.log(`${prefix} /setblock ${x} ${y} ${z} ${action.block}`);
          bot.chat(`/setblock ${x} ${y} ${z} ${action.block}`);
        } else if (action.action === 'clear') {
          const [x1, y1, z1, x2, y2, z2] = action.region;
          console.log(`${prefix} /fill ${x1} ${y1} ${z1} ${x2} ${y2} ${z2} air`);
          bot.chat(`/fill ${x1} ${y1} ${z1} ${x2} ${y2} ${z2} air`);
        } else if (action.action === 'travel') {
          const [x, y, z] = action.position;
          console.log(`${prefix} /tp ${x} ${y} ${z}`);
          bot.chat(`/tp ${x} ${y} ${z}`);
        } else if (action.action === 'npc_summon') {
          const [x, y, z] = action.position;
          console.log(`${prefix} /summon villager ${x} ${y} ${z} {CustomName:\"\\\"${action.name}\\\"\"}`);
          bot.chat(`/summon villager ${x} ${y} ${z} {CustomName:\"\\\"${action.name}\\\"\"}`);
        }
        await sleep(300);
      }
      console.log('[apply] completed');
      if (opts.stayOnline) {
        console.log('[apply] stay-online enabled; bot will remain connected. Ctrl+C 结束。');
        return;
      }
      bot.end();
    } catch (err) {
      console.error(`[apply error] ${err.message}`);
      bot.end();
      process.exitCode = 1;
    }
  });

  await once(bot, 'end');
}

async function run() {
  const argv = process.argv.slice(2);
  if (argv.length === 0) {
    printUsage();
    process.exit(1);
  }

  const opts = parseArgs(argv);
  const task = loadJson(opts.taskFile);

  if (opts.mode === 'dry-run') {
    renderDryRun(task);
    return;
  }

  console.log(`[apply] task_id=${task.task_id} level_id=${task.level_id} assigned_to=${task.assigned_to}`);
  await applyTask(task, opts);
}

if (require.main === module) {
  run().catch((err) => {
    console.error(`[error] ${err.message}`);
    process.exit(1);
  });
}

module.exports = { run, validateAction, loadJson, parseArgs, renderDryRun, applyTask };
