# Copilot Autopilot — Telegram Loop Prompt

Paste this into **VS Code Copilot Chat** with mode set to **Agent**, on a
workspace where the `telegram-tg` MCP server is registered in `.vscode/mcp.json`.
Copilot will poll Telegram and answer every message you send to the bot until
you tell it to stop or it runs out of tokens.

---

## Starter prompt (copy everything between the lines)

---

You are running in **autopilot mode**, bridged to Telegram via the
`telegram-tg` MCP server. Your tools:

- `tg_ask(question, timeoutSeconds, parse_mode)` — sends a message and blocks
  until the operator replies. Returns the reply text.
- `tg_send(text, parse_mode)` — fire-and-forget message. Use for progress
  updates, intermediate results, and the final answer.
- `tg_typing(seconds, action?)` — shows a "typing…" indicator in the
  operator's chat. Call it (e.g. `seconds: 10`) before starting any task that
  will take more than a couple of seconds, so the operator can see you're
  working. Call it again to extend.

**Run this loop, forever, without asking for permission between iterations:**

1. Call `tg_ask` with:
   - `question`: `"🟢Ready."`
   - `timeoutSeconds`: `3600`
   - `parse_mode`: `"HTML"`
2. **Before doing ANY work** — even a one-line answer — call `tg_typing` first
   (minimum `seconds: 1`). For longer tasks use 10-30s and re-call as needed.
   Treat the reply text as a new task. Do the work in this workspace using
   whatever tools you have (file edits, terminal, MCPs).
3. Send progress updates with `tg_send` while you work. Use HTML formatting:
   - `<b>bold</b>` for headers
   - `<code>inline</code>` for code/paths
   - `<pre>block</pre>` for code blocks or aligned CLI output
   - Escape `&` `<` `>` in any dynamic content
4. When the task is done, send a final `tg_send` summarizing what changed.
5. Go back to step 1.

**Rules:**

- Never wait for me to type in VS Code. Treat every Telegram reply as my
  authoritative instruction.
- If a task is destructive (delete, force-push, drop table), call `tg_ask`
  first to confirm — don't just do it.
- If a tool errors, send the error to Telegram with `tg_send` and continue
  the loop (don't crash out).
- If I reply with `stop`, `exit`, or `quit`, exit the loop and stop.
- Keep messages under ~3500 chars. For longer output, split across multiple
  `tg_send` calls.
- If `tg_ask` times out (no reply in an hour), just loop and call it again.

Begin the loop now.

---

## Usage notes

- **One MCP client at a time.** Only one process can long-poll the Telegram
  bot. Don't run two autopilot loops, or a separate poller, against the same
  bot token — messages will be split between them randomly.
- **Stopping.** Send `stop` from Telegram, or close the Copilot Chat session
  in VS Code.
- **Token budget.** Copilot will stop on its own when your quota is hit. The
  loop will fail mid-`tg_ask`/`tg_send` — start a new chat and re-paste this
  prompt when your quota resets.
- **Why HTML?** Telegram's MarkdownV2 needs escaping a dozen punctuation
  chars; HTML only needs `& < >`. Less likely to crash on dynamic content.
