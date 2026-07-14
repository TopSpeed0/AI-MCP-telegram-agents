---
name: agent-skill-factory
description: >
  Agent Skill Factory — harvest pitfalls from Claude Code JSONL session logs and
  turn them into skill fixes. TRIGGER when the user wants to: find recurring
  error→fix patterns in past sessions, auto-improve skills from real trial-and-error,
  run the skill-harvester, add a new pitfall to a skill, or work on the
  agent-skill-factory design. Repo capability lives in Master_Work_Space/scripts/.
tags: [devops, skills, automation, self-improvement]
---

# Agent Skill Factory

Harvests trial-and-error evidence from Claude Code session logs and converts it into
skill pitfall fixes. The factory *fixes your skills* using real failures observed in
`~/.claude/projects/*.jsonl`.

## Where everything lives

| Item | Path |
|------|------|
| Design doc (authoritative) | `Master_Work_Space/docs/agent-skill-factory.md` (gitignored until dev done) |
| Harvester script | `Master_Work_Space/scripts/skill-harvester.py` |
| Error registry | `Master_Work_Space/scripts/error-patterns.json` (gitignored — internal infra names) |
| Runtime output | `Master_Work_Space/.skill-candidates.json` (gitignored) |
| Skills that get fixed | `~/.claude/skills/<skill>/SKILL.md` (SOURCE — local git here) |

**Read the design doc first** for anything non-trivial — it has the full phase plan,
recon data, and the noise-trap findings.

## Core model

- **Skills live in `~/.claude/skills/` (source).** Fixes land here. Local git for rollback.
- **The factory lives in the Master_Work_Space Repo.** Capability ships with the repo.
- **Propagation: fix → git commit → run `sync-skills.py` → Hermes reads it.**
  `Start-Hermes.ps1` runs sync on startup anyway; the explicit sync just makes it immediate.

## Phase status (July 2026)

- **Phase 1 — DONE.** Registry-driven pitfall detection, dry-run. Passes acceptance:
  `--session 6cdd966d` → exactly 2 pitfalls, 0 false positives.
- **Phase 2 — DONE.** `agent_skill_factory` config schema in `.telegram-config.example`.
- **Phase 3 — DESIGNED, not built.** Diff-based generic detection (the real vision).
- **Phase 3a recon — DONE.** 79 sessions, 130 error→fix pairs. Signal confirmed.

## Running the harvester (Phase 1, dry-run)

```bash
cd "Master_Work_Space"
uv run python scripts/skill-harvester.py --session 6cdd966d   # single session
uv run python scripts/skill-harvester.py --last-n 15          # recent sessions
```
Output → `.skill-candidates.json`. **Dry-run never patches a skill.**

⚠️ `uv`'s Python is Windows-native — pass native `C:\...` paths, not MSYS `/c/...`,
to any script run via `uv run python` from the bash terminal.

## IRON RULE — git bracket around EVERY skill fix

Every skill edit (manual or harvester-driven) MUST be bracketed by git in
`~/.claude/skills/`:

1. **Before:** `cd ~/.claude/skills && git status --porcelain` — MUST be empty. If dirty, STOP.
2. **Apply the fix** to `~/.claude/skills/<skill>/SKILL.md`.
3. **After:** `git add <skill>/ && git commit -m "..."` then verify:
   `git status --porcelain` empty + `git log --oneline -1` shows the commit.
4. **Sync:** run `sync-skills.py` to propagate source → AppData mirror.

No skill edit is complete without a clean check before and a verified commit after.
This is what makes every change reversible.

## Phase 1 implementation findings (must survive any rewrite)

- **`working_cmd_scope` — the fix is NOT always a later call.** Two shapes:
  - `later_same_tool` (Case 1, ssh): fix runs in a separate later tool_use.
  - `same_block_or_later` (Case 2, `-rows`): failing cmd AND fix live in the SAME
    multi-line block. A naive "next success" heuristic grabs the wrong command.
- **Target-skill gating** — only emit a candidate if the pattern's `target_skill` was
  actually `Skill()`-loaded that session. Kills cross-domain false positives.
- **Dedup per `(pattern_id, target_skill)`** — one candidate per pattern+skill, not per occurrence.
- **Silent drops** — no locatable fix = no candidate. Precision over recall. Never fabricate.
- **Tools list is `["PowerShell","Bash"]`** — commands appear under both in JSONL.

## Phase 3 design (diff-based, the original vision)

- For ANY error→success pair, **diff the two commands**, turn the delta into a pitfall.
  Registry becomes optional fast-path; the log becomes source of truth. Self-expanding.
- **Layer A (mechanical diff, NO LLM):** generic error detection → pair match → normalize
  → `difflib` delta. Deterministic, cheap, runs freely.
- **Layer B (LLM interpretation):** only fires on candidates Layer A found. Drafts pitfall
  wording. Gated behind user approval.
- **Cadence: every 2 days** (`0 6 */2 * *`). LLM is expensive — empty cycles stay silent,
  zero token spend.

### Phase 3a recon findings (from real data — shape the code)
- 79 sessions → 288 failed commands → **130 error→fix pairs (45% rate)**. Enough signal.
- **New pitfall the registry never had:** `set -privilege diagnostic;` must prefix some
  ONTAP commands — auto-discoverable by diff. Proves the vision.
- **Noise trap 1 — sim=1.0 false pairs:** similarity must be a BAND `0.4 ≤ sim < 1.0`
  AND normalized diff must be non-empty. Empty diff = not a fix = reject.
- **Noise trap 2 — `Import-Module` re-imports:** path/module noise is the DOMINANT noise
  source, bigger than timestamps. Normalize paths/modules aggressively; filter path-only diffs.

## Pitfalls

- Never write pitfall text with server names / hostnames — rules must be GENERIC.
- Verify JSONL shape against real logs; don't trust the design doc's assumptions.
- Skill loads: `tool_use name=="Skill"`, arg key `input.skill`. Command text in
  `input.command` OR `input.cmd`. `tool_result.content` may be str OR list of `{type,text}`.
- `error-patterns.json` + `.skill-candidates.json` are gitignored — they reference internal infra.
