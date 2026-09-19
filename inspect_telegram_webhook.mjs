import { spawnSync } from 'node:child_process';

const nodePath = 'C:\\Program Files\\nodejs\\node.exe';
const n8nPath = 'C:\\Users\\1SKY.IR\\AppData\\Roaming\\npm\\node_modules\\n8n\\bin\\n8n';
const credentialId = 'mPHsflbzAQR2WA5h';

const exported = spawnSync(
  nodePath,
  [n8nPath, 'export:credentials', `--id=${credentialId}`, '--decrypted'],
  { encoding: 'utf8', windowsHide: true },
);
if (exported.status !== 0) {
  throw new Error(`Credential export failed with code ${exported.status}`);
}

const start = exported.stdout.indexOf('[');
const end = exported.stdout.lastIndexOf(']');
if (start < 0 || end < start) {
  throw new Error('Credential export did not return JSON');
}
const credentials = JSON.parse(exported.stdout.slice(start, end + 1));
const data = credentials[0]?.data ?? {};
const token = data.accessToken ?? data.apiToken ?? data.token;
if (!token) {
  throw new Error('Telegram credential token field was not found');
}

const response = await fetch(`https://api.telegram.org/bot${token}/getWebhookInfo`);
const payload = await response.json();
if (!payload.ok) {
  throw new Error(`Telegram getWebhookInfo failed with HTTP ${response.status}`);
}

const webhookUrl = payload.result?.url ? new URL(payload.result.url) : null;
console.log(`telegram_webhook_set=${Boolean(webhookUrl)}`);
console.log(`telegram_webhook_protocol=${webhookUrl?.protocol ?? 'none'}`);
console.log(`telegram_webhook_host=${webhookUrl?.hostname ?? 'none'}`);
console.log(`telegram_pending_updates=${payload.result?.pending_update_count ?? 0}`);
console.log(`telegram_last_error=${payload.result?.last_error_message ?? 'none'}`);
