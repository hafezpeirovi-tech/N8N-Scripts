'use strict';

const assert = require('assert');
const fs = require('fs');

const mainPath = 'C:/Users/1SKY.IR/.n8n/workflows/video-editing-smart.import.json';
const heartbeatPath = 'C:/Users/1SKY.IR/.n8n/workflows/telegram-typing-heartbeat.import.json';
const main = JSON.parse(fs.readFileSync(mainPath, 'utf8'))[0];
const heartbeat = JSON.parse(fs.readFileSync(heartbeatPath, 'utf8'))[0];
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;

const node = (workflow, name) => workflow.nodes.find((item) => item.name === name);
const targets = (workflow, name, output = 0) =>
  (workflow.connections[name]?.main?.[output] || []).map((item) => item.node);

async function run() {
  for (const workflow of [main, heartbeat]) {
    for (const item of workflow.nodes.filter((candidate) => candidate.type === 'n8n-nodes-base.code')) {
      new AsyncFunction(item.parameters.jsCode);
    }
  }

  assert.deepStrictEqual(targets(main, 'Telegram Trigger'), ['Authorize Telegram Owner']);
  assert.deepStrictEqual(targets(main, 'Authorize Telegram Owner'), ['Initialize Processing Heartbeat']);
  assert.deepStrictEqual(
    targets(main, 'Initialize Processing Heartbeat').sort(),
    ['If - PnL Command', 'Start Typing Heartbeat'].sort(),
  );
  assert(!node(main, 'Merge - Preserve Telegram Update'));
  assert(!node(main, 'Telegram - Typing'));
  assert.strictEqual(
    node(main, 'Start Typing Heartbeat').parameters.options.waitForSubWorkflow,
    false,
  );
  assert.strictEqual(node(heartbeat, 'Wait 4 Seconds').parameters.amount, 4);
  assert.deepStrictEqual(targets(heartbeat, 'Wait 4 Seconds'), ['Check Heartbeat Active']);

  const prepareCode = node(main, 'Prepare Video Edit').parameters.jsCode;
  const finalizeCode = node(main, 'Finalize Video Edit').parameters.jsCode;
  for (const code of [prepareCode, finalizeCode]) {
    assert(code.includes('products/HafezStudio/engine/dist/hermes-engine/hermes-engine.exe'));
    assert(code.includes('HERMES_RUNTIME_ROOT'));
    assert(code.includes("'--density', 'max'"));
    assert(!code.includes('Hermes/autocut.py'));
  }
  assert(prepareCode.includes("'prepare', '--cam1'"));
  assert(finalizeCode.includes("'finalize', '--manifest'"));

  const dollarInput = String.fromCharCode(36) + 'input';
  const dollarExecution = String.fromCharCode(36) + 'execution';
  const ownerCode = node(main, 'Authorize Telegram Owner').parameters.jsCode;
  const ownerId = Number(ownerCode.match(/OWNER_ID = ([0-9]+)/)[1]);
  const ownerFn = new AsyncFunction(dollarInput, ownerCode);
  const ownerItem = { json: { message: { from: { id: ownerId }, chat: { id: ownerId, type: 'private' } } } };
  const strangerItem = { json: { message: { from: { id: ownerId + 1 }, chat: { id: ownerId + 1, type: 'private' } } } };
  assert.strictEqual((await ownerFn({ first: () => ownerItem })).length, 1);
  assert.strictEqual((await ownerFn({ first: () => strangerItem })).length, 0);

  const execution = { id: `workflowtest-${Date.now()}` };
  const initializeFn = new AsyncFunction('require', dollarExecution, dollarInput, node(main, 'Initialize Processing Heartbeat').parameters.jsCode);
  const stopFn = new AsyncFunction('require', dollarExecution, dollarInput, node(main, 'Stop Processing Heartbeat').parameters.jsCode);
  const checkFn = new AsyncFunction('require', String.fromCharCode(36), node(heartbeat, 'Check Heartbeat Active').parameters.jsCode);
  let heartbeatFile = '';
  try {
    const initialized = await initializeFn(require, execution, { all: () => [ownerItem] });
    heartbeatFile = initialized[0].json.heartbeat_file;
    assert(fs.existsSync(heartbeatFile));
    const selector = () => ({ first: () => ({ json: initialized[0].json }) });
    assert.strictEqual((await checkFn(require, selector)).length, 1);
    await stopFn(require, execution, { all: () => initialized });
    assert(!fs.existsSync(heartbeatFile));
    assert.strictEqual((await checkFn(require, selector)).length, 0);
  } finally {
    if (heartbeatFile && fs.existsSync(heartbeatFile)) fs.unlinkSync(heartbeatFile);
  }

  const errorFn = new AsyncFunction(dollarInput, dollarExecution, node(main, 'Format Processing Error').parameters.jsCode);
  const fakeSecret = '123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef';
  const formatted = await errorFn(
    { first: () => ({ json: { error: { message: `ENOENT token=${fakeSecret}` } } }) },
    { id: 'error-test-1' },
  );
  assert(formatted[0].json.error_message.includes('Execution'));
  assert(formatted[0].json.error_message.includes('پیشنهاد'));
  assert(!formatted[0].json.error_message.includes(fakeSecret));

  const routedErrors = [
    'AI Agent',
    'Get a file',
    'Parse PnL Command',
    'Get PnL Report',
    'Prepare Video Edit',
    'Finalize Video Edit',
    'Send a text message',
    'Send PnL Report',
    'Send a document',
  ];
  for (const name of routedErrors) {
    assert.strictEqual(node(main, name).onError, 'continueErrorOutput');
    assert.deepStrictEqual(targets(main, name, 1), ['Format Processing Error']);
  }

  console.log('OWNER_PRIVATE=PASS');
  console.log('UNAUTHORIZED=DROP');
  console.log('HEARTBEAT_LIFECYCLE=PASS');
  console.log('ERROR_REDACTION=PASS');
  console.log('WORKFLOW_STRUCTURE=PASS');
  console.log('PORTABLE_ENGINE_ADAPTER=PASS');
}

run().catch((error) => {
  console.error(error);
  process.exit(1);
});
