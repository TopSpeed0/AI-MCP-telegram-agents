# AI-MCP-telegram-agents

<p align="center">
  <img src="docs/banner.png" alt="Telegram ↔ VS Code Copilot Bridge" width="800">
</p>

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Node.js](https://img.shields.io/badge/node-%3E%3D22.10-339933?logo=node.js&logoColor=white)](https://nodejs.org)
[![Zero dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)](package.json)
[![MCP](https://img.shields.io/badge/MCP-2024--11--05-8A2BE2)](https://modelcontextprotocol.io/)
[![Telegram Bot API](https://img.shields.io/badge/Telegram-Bot%20API-26A5E4?logo=telegram&logoColor=white)](https://core.telegram.org/bots/api)
[![VS Code](https://img.shields.io/badge/VS%20Code-Copilot%20Agent-007ACC?logo=visualstudiocode&logoColor=white)](https://code.visualstudio.com/)
[![Platform](https://img.shields.io/badge/platform-win%20%7C%20mac%20%7C%20linux-lightgrey)](#requirements)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-ff69b4)](https://github.com)

A **zero-dependency** Telegram ↔ VS Code Copilot bridge as a [Model Context
Protocol](https://modelcontextprotocol.io/) (MCP) server.

Lets a Copilot agent **ask you questions and receive instructions over
Telegram**, so you can drive long-running coding sessions from your phone.

> **Architecture Note (2026):** The `@telegram-autopilot` / `@vscode-worker` patterns described here are the **v1 foundation**. The recommended production setup uses **Hermes as Overmind** with any number of standalone worker daemons — see [§6 Hybrid mode](#6-hybrid-mode--hermes-overmind--multi-worker) for the full picture. The MCP server (`mcp/telegram-tg.js`) in this repo is still used by all workers as their Telegram tool.

---

Two tools are exposed to the agent:

| Tool | Behavior |
|------|----------|
| `tg_send(text, parse_mode?)` | Fire-and-forget notification. |
| `tg_ask(question, timeoutSeconds?, parse_mode?)` | Sends a message and **blocks until you reply** in Telegram. Returns the reply text. |
| `tg_typing(seconds?, action?)` | Shows a "typing…" indicator in your chat for N seconds (refreshed every 4s). Use before long work so you can see the agent is busy. Other actions: `upload_photo`, `upload_document`, `record_video`, etc. |

Combine with the built-in Copilot agent to turn Copilot Chat into a
Telegram-driven agent loop.

---

## Why not [chigwell/telegram-mcp](https://github.com/chigwell/telegram-mcp)?

Different problem. [chigwell/telegram-mcp](https://github.com/chigwell/telegram-mcp)
is excellent if you want an agent to **operate your Telegram account** — read
chats, manage groups, send media, 80+ tools via Telethon and your personal
account session.

This project does the opposite: it exposes the **minimum** surface needed for
**human-in-the-loop agent control** from Telegram.

|                          | **AI-MCP-telegram-agents** (this)          | **chigwell/telegram-mcp**                   |
|--------------------------|-------------------------------------------|---------------------------------------------|
| Auth                     | Bot token (BotFather)                     | Personal Telegram account (session string)  |
| Tools                    | 2 — `tg_send`, `tg_ask`                   | 80+ (chats, groups, media, admin, etc.)     |
| Blocks until human reply | **Yes** (`tg_ask` long-polls)             | No                                          |
| Runtime                  | Node.js 18+, **zero dependencies**, 1 file | Python + Telethon + uv/Docker              |
| Telegram API             | Bot HTTP API (`api.telegram.org/bot…`)    | MTProto via Telethon                        |
| Use case                 | "Drive Copilot from my phone"             | "Let the agent run my Telegram account"     |

The `tg_ask` blocking primitive is what makes the **autopilot loop** possible:
the agent halts and waits for your Telegram reply before continuing. None of
the chigwell tools wait for human input — they're all immediate Telegram API
calls. Pick whichever matches what you actually need; they don't overlap.

This codebase **does not use or derive from** chigwell/telegram-mcp's code.
It's an independent Node implementation against the public Bot API.

---

## Requirements

- **Node.js 22.10+** (uses built-in `https` + `--use-system-ca`, no `npm install` needed)
- **VS Code** with GitHub Copilot Chat (Agent mode)
- A **Telegram bot** and your numeric **chat ID**

> **Behind a corporate TLS proxy?** Both `setup.js` and the MCP server launch
> Node with `--use-system-ca`, which trusts the OS certificate store. As long
> as your proxy's root cert is installed in Windows/macOS/Linux trust roots
> (it usually is, via group policy), things just work.

---

## Quick Start (one command)

After cloning, run the interactive installer:

```bash
git clone https://github.com/TopSpeed0/AI-MCP-telegram-agents.git
cd AI-MCP-telegram-agents
node setup.js          # or: npm run setup
```

The installer will:

1. Ask for your **bot token** (validates it via Telegram's `getMe`).
2. Auto-detect your **chat ID** — it asks you to send any message to the bot,
   then reads it back. Multi-chat? You get a numbered picker. No message? Manual fallback.
3. Write `.telegram-config` (already gitignored, mode `0600`).
4. Send a confirmation message to your Telegram.
5. Print the next steps.

Then reload VS Code → open Copilot Chat (Agent mode) → type
`@telegram-autopilot start autopilot` and go.

If you prefer the manual route, the step-by-step guide is below.

---

## 1. Create a Telegram bot

1. Open Telegram, message [@BotFather](https://t.me/BotFather).
2. Send `/newbot`, follow the prompts, copy the **bot token**
   (looks like `1234567890:ABCdef...`).
3. Start a chat with your new bot and send it any message.
4. Get your **chat ID**:
   ```
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
   ```
   Open that URL in a browser — find `"chat":{"id":<NUMBER>,...}` in the JSON.

---

## 2. Drop the folder into your project

Either:

- **Use as a submodule / copy** alongside an existing project, and merge the
  `.vscode/mcp.json` snippet into your workspace's own `.vscode/mcp.json`, **or**
- **Open this folder directly in VS Code** as a standalone workspace.

The MCP server file is `mcp/telegram-tg.js`.

---

## 3. Configure credentials

`node setup.js` (or `npm run setup`) does this for you — it writes
`.telegram-config` in the project root with your token and chat ID.

If you prefer to do it by hand:

```bash
cp .telegram-config.example .telegram-config
# edit .telegram-config and fill in bot_token + chat_id
```

`.telegram-config` is **git-ignored** and gets file mode `0600` when written
by `setup.js`.

> **Alternative:** set environment variables `TELEGRAM_BOT_TOKEN` and
> `TELEGRAM_CHAT_ID` instead. The server checks env vars first, then falls
> back to `.telegram-config`. Use this if you'd rather not have a file on
> disk (e.g. CI, containers, or a secret manager).

---

## 4. Start the MCP server in VS Code

1. Open this folder (or your own workspace with `mcp.json` merged in).
2. **Reload window** (or run command **MCP: List Servers** → start `telegram-tg`).
3. Open Copilot Chat, switch to **Agent** mode.
4. You should see `tg_send` and `tg_ask` listed in the tool picker.

Test it:

> Send me a Telegram message saying "hello from Copilot".

The agent should call `tg_send` and a message lands in your Telegram chat.

---

## 5. Run the autopilot loop

The repo ships a Copilot agent at
[`.github/agents/telegram-autopilot.agent.md`](.github/agents/telegram-autopilot.agent.md).

In Copilot Chat, type:

```
@telegram-autopilot start autopilot
```

The agent begins the loop automatically — sends 🟢Ready. to Telegram and waits
for your next instruction. Reply from your phone; Copilot does the work in
VS Code and reports back.

> **Tip:** You can also click the `@` icon in the chat input and select
> **telegram-autopilot** from the agent picker.

Send `stop` from Telegram (or close the chat) to exit the loop.

### Token budget

Copilot will stop on its own when your quota is hit. The loop will fail
mid-`tg_ask`/`tg_send` — start a new chat and type
`@telegram-autopilot start autopilot` again when your quota resets.

### Why HTML for messages?

Telegram's MarkdownV2 requires escaping a dozen punctuation characters;
HTML only needs `&` `<` `>`. Much less likely to crash on dynamic content
like file paths or code output.

---

## How it works

- Pure Node.js, no dependencies. Speaks **MCP 2024-11-05** JSON-RPC over stdio.
- `tg_send` calls Telegram's `sendMessage` once.
- `tg_ask` sends a `sendMessage`, then **long-polls** `getUpdates` until either
  a new reply arrives in the configured chat or `timeoutSeconds` elapses.
- Update offset persisted to `.telegram-state.json` to avoid double-consuming
  messages across restarts.
- Filters messages to the configured `chat_id` so other Telegram users can't
  drive your agent.

---

## ⚠️ One poller per bot token

Telegram's `getUpdates` is exclusive — **only one process at a time** can long-
poll a given bot. If you run two autopilot sessions, a separate daemon, or
webhook + polling against the same token, replies will be split randomly.

If you need parallel agents, create a separate bot per agent.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `No Telegram config` error | Set env vars or create `.telegram-config`. |
| Server starts but `tg_ask` never returns | Some other process is polling the same bot. Stop the other process or use a new bot token. |
| `Conflict: terminated by other getUpdates request` in stderr | Same as above. |
| `unable to get local issuer certificate` / `self-signed cert in chain` | Corporate TLS proxy. Already handled — both `setup.js` and the MCP server use `--use-system-ca` (Node 22.10+). On older Node, set `NODE_EXTRA_CA_CERTS=/path/to/corp-root.pem` and re-run. |
| Non-text replies | The server returns `(non-text message)` for stickers/photos. Reply with text. |

---

## Security notes

- The bot token is full control of your bot — **never commit it**.
  `.gitignore` already excludes `.telegram-config` and `.env`.
- The server only accepts messages from the configured `chat_id`, but **anyone
  who knows the bot username can DM it** (their messages just get filtered).
  Don't share the bot username if your agent does sensitive work.
- The agent has full access to whatever tools VS Code exposes (terminal, file
  edits). Treat the Telegram chat like a remote shell — don't share it.

---

## 6. Hybrid mode — Hermes Overmind + Multi-Worker

For production setups, Hermes is the **always-on Overmind** that owns Telegram and delegates to specialized worker daemons.

### Architecture

```
You (Telegram)
    │
    ▼
Hermes Agent — Overmind (always-on, owns Telegram)
    ├── General tasks → handles directly (web, research, cron, memory, MCP)
    │
    ├── worker-a → .<worker-a>-queue.json ┐
    ├── worker-b → .<worker-b>-queue.json ├─ any number of workers
    └── worker-n → .<worker-n>-queue.json ┘
                         ↓
             Worker daemon (standalone process)
             reads queue, executes, writes result
```

Register any number of workers in `.telegram-config` under `agents`. VS Code Copilot (this repo's `@vscode-worker`) is one possible worker — available as a **legacy option** for workflows that need the VS Code editor directly.

### Worker queue paths

Worker paths are stored in `.telegram-config` under `agents`:

```json
{
  "bot_token": "...",
  "chat_id": "...",
  "agents": {
    "copilot": { "queue": "/path/to/.copilot-queue.json" },
    "claude":  { "queue": "/path/to/.claude-queue.json" },
    "vscode":  { "queue": "/path/to/.vscode-queue.json" }
  }
}
```

Hermes reads these paths at delegation time — no hardcoded paths in the agent config.

### Queue protocol

```json
{ "id": "task-001", "status": "pending", "task": "Natural language instruction" }
```

Status flow: `pending` → `working` → `done` | `error`

Hermes polls the queue file until completion, reads `result`, and relays it to Telegram.

### Key design decisions

- **Generic + local**: each daemon works standalone (direct Telegram messages) AND as a Hermes worker (queue polling) — same process, no mode switching
- **Skills**: CLI daemons load skills from `~/.claude/skills/` — one skill library, multiple workers
- **No bot-to-bot**: Hermes delegates via shared JSON files, not Telegram (bots can't message other bots)
- **Corporate TLS**: all use `node --use-system-ca` so they work behind MITM proxies
- **Config-driven**: worker paths live in `.telegram-config`, not hardcoded in prompts or agent config

### Quick Setup

```bash
# 1. Run setup.js first (if not done already)
node setup.js

# 2. Add agents paths to .telegram-config (see .telegram-config.example)

# 3. Start Hermes gateway
hermes gateway start

# 4. Start your worker daemons
# Copilot CLI: see TopSpeed0/Copilot-CLI-Telegram-MCP
# Claude Code: see TopSpeed0/ClaudeCodeTelgMCP

# Telegram: send a message to your bot!
```

### VS Code worker (legacy)

The original `@vscode-worker` + `.vscode-queue.json` pattern still works — useful when you're already in VS Code and want Copilot Chat to handle a task. Start it with:

```
@vscode-worker start worker
```

See also: [Copilot-CLI-Telegram-MCP](https://github.com/TopSpeed0/Copilot-CLI-Telegram-MCP) | [ClaudeCodeTelgMCP](https://github.com/TopSpeed0/ClaudeCodeTelgMCP)

### Hermes Installation Layout

After `hermes gateway install`, Hermes creates the following on Windows:

```
C:\Users\<username>\AppData\Local\hermes\
├── hermes-agent\          ← source code + venv (pythonw.exe lives here)
│   └── venv\Scripts\
│       ├── hermes.exe
│       └── pythonw.exe    ← headless runner (no console window)
├── gateway-service\
│   └── Hermes_Gateway.cmd ← startup script used by the Scheduled Task
├── config.yaml            ← main config
├── .env                   ← API keys / secrets
├── skills\                ← agent skills
└── state.db               ← session store (SQLite)
```

**Windows Scheduled Task (auto-start on logon):**

| Field | Value |
|-------|-------|
| Task name | `Hermes_Gateway` |
| Trigger | `MSFT_TaskLogonTrigger` — runs at user logon |
| Script | `%LOCALAPPDATA%\hermes\gateway-service\Hermes_Gateway.cmd` |
| Process | `pythonw.exe -m hermes_cli.main gateway run` (headless, no console) |
| Status | Running silently in background |

> **CISO / Security note:** The Scheduled Task runs only under your user account (not SYSTEM).
> To disable auto-start: open Task Scheduler → `Hermes_Gateway` → Disable.
> To start manually instead, use the Desktop shortcut (see below).

**Create a manual Desktop shortcut** (run once in PowerShell after install):

```powershell
# Creates shortcut on Desktop — works with or without OneDrive
.\create-hermes-shortcut.ps1
```

Or run inline:

```powershell
$desktop = if ($env:OneDrive) { "$env:OneDrive\Desktop" } else { "$env:USERPROFILE\Desktop" }
$ws  = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut("$desktop\Hermes Gateway (Start).lnk")
$lnk.TargetPath      = "$env:LOCALAPPDATA\hermes\gateway-service\Hermes_Gateway.cmd"
$lnk.WorkingDirectory = "$env:LOCALAPPDATA\hermes\hermes-agent"
$lnk.WindowStyle     = 7   # minimised / hidden
$lnk.Description     = "Start Hermes Gateway"
$lnk.Save()
Write-Host "Shortcut created at $desktop"
```

### Important Notes

- **One bot token owner at a time.** Either Hermes gateway OR `@telegram-autopilot` can poll the bot — not both. Stop one before starting the other.
- **OAuth, not PAT.** GitHub Copilot's inference API requires an OAuth token (`gho_...`). PATs (`github_pat_...`) return "Personal Access Tokens are not supported". Use `gh auth login` via browser.
- **Corporate TLS proxy?** Python's `certifi` doesn't include corporate root CAs. Export them from Windows cert store and set `SSL_CERT_FILE` in Hermes `.env`.

### Non-blocking queue watcher

By default, polling the queue blocks the orchestrator while it waits. To stay
responsive, use one of these approaches:

**Option A — Hermes Overmind (built-in cron):**
Hermes schedules an internal cron job after writing the task. The cron polls
every 30 seconds and sends a Telegram notification when done — Hermes stays
free to chat in the meantime.

**Option B — Standalone watcher (any setup):**
Run `queue-watch.js` in a side terminal. It polls `.vscode-queue.json` every
10 seconds and sends a Telegram message when the task completes, then exits.

```bash
node queue-watch.js
# or custom interval/path:
node queue-watch.js --interval 5000 --queue /path/to/.vscode-queue.json
```

Requires the same `.telegram-config` (or env vars) as the MCP server.
Zero dependencies — pure Node.js.

---

## 7. Skills — Teaching the Worker

The worker has no built-in memory. Skills are markdown files that give it domain knowledge on demand.

### How it works

VS Code auto-scans `SKILL.md` frontmatter at startup and injects a `<skill>` summary block into every conversation. When the worker encounters a matching task, it reads the full file before executing.

**Zero extra token cost** — only frontmatter is injected automatically. Full content is read on demand.

### Where to put skills

Add a skills folder to your `.code-workspace`:
```json
{ "path": ".github/skills" }
```

> **Recommended:** `.github/skills/` inside your workspace — git-tracked, no tool dependency, works with VS Code out of the box.
>
> **Power users (Claude Code CLI too):** use `~/.claude/skills/` — one skill file works for both Copilot and Claude Code.

### Skill file format

```
.github/skills/
└── my-skill/
    └── SKILL.md
```

Minimal `SKILL.md`:
```yaml
---
name: my-skill
description: What this skill does. TRIGGER when user mentions X, Y, Z.
---

# My Skill

## Steps
1. Do this first
2. Then this
```

### Wiring to the worker

Add to your `copilot-instructions.md`:
```md
## Worker Rules
- Before any domain task → always read_file the matching SKILL.md first.
- Never rely on the system prompt summary alone.
```

**The golden rule:**
> Always spawn `@vscode-worker` from within the workspace session. Fresh window = no workspace = skills invisible.

---

## 🎮 Fun Fact

The architecture of this hybrid mode was heavily inspired by **StarCraft (SC2)** RTS mechanics.

The **Hermes Agent** acts as the *Command Center / Overmind* (handling high-level strategy, scouting, and global state), while the **VS Code worker** operates like an *SCV / Drone* (staying inside the local workspace base to execute the heavy macro work).

---

## License

[MIT](LICENSE)
