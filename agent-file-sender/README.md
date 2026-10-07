# Agent File Sender

Reusable local file delivery for Codex and Antigravity through n8n and the owner's existing Telegram bot. Sending is always a document, so APKs, PDFs, archives, images, audio and videos retain the original file bytes.

## Use

```powershell
& "$env:USERPROFILE\.n8n\scripts\agent-file-sender\Send-AgentFile.ps1" `
  -FilePath 'C:\Work\final-report.pdf' `
  -Caption 'گزارش نهایی'
```

Use only for files the user explicitly requested to send. The destination is fixed during installation. There is no recipient parameter or public webhook. Both agents use this same entry point; no Telegram token is copied into an agent, script, shell command or Git.

The existing boot-bound local Hermes guard must authorize `CHAT_ADMIN`. When Codex's sandbox cannot access DPAPI, run this same script with its normal elevated tool permission; do not weaken the guard. After a PC restart, the owner may need to unlock the existing local guard again. Do not automate that unlock.

`-ValidateOnly` checks filename, size and installation without sending or reading the file contents. Each file must be non-empty and at most 50,000,000 bytes. Captions are limited to 1,024 UTF-16 characters conservatively. Telegram's documented cloud Bot API limit: https://core.telegram.org/bots/api#senddocument .

## Results and retries

Successful output is JSON with `status: sent`, `messageId`, `sha256`, filename, byte count and `receiptPath`. A matching Telegram response for the configured chat, filename and size is required. n8n process exit code alone is never success.

Repeating the same file bytes, filename and caption returns `already_sent` and the saved receipt without another upload. `-RequestId` can supply a stable caller identifier. Reusing an ID for different content fails. Use `-Resend` only when the user explicitly requests another copy.

`SENDER_BUSY` means another agent holds the local sender lock; that invocation did not send. `DELIVERY_UNCERTAIN` or `DELIVERY_UNCONFIRMED` means the outcome must be inspected before retrying. No automatic Telegram retry is configured. If n8n logged a valid receipt but the wrapper was interrupted, repeating the same invocation recovers that receipt instead of sending again. Telegram provides no end-to-end exactly-once upload guarantee; do not claim one.

Runtime files are outside Git in `Documents\Codex\AgentFileSender`: configuration, request journals, receipts and n8n execution logs. Successful staged copies are removed; source files are never deleted. Failed staged files are retained for diagnosis. Runtime data and n8n execution history may include filenames/captions and must not be committed. The lock prevents simultaneous Codex/Antigravity requests from mixing file contents or captions.

## Architecture

Manual trigger → read request JSON → extract JSON → read staged file → Telegram Send Document.

The workflow intentionally remains inactive: the sender invokes it explicitly using `n8n execute --id`. Do not activate it, change the bot's webhook, or manually rerun an old delivery. n8n CLI must be installed on the machine, but opening Telegram Desktop is unnecessary. The local PC must be running and able to reach Telegram.

The source template lives in the companion N8N-Workflows repository as `agent-file-sender.json`. It contains no credential value or recipient. Installation binds the existing n8n credential reference and owner chat locally; it never exports or decrypts the bot token. CLI proxy and task-runner settings are process-local and restored afterwards. A dedicated broker port avoids the running n8n service's default port.

## Install once

```powershell
& .\Install-AgentFileSender.ps1 -CredentialId '<existing n8n credential ID>' `
  -ChatId '<owner private chat ID>' -ProxyUrl 'http://127.0.0.1:10808'
```

Installation requires the existing `HERMES_CONFIG_WRITE` local authorization. It creates one new manual workflow and refuses a second installation when config.json exists. If import was interrupted, inspect installed-workflow.json and the n8n runtime using that exact ID before recovering; never blindly create another workflow. Do not change existing trading workflows or credentials.

## Verification

Run `Test-AgentFileSender.ps1` for local checks. Then send a small authorized guide through `Send-AgentFile.ps1`, verify the Telegram receipt, repeat the exact request and verify `already_sent` without another n8n execution. Changes to source files must be followed by a new verification appropriate to the change.
