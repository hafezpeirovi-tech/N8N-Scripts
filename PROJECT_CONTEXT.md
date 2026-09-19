# N8N Scripts Project Context

## Purpose
This repository contains utility scripts written in Python and JavaScript (Node.js) to automate, build, and inspect the local n8n automation workspace.

## Dependencies
- Node.js (
8n global package via 
pm)
- Python (modules: json, sqlite3, pathlib)
- Direct access to local SQLite databases and 
8n configuration.

## Hardcoded Paths
Scripts heavily rely on specific Windows user paths:
- C:\Users\1SKY.IR\.n8n (Workspace, SQLite DB)
- C:\Users\1SKY.IR\AppData\Roaming\npm\node_modules\n8n
- C:\Users\1SKY.IR\.cloudflared\cert.pem
- C:\Users\1SKY.IR\AppData\Local\Google\Chrome\User Data\...

## Interaction with n8n
These scripts DO NOT run inside the n8n execution context. They operate locally on the host machine to dynamically extract workflows, decrypt credentials on-the-fly (via 
8n export:credentials), and manage infrastructure.
