# Decisions

- **Dynamic Decryption**: Secrets are intentionally not stored in these scripts. Instead, the 
8n export:credentials CLI command or direct database decryption is utilized at runtime.
- **Polyglot Design**: Python is used for templating JSON workflows. Node.js/MJS is used for direct integration with 
8n binary logic.
