from __future__ import annotations

import json
import uuid
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
SOURCE = WORKSPACE / "backups" / "video-editing" / "20260825-smart-edit" / "workflow.before.json"
OUTPUT = WORKSPACE / "workflows" / "video-editing-smart.import.json"
HEARTBEAT_OUTPUT = WORKSPACE / "workflows" / "telegram-typing-heartbeat.import.json"
HEARTBEAT_WORKFLOW_ID = "1f9f6680-65cd-4ee8-a733-9e7e2e0a4b11"


PREPARE_CODE = r"""const { execFile } = require('child_process');
const fs = require('fs');

const text = String($json.message?.text || '');
const lines = text.split('\n').map((line) => line.trim()).filter(Boolean);
if (lines.length < 2) {
  throw new Error('لطفاً مسیر هر دو ویدیو را در دو خط جداگانه بفرستید.');
}

const cleanPath = (value) => value.replace(/^["']|["']$/g, '');
const cam1 = cleanPath(lines[0]);
const cam2 = cleanPath(lines[1]);
const enginePath = 'C:/Users/1SKY.IR/.n8n/products/HafezStudio/engine/dist/hermes-engine/hermes-engine.exe';
const studioRoot = 'C:/Users/1SKY.IR/.n8n/products/HafezStudio';
const outputRoot = 'C:/Users/1SKY.IR/.n8n/hermes_output';

function runEngine(args) {
  return new Promise((resolve) => {
    execFile(
      enginePath,
      args,
      {
        windowsHide: true,
        maxBuffer: 1024 * 1024 * 30,
        env: {
          ...process.env,
          PYTHONUTF8: '1',
          HERMES_STUDIO_ROOT: studioRoot,
          HERMES_RUNTIME_ROOT: `${studioRoot}/runtime`,
        },
      },
      (error, stdout, stderr) => resolve({ error, stdout, stderr }),
    );
  });
}

const result = await runEngine([
  'prepare', '--cam1', cam1, '--cam2', cam2, '--output', outputRoot,
  '--style', 'signal-os', '--density', 'max', '--language', 'fa-en',
]);
const manifestMatch = result.stdout.match(/MANIFEST_PATH:\s*(.*\.edit\.json)/);
const reviewMatch = result.stdout.match(/REVIEW_PATH:\s*(.*\.review\.txt)/);
const tasksMatch = result.stdout.match(/REVIEW_TASKS_PATH:\s*(.*\.review-tasks\.json)/);
const manifestPath = manifestMatch ? manifestMatch[1].trim() : '';
const reviewPath = reviewMatch ? reviewMatch[1].trim() : '';
const tasksPath = tasksMatch ? tasksMatch[1].trim() : '';

if (
  result.error || !manifestPath || !reviewPath || !tasksPath ||
  !fs.existsSync(manifestPath) || !fs.existsSync(reviewPath) || !fs.existsSync(tasksPath)
) {
  throw new Error(
    'مرحله آماده‌سازی تدوین شکست خورد.\nSTDOUT:\n' +
    result.stdout.slice(-4000) +
    '\nSTDERR:\n' +
    result.stderr.slice(-4000),
  );
}

const taskEnvelope = JSON.parse(fs.readFileSync(tasksPath, 'utf8'));
const tasks = Array.isArray(taskEnvelope.tasks) ? taskEnvelope.tasks : [];
if (!tasks.length) throw new Error('هیچ وظیفه AI برای Transcript ساخته نشد.');

return tasks.map((task) => ({
  json: {
    manifest_path: manifestPath,
    review_path: reviewPath,
    review_tasks_path: tasksPath,
    review_protocol: taskEnvelope.protocol || 'hermes-ai-tasks-v1',
    task_id: String(task.task_id || ''),
    task_type: String(task.task_type || ''),
    review_prompt: String(task.prompt || ''),
    segment_ids: Array.isArray(task.segment_ids) ? task.segment_ids : [],
    prepare_log: result.stdout.slice(-4000),
  },
}));"""


FINALIZE_CODE = r"""const { execFile } = require('child_process');
const fs = require('fs');
const path = require('path');

const preparedItems = $('Prepare Video Edit').all().map((item) => item.json);
const prepared = preparedItems[0] || {};
const manifestPath = String(prepared.manifest_path || '');
if (!manifestPath || !fs.existsSync(manifestPath)) {
  throw new Error('Manifest تدوین پیدا نشد.');
}

const responseItems = $input.all();
function responseText(value) {
  if (typeof value?.text === 'string') return value.text;
  if (typeof value?.output === 'string') return value.output;
  if (typeof value?.response === 'string') return value.response;
  try { return JSON.stringify(value || {}); } catch (_) { return String(value || ''); }
}
const reviewPayload = JSON.stringify({
  protocol: 'hermes-ai-tasks-v1',
  tasks: preparedItems.map((task, index) => ({
    task_id: String(task.task_id || `task-${index + 1}`),
    task_type: String(task.task_type || ''),
    response: responseText(responseItems[index]?.json),
  })),
}, null, 2);
const reviewResultPath = manifestPath.replace(/\.edit\.json$/i, '.gemini.json');
fs.writeFileSync(reviewResultPath, reviewPayload || '{}', 'utf8');

const enginePath = 'C:/Users/1SKY.IR/.n8n/products/HafezStudio/engine/dist/hermes-engine/hermes-engine.exe';
const studioRoot = 'C:/Users/1SKY.IR/.n8n/products/HafezStudio';
function runEngine(args) {
  return new Promise((resolve) => {
    execFile(
      enginePath,
      args,
      {
        windowsHide: true,
        maxBuffer: 1024 * 1024 * 30,
        env: {
          ...process.env,
          PYTHONUTF8: '1',
          HERMES_STUDIO_ROOT: studioRoot,
          HERMES_RUNTIME_ROOT: `${studioRoot}/runtime`,
        },
      },
      (error, stdout, stderr) => resolve({ error, stdout, stderr }),
    );
  });
}

const result = await runEngine([
  'finalize', '--manifest', manifestPath, '--review', reviewResultPath,
  '--style', 'signal-os', '--density', 'max', '--language', 'fa-en',
]);
const xmlMatch = result.stdout.match(/فایل پریمیر ساخته شد:\s*(.*\.xml)/);
const safeSrtMatch = result.stdout.match(/فایل زیرنویس Safe ساخته شد:\s*(.*\.srt)/);
const tightSrtMatch = result.stdout.match(/فایل زیرنویس Tight ساخته شد:\s*(.*\.srt)/);
const youtubeMatch = result.stdout.match(/بسته یوتیوب ساخته شد:\s*(.*\.md)/);
const editNotesMatch = result.stdout.match(/راهنمای تدوین ساخته شد:\s*(.*\.md)/);
const professionalPlanMatch = result.stdout.match(/برنامه حرفه‌ای Premiere ساخته شد:\s*(.*\.json)/);
const xmlPath = xmlMatch ? xmlMatch[1].trim() : '';
const safeSrtPath = safeSrtMatch ? safeSrtMatch[1].trim() : '';
const tightSrtPath = tightSrtMatch ? tightSrtMatch[1].trim() : '';
const youtubePath = youtubeMatch ? youtubeMatch[1].trim() : '';
const editNotesPath = editNotesMatch ? editNotesMatch[1].trim() : '';
const professionalPlanPath = professionalPlanMatch ? professionalPlanMatch[1].trim() : '';

if (result.error || !xmlPath || !safeSrtPath || !tightSrtPath || !fs.existsSync(xmlPath)) {
  throw new Error(
    'مرحله نهایی تدوین شکست خورد.\nSTDOUT:\n' +
    result.stdout.slice(-4000) +
    '\nSTDERR:\n' +
    result.stderr.slice(-4000),
  );
}

const outputs = [];
function addOutput(filePath, type, mimeType) {
  if (!filePath || !fs.existsSync(filePath)) return;
  outputs.push({
    json: { status: 'Done', type, output: result.stdout },
    binary: {
      data: {
        data: fs.readFileSync(filePath).toString('base64'),
        mimeType,
        fileName: path.basename(filePath),
      },
    },
  });
}
addOutput(xmlPath, 'XML_SAFE_TIGHT', 'text/xml');
addOutput(safeSrtPath, 'SRT_SAFE', 'application/x-subrip');
addOutput(tightSrtPath, 'SRT_TIGHT', 'application/x-subrip');
addOutput(youtubePath, 'YOUTUBE_PACKAGE', 'text/markdown');
addOutput(editNotesPath, 'EDIT_NOTES', 'text/markdown');
addOutput(professionalPlanPath, 'PREMIERE_PROFESSIONAL_PLAN', 'application/json');
return outputs;"""


OWNER_AUTH_CODE = r"""const OWNER_ID = 1140471;
const item = $input.first();
const message = item?.json?.message;
const fromId = Number(message?.from?.id);
const chatId = Number(message?.chat?.id);
const chatType = String(message?.chat?.type || '');

const isOwnerPrivateChat =
  Number.isSafeInteger(fromId) &&
  Number.isSafeInteger(chatId) &&
  fromId === OWNER_ID &&
  chatId === OWNER_ID &&
  chatType === 'private';

// Unauthorized updates are deliberately dropped without a reply or typing action.
if (!isOwnerPrivateChat) {
  return [];
}

return [item];"""


INITIALIZE_PROCESSING_CODE = r"""const fs = require('fs');
const path = require('path');

const heartbeatDir = 'C:/Users/1SKY.IR/.n8n/hermes_output/typing-heartbeats';
fs.mkdirSync(heartbeatDir, { recursive: true });

// Remove abandoned markers from a previous crash. A normal execution removes
// its own marker as soon as the final Telegram result (or error) is sent.
const staleBefore = Date.now() - 12 * 60 * 60 * 1000;
for (const name of fs.readdirSync(heartbeatDir)) {
  if (!/^typing-[A-Za-z0-9_-]+\.lock$/.test(name)) continue;
  const candidate = path.join(heartbeatDir, name);
  try {
    if (fs.statSync(candidate).mtimeMs < staleBefore) fs.unlinkSync(candidate);
  } catch (_) {}
}

const executionId = String($execution.id).replace(/[^A-Za-z0-9_-]/g, '');
if (!executionId) throw new Error('Execution ID برای heartbeat معتبر نیست.');
const heartbeatFile = path.join(heartbeatDir, `typing-${executionId}.lock`);
fs.writeFileSync(
  heartbeatFile,
  JSON.stringify({ execution_id: executionId, created_at: new Date().toISOString() }),
  'utf8',
);

return $input.all().map((item) => ({
  ...item,
  json: {
    ...item.json,
    heartbeat_file: heartbeatFile,
    root_execution_id: executionId,
  },
}));"""


STOP_PROCESSING_CODE = r"""const fs = require('fs');
const path = require('path');
const heartbeatDir = 'C:/Users/1SKY.IR/.n8n/hermes_output/typing-heartbeats';
const executionId = String($execution.id).replace(/[^A-Za-z0-9_-]/g, '');
const heartbeatFile = path.join(heartbeatDir, `typing-${executionId}.lock`);
try {
  if (fs.existsSync(heartbeatFile)) fs.unlinkSync(heartbeatFile);
} catch (_) {}
return $input.all();"""


FORMAT_ERROR_CODE = r"""const source = $input.first()?.json ?? {};
const error = source.error ?? source;

function stringify(value) {
  if (typeof value === 'string') return value;
  try { return JSON.stringify(value); } catch (_) { return String(value ?? ''); }
}

let raw = [
  error?.message,
  error?.description,
  error?.cause?.message,
  source?.message,
  stringify(error),
].filter(Boolean).join('\n');

raw = raw
  .replace(/\b\d{6,12}:[A-Za-z0-9_-]{20,}\b/g, '[TELEGRAM_TOKEN_REDACTED]')
  .replace(/(authorization\s*[:=]\s*bearer\s+)[^\s,;]+/gi, '$1[REDACTED]')
  .replace(/((?:api[_ -]?key|token|password|secret)\s*[:=]\s*)[^\s,;]+/gi, '$1[REDACTED]')
  .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, ' ')
  .trim();
if (!raw) raw = 'جزئیات فنی خطا از نود دریافت نشد.';
if (raw.length > 1100) raw = '…' + raw.slice(-1100);

const lower = raw.toLowerCase();
let stage = 'پردازش عمومی';
let suggestion = 'یک‌بار دیگر تلاش کن؛ اگر تکرار شد شناسه اجرا را برای بررسی لاگ نگه دار.';
if (lower.includes('آماده‌سازی تدوین') || lower.includes('manifest_path')) {
  stage = 'آماده‌سازی ویدیو، Sync یا Transcript';
  suggestion = 'وجود هر دو مسیر ویدیو، دسترسی فایل‌ها و فضای خالی دیسک را بررسی کن.';
} else if (lower.includes('مرحله نهایی تدوین') || lower.includes('فایل پریمیر')) {
  stage = 'ساخت XML، زیرنویس یا Voice Master';
  suggestion = 'فضای دیسک و دسترسی پوشه hermes_output را بررسی کن و دوباره اجرا بگیر.';
} else if (lower.includes('enoent') || lower.includes('not found') || lower.includes('پیدا نشد')) {
  stage = 'خواندن فایل';
  suggestion = 'مسیر فایل را دقیق و بدون بک‌اسلش اضافه در انتهای نام فایل ارسال کن.';
} else if (lower.includes('timeout') || lower.includes('timed out')) {
  stage = 'ارتباط با سرویس';
  suggestion = 'اتصال اینترنت یا سرویس محلی را بررسی کن و سپس دوباره تلاش کن.';
} else if (lower.includes('cuda') || lower.includes('memory') || lower.includes('allocation')) {
  stage = 'پردازش هوش مصنوعی/GPU';
  suggestion = 'برنامه‌های سنگین GPU را ببند یا پردازش را دوباره اجرا کن تا fallback فعال شود.';
} else if (lower.includes('telegram') || lower.includes('senddocument')) {
  stage = 'ارسال نتیجه در تلگرام';
  suggestion = 'فایل‌های خروجی داخل hermes_output باقی مانده‌اند؛ محدودیت حجم یا اتصال تلگرام را بررسی کن.';
} else if (lower.includes('pnl') || lower.includes('5001')) {
  stage = 'گزارش سود و زیان';
  suggestion = 'سرویس گزارش‌گیری محلی را بررسی و فرمان را دوباره ارسال کن.';
} else if (lower.includes('gemini') || lower.includes('ollama') || lower.includes('model')) {
  stage = 'پاسخ هوش مصنوعی';
  suggestion = 'اتصال Gemini یا سرویس Ollama را بررسی کن و پیام را دوباره بفرست.';
}

const nodeName = String(
  error?.node?.name ?? error?.context?.nodeName ?? source?.node?.name ?? stage
).slice(0, 120);
const executionId = String($execution.id);
const escapeHtml = (value) => String(value)
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;');

const message = [
  '⚠️ <b>پردازش کامل نشد</b>',
  '',
  `🧩 <b>مرحله:</b> ${escapeHtml(nodeName)}`,
  `🆔 <b>Execution:</b> <code>${escapeHtml(executionId)}</code>`,
  '',
  '🔎 <b>دلیل خلاصه:</b>',
  `<code>${escapeHtml(raw)}</code>`,
  '',
  '💡 <b>پیشنهاد:</b>',
  escapeHtml(suggestion),
].join('\n');

return [{ json: { error_message: message, execution_id: executionId } }];"""


HEARTBEAT_CHECK_CODE = r"""const fs = require('fs');
const path = require('path');
const OWNER_ID = 1140471;
const heartbeatDir = path.resolve('C:/Users/1SKY.IR/.n8n/hermes_output/typing-heartbeats');
const rootInput = $('When Executed by Another Workflow').first()?.json ?? {};
const heartbeatFile = path.resolve(String(rootInput.heartbeat_file || ''));
const chatId = Number(rootInput.message?.chat?.id ?? rootInput.owner_chat_id);

const validPath = heartbeatFile.startsWith(heartbeatDir + path.sep) &&
  /^typing-[A-Za-z0-9_-]+\.lock$/.test(path.basename(heartbeatFile));
if (!validPath || chatId !== OWNER_ID || !fs.existsSync(heartbeatFile)) return [];

try {
  const ageMs = Date.now() - fs.statSync(heartbeatFile).mtimeMs;
  if (ageMs > 12 * 60 * 60 * 1000) {
    fs.unlinkSync(heartbeatFile);
    return [];
  }
} catch (_) {
  return [];
}

return [{ json: { owner_chat_id: OWNER_ID } }];"""


def find_node(workflow: dict, name: str) -> dict:
    return next(node for node in workflow["nodes"] if node["name"] == name)


def replace_connection_target(workflow: dict, old_name: str, new_name: str) -> None:
    for source in workflow["connections"].values():
        for outputs in source.values():
            for group in outputs:
                for connection in group:
                    if connection.get("node") == old_name:
                        connection["node"] = new_name


def append_ai_connection(workflow: dict, model_name: str, node_name: str, index: int) -> None:
    model_connections = workflow["connections"][model_name]["ai_languageModel"][0]
    candidate = {"node": node_name, "type": "ai_languageModel", "index": index}
    if candidate not in model_connections:
        model_connections.append(candidate)


def build_heartbeat_workflow(telegram_credentials: dict) -> dict:
    version_id = str(uuid.uuid4())
    trigger_name = "When Executed by Another Workflow"
    check_name = "Check Heartbeat Active"
    typing_name = "Telegram Typing Heartbeat"
    wait_name = "Wait 4 Seconds"
    workflow = {
        "id": HEARTBEAT_WORKFLOW_ID,
        "name": "Hermes - Telegram Typing Heartbeat",
        "active": True,
        "nodes": [
            {
                "parameters": {"inputSource": "passthrough"},
                "type": "n8n-nodes-base.executeWorkflowTrigger",
                "typeVersion": 1.1,
                "position": [-480, 0],
                "id": str(uuid.uuid4()),
                "name": trigger_name,
            },
            {
                "parameters": {"jsCode": HEARTBEAT_CHECK_CODE},
                "type": "n8n-nodes-base.code",
                "typeVersion": 2,
                "position": [-256, 0],
                "id": str(uuid.uuid4()),
                "name": check_name,
            },
            {
                "parameters": {
                    "resource": "message",
                    "operation": "sendChatAction",
                    "chatId": "={{ $json.owner_chat_id }}",
                    "action": "typing",
                    "additionalFields": {},
                },
                "type": "n8n-nodes-base.telegram",
                "typeVersion": 1.2,
                "position": [-32, 0],
                "id": str(uuid.uuid4()),
                "name": typing_name,
                "credentials": json.loads(json.dumps(telegram_credentials)),
                "onError": "continueRegularOutput",
            },
            {
                "parameters": {"resume": "timeInterval", "amount": 4, "unit": "seconds"},
                "type": "n8n-nodes-base.wait",
                "typeVersion": 1.1,
                "position": [192, 0],
                "id": str(uuid.uuid4()),
                "name": wait_name,
            },
        ],
        "connections": {
            trigger_name: {"main": [[{"node": check_name, "type": "main", "index": 0}]]},
            check_name: {"main": [[{"node": typing_name, "type": "main", "index": 0}]]},
            typing_name: {"main": [[{"node": wait_name, "type": "main", "index": 0}]]},
            wait_name: {"main": [[{"node": check_name, "type": "main", "index": 0}]]},
        },
        "settings": {"executionOrder": "v1", "availableInMCP": False},
        "staticData": None,
        "pinData": {},
        "versionId": version_id,
        "activeVersionId": version_id,
        "versionMetadata": {
            "name": "Isolated four-second Telegram typing heartbeat",
            "description": (
                "Runs asynchronously from the owner-only Telegram workflow and stops when "
                "the root execution removes its validated marker file."
            ),
        },
    }
    return workflow


def main() -> None:
    exported = json.loads(SOURCE.read_text(encoding="utf-8-sig"))
    workflow = exported[0] if isinstance(exported, list) else exported
    typing_template = find_node(workflow, "Telegram - Typing")
    telegram_credentials = json.loads(json.dumps(typing_template["credentials"]))
    workflow["nodes"] = [
        node
        for node in workflow["nodes"]
        if node["name"] not in {"Telegram - Typing", "Merge - Preserve Telegram Update"}
    ]
    workflow["connections"].pop("Telegram - Typing", None)
    workflow["connections"].pop("Merge - Preserve Telegram Update", None)

    old_name = "Code in JavaScript"
    prepare_name = "Prepare Video Edit"
    review_name = "Review Transcript & Select Punch-ins"
    finalize_name = "Finalize Video Edit"
    owner_name = "Authorize Telegram Owner"
    initialize_name = "Initialize Processing Heartbeat"
    start_heartbeat_name = "Start Typing Heartbeat"
    format_error_name = "Format Processing Error"
    send_error_name = "Send Processing Error"
    stop_name = "Stop Processing Heartbeat"

    prepare = find_node(workflow, old_name)
    prepare["name"] = prepare_name
    prepare["parameters"] = {"jsCode": PREPARE_CODE}
    prepare["position"] = [64, -144]
    prepare["onError"] = "continueErrorOutput"
    replace_connection_target(workflow, old_name, prepare_name)
    workflow["connections"].pop(old_name, None)

    review_node = {
        "parameters": {
            "promptType": "define",
            "text": "={{ $json.review_prompt }}",
            "needsFallback": True,
            "options": {},
        },
        "type": "@n8n/n8n-nodes-langchain.chainLlm",
        "typeVersion": 1.9,
        "position": [304, -144],
        "id": str(uuid.uuid4()),
        "name": review_name,
        "onError": "continueRegularOutput",
    }
    finalize_node = {
        "parameters": {"jsCode": FINALIZE_CODE},
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [544, -144],
        "id": str(uuid.uuid4()),
        "name": finalize_name,
        "onError": "continueErrorOutput",
    }
    owner_node = {
        "parameters": {"jsCode": OWNER_AUTH_CODE},
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [-592, -16],
        "id": str(uuid.uuid4()),
        "name": owner_name,
    }
    initialize_node = {
        "parameters": {"jsCode": INITIALIZE_PROCESSING_CODE},
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [-368, -16],
        "id": str(uuid.uuid4()),
        "name": initialize_name,
        "onError": "continueErrorOutput",
    }
    start_heartbeat_node = {
        "parameters": {
            "source": "database",
            "workflowId": HEARTBEAT_WORKFLOW_ID,
            "mode": "once",
            "options": {"waitForSubWorkflow": False},
        },
        "type": "n8n-nodes-base.executeWorkflow",
        "typeVersion": 1.1,
        "position": [-144, -176],
        "id": str(uuid.uuid4()),
        "name": start_heartbeat_name,
        "onError": "continueRegularOutput",
    }
    format_error_node = {
        "parameters": {"jsCode": FORMAT_ERROR_CODE},
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [800, 160],
        "id": str(uuid.uuid4()),
        "name": format_error_name,
    }
    send_error_node = {
        "parameters": {
            "resource": "message",
            "operation": "sendMessage",
            "chatId": "=1140471",
            "text": "={{ $json.error_message }}",
            "additionalFields": {"parse_mode": "HTML"},
        },
        "type": "n8n-nodes-base.telegram",
        "typeVersion": 1.2,
        "position": [1024, 160],
        "id": str(uuid.uuid4()),
        "name": send_error_name,
        "credentials": json.loads(json.dumps(telegram_credentials)),
        "onError": "continueRegularOutput",
    }
    stop_node = {
        "parameters": {"jsCode": STOP_PROCESSING_CODE},
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1248, -32],
        "id": str(uuid.uuid4()),
        "name": stop_name,
        "onError": "continueRegularOutput",
    }
    workflow["nodes"].extend(
        [
            review_node,
            finalize_node,
            owner_node,
            initialize_node,
            start_heartbeat_node,
            format_error_node,
            send_error_node,
            stop_node,
        ]
    )
    find_node(workflow, "Send a document")["position"] = [784, -144]
    find_node(workflow, "Telegram Trigger")["position"] = [-816, -16]

    workflow["connections"][prepare_name] = {"main": [
        [{"node": review_name, "type": "main", "index": 0}],
        [{"node": format_error_name, "type": "main", "index": 0}],
    ]}
    workflow["connections"][review_name] = {
        "main": [[{"node": finalize_name, "type": "main", "index": 0}]]
    }
    workflow["connections"][finalize_name] = {"main": [
        [{"node": "Send a document", "type": "main", "index": 0}],
        [{"node": format_error_name, "type": "main", "index": 0}],
    ]}
    workflow["connections"]["Telegram Trigger"] = {
        "main": [[{"node": owner_name, "type": "main", "index": 0}]]
    }
    workflow["connections"][owner_name] = {
        "main": [[{"node": initialize_name, "type": "main", "index": 0}]]
    }
    workflow["connections"][initialize_name] = {"main": [
        [
            {"node": start_heartbeat_name, "type": "main", "index": 0},
            {"node": "If - PnL Command", "type": "main", "index": 0},
        ],
        [{"node": format_error_name, "type": "main", "index": 0}],
    ]}
    workflow["connections"][format_error_name] = {
        "main": [[{"node": send_error_name, "type": "main", "index": 0}]]
    }
    workflow["connections"][send_error_name] = {
        "main": [[{"node": stop_name, "type": "main", "index": 0}]]
    }

    error_routes = {
        "AI Agent": "Send a text message",
        "Get a file": "AI Agent",
        "Parse PnL Command": "Get PnL Report",
        "Get PnL Report": "Send PnL Report",
        "Send a text message": stop_name,
        "Send PnL Report": stop_name,
        "Send a document": stop_name,
    }
    for node_name, success_target in error_routes.items():
        node = find_node(workflow, node_name)
        node["onError"] = "continueErrorOutput"
        workflow["connections"][node_name] = {"main": [
            [{"node": success_target, "type": "main", "index": 0}],
            [{"node": format_error_name, "type": "main", "index": 0}],
        ]}
    append_ai_connection(workflow, "Google Gemini Chat Model1", review_name, 0)
    append_ai_connection(workflow, "Local AI Fallback - Qwen 3.5 4B", review_name, 1)

    gemini_model = find_node(workflow, "Google Gemini Chat Model1")
    gemini_model["retryOnFail"] = True
    gemini_model["maxTries"] = 3
    gemini_model["waitBetweenTries"] = 5000

    local_model = find_node(workflow, "Local AI Fallback - Qwen 3.5 4B")
    local_options = local_model.setdefault("parameters", {}).setdefault("options", {})
    local_options.update(
        {
            "think": False,
            "temperature": 0.15,
            "keepAlive": "5m",
            "lowVram": True,
            "numBatch": 128,
            "numCtx": 8192,
            "numGpu": 0,
            "numPredict": 1400,
            "numThread": 6,
            "useMMap": True,
        }
    )

    version_id = str(uuid.uuid4())
    workflow["versionId"] = version_id
    workflow["activeVersionId"] = version_id
    workflow["active"] = True
    workflow["versionMetadata"] = {
        "name": "Hafez Studio Director Engine v0.1",
        "description": (
            "Silently rejects every Telegram update outside the owner's private chat. "
            "Starts an isolated four-second typing heartbeat, stops it after the last result, "
            "and sends redacted actionable errors for terminal processing failures. "
            "Delegates prepare/finalize stages to the portable Hafez Studio engine, preserves the "
            "proven two-camera sync and silence cuts, derives sequence format from camera 1, and "
            "validates complete Persian editorial statements with optional English kickers. Adds "
            "dense Signal OS graphics, original editable MOGRT mappings, flowcharts, comparisons, "
            "smart camera switching, Premiere markers, complete YouTube/edit-note packages, and "
            "Broadcast Warm Male v2 mastering only from camera 1 microphone audio while keeping "
            "raw camera audio disabled."
        ),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps([workflow], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    heartbeat = build_heartbeat_workflow(telegram_credentials)
    HEARTBEAT_OUTPUT.write_text(
        json.dumps([heartbeat], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(OUTPUT)
    print(HEARTBEAT_OUTPUT)


if __name__ == "__main__":
    main()
