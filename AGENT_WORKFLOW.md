# AGENT WORKFLOW

This document defines the unified collaboration standard for Codex and Antigravity agents working on this repository.

## A. Source of Truth
- The GitHub repository is the absolute **Source of Truth**.
- No other location should be considered authoritative for source code.

## B. Branching Model
- main = Stable and synchronized.
- **Codex Agents** must work on: codex/<task-name>
- **Antigravity Agents** must work on: ntigravity/<task-name>
- Direct commits to main by agents are **strictly prohibited** unless the change is trivial and explicitly approved by the user.

## C. Agent Startup Protocol
Before beginning any work, every agent MUST execute:
1. git status
2. git pull origin main (or git fetch origin if on a separate branch)
3. Read the relevant documentation (AGENT_WORKFLOW.md, PROJECT_CONTEXT.md, ARCHITECTURE.md).

## D. Before Editing Guidelines
- **Inspect Relevant Files:** Always read the current state of the source code before modifying.
- **Understand Dependencies:** Check how changes impact other components.
- **Never Assume Missing Context:** If something is ambiguous, clarify or state the inference.
- **Never Invent History:** Do not hallucinate previous decisions or features.

## E. Safety Rules
The following commands and actions are **BANNED** unless explicitly requested by the user:
- git reset --hard
- git clean -fd
- git push --force
- Any form of History Rewrite (e.g., rebasing pushed commits).

## F. Secrets Management
Never commit or document any of the following:
- .env files
- API keys, passwords, or Bearer tokens
- Credentials or private keys
- Runtime databases (e.g., database.sqlite)

## G. Completion Protocol
Before finishing a task, the agent MUST:
1. Run relevant tests.
2. Run git diff to review changes.
3. Run git status.
4. Commit the changes cleanly.
5. Push the dedicated branch to origin.

## H. Parallel Agents & Collaboration
- **Parallel Work:** Each agent MUST work on its dedicated branch (codex/<task> or ntigravity/<task>).
- **Syncing:** Both agents must run git fetch origin before starting and before merging.
- **Merging:** Merges to main are only allowed after a diff review, conflict check, and test verification.
- **No Overwriting:** No agent is permitted to reset, overwrite, or destroy another agent's branch or changes.
