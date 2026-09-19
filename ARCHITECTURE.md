# Architecture

## Categories
1. **Build Scripts**: uild_phase2_workflows.py, uild_video_editing_workflow.py. These consume templates and output final JSON workflow files.
2. **Inspection Scripts**: inspect_n8n_state.py, inspect_telegram_webhook.mjs, inspect_cloudflare_tunnel_host.py. These dynamically read host status and n8n internals.
3. **Task Scripts**: i-news-schedule.cjs directly queries database.sqlite to bypass n8n credential boundaries for maintenance tasks.

## Security Posture
- Credentials are NOT hardcoded.
- Authentication tokens are either decrypted dynamically using 
8n export:credentials --decrypted or fetched via direct AES-256 decryption from the SQLite DB using CipherAes256CBC.
