# telegram-vscode-mcp

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

|                          | **telegram-vscode-mcp** (this)            | **chigwell/telegram-mcp**                   |
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
git clone https://github.com/<you>/telegram-vscode-mcp.git
cd telegram-vscode-mcp
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

## 6. Hybrid mode — Hermes + VS Code Copilot

For advanced setups, you can run **two agents** as a hybrid:

- **[Hermes Agent](https://hermes-agent.nousresearch.com/)** — always-on,
  owns the Telegram bot, handles general tasks (research, web, memory, cron)
- **VS Code Copilot** — workspace worker, handles coding tasks (file edits,
  terminal, language server, refactoring)

They communicate via a shared task queue file (`.vscode-queue.json`).

### Architecture

```
You (Telegram)
    │
    ▼
Hermes Agent (always-on)
    ├── General tasks → handles directly
    └── VS Code tasks → writes to .vscode-queue.json
                              │
                              ▼
                    vscode-queue MCP server (in VS Code)
                              │
                              ▼
                    vscode-worker agent (Copilot loop)
                              │
                              ▼
                    Result → .vscode-queue.json → Hermes → Telegram
```

### Quick Setup (one command after setup.js)

```bash
node setup-hybrid.js
```

The hybrid installer will:
1. Read your `.telegram-config` (from `setup.js`)
2. Check prerequisites (Hermes, `gh` CLI, Node 22+)
3. Ensure GitHub OAuth login (not PAT — Copilot API requires OAuth)
4. Configure Hermes model → GitHub Copilot (free with your Copilot subscription)
5. Inject the delegation instructions into Hermes config
6. Configure Telegram gateway with your bot token
7. Optionally fix corporate TLS proxy (exports Windows root CAs for Python)

### Manual Setup

1. Install [Hermes Agent](https://hermes-agent.nousresearch.com/docs/getting-started/installation):
   ```bash
   pip install hermes-agent
   ```

2. Login to GitHub with OAuth (PATs don't work with Copilot API):
   ```bash
   gh auth login -h github.com -p https -w
   ```

3. Configure Hermes model:
   ```bash
   hermes setup model
   # Select: GitHub Copilot (option 13)
   # Select: claude-sonnet-4.6 (or any available model)
   ```

4. Configure Telegram gateway:
   ```bash
   hermes setup gateway
   # Select: Telegram
   # Enter: your bot token (same as .telegram-config)
   # Enter: your chat ID as allowed user
   ```

5. Open this folder in VS Code. The `vscode-queue` MCP server is already
   registered in `.vscode/mcp.json`.

### Running the Hybrid

```bash
# Terminal: start Hermes gateway
hermes gateway start

# VS Code: open Copilot Chat → new panel → type:
@vscode-worker start worker

# Telegram: send a message to your bot!
```

To stop:
```bash
hermes gateway stop
# Close the worker chat panel in VS Code
```

### Important Notes

- **One bot token owner at a time.** Either Hermes gateway OR `@telegram-autopilot`
  can poll the bot — not both. Stop one before starting the other.
- **OAuth, not PAT.** GitHub Copilot's inference API requires an OAuth token (`gho_...`).
  PATs (`github_pat_...`) return "Personal Access Tokens are not supported". Use
  `gh auth login` via browser.
- **Corporate TLS proxy?** Python's `certifi` doesn't include corporate root CAs.
  Export them from Windows cert store and set `SSL_CERT_FILE` in Hermes `.env`.
  The hybrid installer handles this automatically.

### Queue protocol

Hermes writes tasks to `.vscode-queue.json`:

```json
{
  "id": "task-001",
  "task": "Fix the import error in src/utils.ts",
  "context": "Error: Cannot find module './helpers'",
  "status": "pending",
  "created": "2026-05-29T12:00:00Z",
  "updated": "2026-05-29T12:00:00Z"
}
```

Status flow: `pending` → `working` (Copilot picks it up) → `done` or `error`.

One task at a time. Hermes polls the file for completion, reads `result`,
and relays it to Telegram.

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
