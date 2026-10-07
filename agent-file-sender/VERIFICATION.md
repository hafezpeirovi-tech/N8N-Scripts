# Verification — 2026-10-07

Verified on the owner's Windows machine using the installed n8n CLI and existing Telegram credential.

- PowerShell syntax validation passed for all four scripts.
- Eleven local checks passed: input validation, request identity, matching Telegram receipts, wrong recipient/name/size rejection, and incomplete result rejection.
- The installer imported the new manual workflow successfully. Its active flag remains false.
- A real delivery of `USE-FROM-AGENTS.txt` completed with a Telegram message acknowledgement matching the destination, filename and 1,972-byte size.
- Repeating the same request returned `already_sent` and the same message ID. A read-only n8n history check confirmed the execution count remained one, with status `success`.
- The temporary request and staged file were removed after success; the original guide remains intact.

Private delivery identifiers and receipts are stored only in the local runtime directory, outside this repository. No bot token was exported.

This verifies the local happy path and duplicate-request handling. It does not claim exactly-once delivery across arbitrary network/process failures or support for files above the configured size limit. Uncertain attempts require inspection before another upload.
