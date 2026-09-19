'use strict';

// Scoped maintenance for the existing n8n scheduled-news records. Credentials
// stay in process memory and are never included in reports or error messages.
const fs = require('node:fs');
const path = require('node:path');
const { createRequire } = require('node:module');
const { execFileSync } = require('node:child_process');
const { DatabaseSync } = require('node:sqlite');

const workspace = path.resolve(__dirname, '..');
const runnerId = '8c2ff152-61ec-40bf-ad71-f330569f7bda';
const n8nRoot = 'C:/Users/1SKY.IR/AppData/Roaming/npm/node_modules/n8n';
const n8nRequire = createRequire(path.join(n8nRoot, 'package.json'));
let stage = 'authorization';

function authorize(category) {
  const result = execFileSync(
    'C:/Users/1SKY.IR/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe',
    ['-NoLogo', '-NoProfile', '-NonInteractive', '-File',
      path.join(workspace, 'security/hermes-local-guard/Test-HermesSession.ps1'),
      '-Category', category],
    { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true },
  );
  if (!result.includes(`LOCAL_SESSION_AUTHORIZED category=${category} `)) {
    throw new Error('Local authorization unavailable.');
  }
}

async function main() {
  const pause = process.argv[2] === '--pause';
  if (process.argv.length > 3 || (process.argv[2] && !['--inspect', '--pause'].includes(process.argv[2]))) {
    throw new Error('Unsupported operation.');
  }
  authorize(pause ? 'HERMES_CONFIG_WRITE' : 'SENSITIVE_READ');
  stage = 'read-local-workflow';
  const sqlite = new DatabaseSync(path.join(workspace, 'database.sqlite'), { readOnly: true });
  let connection;
  let recentExecutions;
  try {
    const workflow = sqlite.prepare('SELECT nodes FROM workflow_entity WHERE id=?').get(runnerId);
    const node = JSON.parse(workflow.nodes).find(n => n.name === 'Claim Due Tasks');
    const credentialId = node.credentials.postgres.id;
    const credential = sqlite.prepare('SELECT data FROM credentials_entity WHERE id=? AND type=?')
      .get(credentialId, 'postgres');
    const instance = JSON.parse(fs.readFileSync(path.join(workspace, 'config'), 'utf8'));
    const { CipherAes256CBC } = n8nRequire('n8n-core/dist/encryption/aes-256-cbc.js');
    const stored = JSON.parse(new CipherAes256CBC().decrypt(credential.data, instance.encryptionKey));
    const defaults = { host: 'localhost', database: 'postgres', user: 'postgres', password: '', port: 5432, ssl: 'disable' };
    const data = { ...defaults, ...stored };
    const expressionFields = Object.keys(defaults).filter(k =>
      typeof data[k] === 'string' && data[k].startsWith('='));
    if (expressionFields.length) throw new Error('Runtime credential expressions require n8n.');
    if (data.sshTunnel) throw new Error('Unexpected tunnel configuration.');
    connection = {
      host: data.host, port: data.port || 5432, database: data.database,
      user: data.user, password: data.password,
      ssl: data.allowUnauthorizedCerts === true
        ? { rejectUnauthorized: false }
        : !['disable', undefined].includes(data.ssl),
      sslmode: data.ssl || 'disable',
      application_name: 'Hermes scheduled-news maintenance',
      connectionTimeoutMillis: 10000,
      statement_timeout: 10000,
      query_timeout: 12000,
    };
    recentExecutions = sqlite.prepare(
      'SELECT id,status,startedAt,stoppedAt FROM execution_entity WHERE workflowId=? ORDER BY id DESC LIMIT 4',
    ).all(runnerId);
  } finally {
    sqlite.close();
  }

  stage = 'connect-task-storage';
  const { Client } = n8nRequire('pg');
  const client = new Client(connection);
  try {
    await client.connect();
    connection.password = undefined;
    if (pause) {
      stage = 'pause-news-schedules';
      const expected = new Map([
        ['1', { name: 'AI News Digest - Morning', hour: 10 }],
        ['2', { name: 'AI News Digest - Evening', hour: 17 }],
      ]);
      const ids = [...expected.keys()];
      await client.query('BEGIN');
      await client.query("SET LOCAL lock_timeout = '3s'");
      try {
        const before = (await client.query(`
          SELECT id::text, owner_chat_id::text, name, task_type, schedule_kind,
                 hour_local, minute_local, timezone, active, locked_at, updated_at,
                 (task_prompt ~* 'AI|artificial intelligence|هوش مصنوعی') AS ai_related
          FROM hermes_scheduled_tasks
          WHERE id = ANY($1::bigint[]) AND deleted_at IS NULL
          ORDER BY id
          FOR UPDATE NOWAIT
        `, [ids])).rows;
        if (before.length !== 2 || new Set(before.map(r => r.owner_chat_id)).size !== 1) {
          throw new Error('Target schedules no longer match the inspected records.');
        }
        for (const row of before) {
          const match = expected.get(row.id);
          if (!match || row.name !== match.name || row.task_type !== 'research_report' ||
              row.schedule_kind !== 'daily' || row.hour_local !== match.hour ||
              row.minute_local !== 0 || row.timezone !== 'Asia/Tehran' || !row.ai_related ||
              row.locked_at !== null) {
            throw new Error('A target changed or has an in-flight delivery.');
          }
        }
        const backupPath = path.join(workspace, 'backups',
          `ai-news-pause-${new Date().toISOString().replace(/[:.]/g, '-')}.json`);
        fs.writeFileSync(backupPath, JSON.stringify({
          operation: 'pause-only',
          tasks: before.map(({ id, name, active, updated_at }) => ({ id, name, active, updated_at })),
        }, null, 2), { flag: 'wx', mode: 0o600 });
        const changed = await client.query(`
          UPDATE hermes_scheduled_tasks
          SET active = FALSE, updated_at = now()
          WHERE id = ANY($1::bigint[]) AND active = TRUE AND deleted_at IS NULL
          RETURNING id::text, name, active
        `, [ids]);
        const verified = (await client.query(`
          SELECT id::text, name, active, locked_at
          FROM hermes_scheduled_tasks WHERE id = ANY($1::bigint[]) ORDER BY id
        `, [ids])).rows;
        if (verified.length !== 2 || verified.some(row => row.active || row.locked_at !== null)) {
          throw new Error('Pause verification failed.');
        }
        await client.query('COMMIT');
        console.log(JSON.stringify({ ok: true, operation: 'paused', changed: changed.rowCount,
          schedules: verified, backup: path.basename(backupPath) }));
      } catch (error) {
        await client.query('ROLLBACK').catch(() => {});
        throw error;
      }
    }
    stage = 'inspect-schedules';
    await client.query('BEGIN READ ONLY');
    const result = await client.query(`
      SELECT id::text, name, task_type, schedule_kind, hour_local, minute_local,
             timezone, active, next_run_at, last_run_at, last_status, locked_at,
             (task_prompt ~* 'AI|artificial intelligence|هوش مصنوعی') AS ai_related
      FROM hermes_scheduled_tasks
      WHERE deleted_at IS NULL
      ORDER BY id
    `);
    await client.query('COMMIT');
    console.log(JSON.stringify({ schedules: result.rows, recent_runner_executions: recentExecutions }));
  } finally {
    await client.end().catch(() => {});
  }
}

main().catch(error => {
  const code = /^[A-Z0-9_]{2,40}$/.test(String(error.code || '')) ? error.code : undefined;
  console.error(JSON.stringify({ ok: false, stage, code }));
  process.exitCode = 1;
});
