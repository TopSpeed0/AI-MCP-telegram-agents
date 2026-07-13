# Agent Skill Factory

**Date:** July 2026  
**Status:** DRAFT — no changes implemented yet

---

## Problem

Hermes learns from trial and error but **never persists that learning**.  
Skills are created manually — nothing is automatic.  

Every time Claude Code runs a session, it produces evidence of:
- Commands that **failed** (wrong syntax, incompatible flags, missing module)
- The **corrected command** that worked immediately after
- Exactly which skill was loaded at that moment

That evidence sits in JSONL logs and is never used again.  
Next session — same agent, same tool, same mistake.

---

## Primary Use Case — Pitfall Detection (Most Valuable)

> **Find trial-and-error sequences → extract the working syntax → patch the existing skill with a `⚠️ PITFALL` entry.**

This is the **highest-value action** the harvester can take.  
It does not create a new skill — it improves an existing one with real, observed failure data.

### Example — July 13 2026

**Pattern detected in `linux-troubleshooting` session:**

| Step | What happened |
|------|---------------|
| Skill loaded | `workspace-mobaxterm` |
| Failed attempt | `ssh -o BatchMode=yes lperpproddb01` → `Permission denied (publickey,gssapi-keyex)` |
| Working command | `Invoke-MobaSSH -ConnectionName "lperpproddb01"` |
| Skill already says | "NEVER use raw ssh with password" |
| Gap | Rule was too narrow — agent assumed keyless ssh was OK |
| Fix | Add pitfall: *raw ssh always fails on Cognyte hosts, even without password* |

**Second pattern in same session:**

| Step | What happened |
|------|---------------|
| Skill loaded | `workspace-netapp-code` |
| Failed attempt | `qos statistics volume latency show -vserver X -rows 5` → `Error: Field "-rows" cannot be used with field "-vserver"` |
| Working command | `statistics volume show -vserver X -volume Y` (no `-rows`) |
| Skill already says | nothing about `-rows` |
| Fix | Add pitfall: *`-rows` is incompatible with `-vserver`/`-volume` filters — remove it* |

Both fixes are **patches to existing skills**, not new skills.

---

## Secondary Use Case — New Skill Detection

When a session uses **no existing skill** for a recurring task domain → propose a new skill candidate.  
Threshold: `min_occurrences: 2` (must appear in at least 2 separate sessions).

---

## Idea

Hermes watches Claude Code and Copilot CLI logs, detects two types of patterns:
1. **Trial-and-error** within a loaded skill → patch the skill with the discovered pitfall
2. **Recurring tasks** with no skill coverage → propose a new skill candidate

---

## Existing Data Sources

| Source | Path | Format | Contents |
|--------|------|--------|----------|
| Claude Code sessions | `~/.claude/projects/<name>/*.jsonl` | JSONL (one event per line) | user messages, tool calls, results |
| Copilot queue | `.copilot-queue.json` | JSON | task + result per task |
| Claude queue | `.claude-queue.json` | JSON | task + result per task |
| VS Code workspaceStorage | `~/AppData/Roaming/Code/User/workspaceStorage/*/state.vscdb` | SQLite | Copilot chat history |

> **Note:** VS Code workspaceStorage is SQLite and hard to query reliably. Excluded from Phase 1.

### JSONL event structure (Claude Code)
```json
{"message": {"role": "user", "content": "resync SVM-DR on NADR..."}}
{"message": {"role": "assistant", "content": [{"type": "tool_use", "name": "Bash", "input": {...}}]}}
{"message": {"role": "user", "content": [{"type": "tool_result", "content": "..."}]}}
```

### Current skills in `~/.claude/skills/`
21 skills exist today (workspace-*, dc-health-check, dns-audit, humanizer, etc.)  
All created manually — zero auto-generated skills.

---

## Proposed Architecture

```
[Copilot / Claude Code sessions]
          ↓  JSONL logs + queue files
    skill-harvester.js   (new script)
          ↓  reads logs, detects patterns, outputs JSON candidates
    Hermes cron job   (every N hours)
          ↓  reads candidates, drafts SKILL.md via LLM
    ~/.claude/skills/<new-skill>/SKILL.md
          ↓  git commit + push
    TopSpeed0/Master_Work_Space
          ↓  Telegram notification to user
```

---

## New `.telegram-config` Field

Field name: **`agent_skill_factory`**

```json
{
  "agent_skill_factory": {
    "enabled": true,
    "schedule": "0 */6 * * *",
    "sources": {
      "claude_projects_dir": "~/.claude/projects",
      "queue_files": ["agents.copilot.queue", "agents.claude.queue"]
    },
    "output_skills_dir": "~/.claude/skills",
    "git_auto_push": true,
    "min_occurrences": 2,
    "dry_run": true
  }
}
```

| Field | Description |
|-------|-------------|
| `enabled` | Feature on/off |
| `schedule` | Cron expression for how often to run |
| `sources.claude_projects_dir` | Where to scan JSONL sessions |
| `sources.queue_files` | References to queue paths already defined in `agents` |
| `output_skills_dir` | Where to write new skills |
| `git_auto_push` | Auto-push to git after skill creation |
| `min_occurrences` | Minimum times a pattern must appear before generating a skill |
| `dry_run` | When true: print candidates only, do not write files (recommended default) |

---

## `skill-harvester.js` — What It Does

### Input
- JSONL files from `~/.claude/projects` (last N sessions)
- Queue files (Copilot + Claude) — all completed tasks

### Algorithm

**Step 1 — Pitfall Detection (primary)**
1. Find `tool_use` events where the result contains error keywords (`error`, `permission denied`, `cannot`, `invalid`, `field X cannot be used with field Y`, etc.)
2. Look at the next 1–3 calls of the **same tool** — if one succeeds, that's the corrected syntax
3. Check which `Skill(...)` was loaded in this session → that's the skill to patch
4. Output: `{ type: "pitfall", skill: "workspace-netapp-code", failed_cmd: "...", working_cmd: "...", error_msg: "..." }`

**Step 2 — New Skill Detection (secondary)**
1. Extract all user task messages
2. Classify domain using triggers from installed skills (dynamic, not hardcoded)
3. If no skill was loaded for that domain AND task appears in 2+ sessions → propose new skill candidate
4. Output: `{ type: "new_skill", domain: "...", sample_tasks: [...], tool_sequence: [...] }`

### Output format
```json
[
  {
    "type": "pitfall",
    "skill": "workspace-mobaxterm",
    "failed_cmd": "ssh -o BatchMode=yes lperpproddb01 ...",
    "working_cmd": "Invoke-MobaSSH -ConnectionName 'lperpproddb01' -Command '...'",
    "error_msg": "Permission denied (publickey,gssapi-keyex)",
    "proposed_patch": "⚠️ PITFALL: raw ssh always fails on Cognyte Linux hosts even without password. Use Invoke-MobaSSH."
  },
  {
    "type": "new_skill",
    "domain": "netapp",
    "occurrences": 3,
    "sample_tasks": ["resync SVM-DR on NADR...", "..."],
    "tool_sequence": ["Bash(Get-NcSnapmirror)", "Bash(Initialize-NcSnapmirrorUpdate)"],
    "suggested_skill_name": "workspace-netapp-snapmirror"
  }
]
```

---

## Hermes Cron Job — Full Flow

```
1. Run skill-harvester.js → read JSON candidates
2. For each candidate:
   a. Verify no existing skill covers the same domain/name
   b. Send to LLM: "generate a full SKILL.md from these candidates"
   c. Write to ~/.claude/skills/<name>/SKILL.md
   d. git add + commit + push
3. Send Telegram summary: "Created N new skills: ..."
```

---

## `skill-harvester.js` — Design Decisions

### Directories (from config, not hardcoded)

The harvester reads all paths from the `agent_skill_factory` config block — nothing is hardcoded:

| Config key | Purpose | Default |
|------------|---------|---------|
| `sources.claude_projects_dir` | Scan JSONL sessions here | `~/.claude/projects` |
| `sources.skills_dir` | Load installed skills for dynamic classification | `~/.claude/skills` |
| `output_skills_dir` | Write new skill candidates here | `~/.claude/skills` |

> `sources.skills_dir` doubles as both the classification source AND the dedup check — if a skill already exists there, don't propose it again.

### Dynamic Domain Classification (no hardcoded rules)

`classifyDomain()` must **not** contain a static keyword list.  
Instead, at startup the harvester scans `sources.skills_dir`, reads each `SKILL.md` frontmatter, and extracts the `triggers` field to build rules on the fly:

```
~/.claude/skills/
  workspace-netapp-code/SKILL.md   → triggers: [ontap, snapmirror, svm, nfs]
  linux-troubleshooting/SKILL.md   → triggers: [ssh, dmesg, systemd, linux]
  workspace-mobaxterm/SKILL.md     → triggers: [mobaxterm, moba, ssh credentials]
  ...
```

Result at runtime:
```javascript
const rules = loadSkillsDir(config.sources.skills_dir);
// → [{ skill: 'workspace-netapp-code', keywords: ['ontap','snapmirror',...] }, ...]
```

This means the harvester is **automatically aware of whatever skills are installed** — no manual sync needed when a new skill is added.

### What to extract from SKILL.md

SKILL.md frontmatter already has everything needed:
```yaml
---
name: workspace-netapp-code
triggers:         # ← primary classification source
  - ontap
  - snapmirror
  - svm
description: ...  # ← fallback if no triggers field
---
```

If `triggers` is missing, fall back to splitting the `description` into keywords (first 10 words, lowercase).

### Composite Workflow Detection

When a session loads **3+ distinct skills**, treat it as a `workflow` candidate, not a single-domain candidate.  
Threshold for workflow candidates: `min_occurrences_override: 1` (workflows are by definition rare/unique).

### Signals to extract per session

1. First user message (the task) — main text for classification
2. All `Skill(...)` tool calls — which skills were loaded
3. `mcp__ccd_session__mark_chapter` titles — strongest signal (explicit chapter = task boundary)
4. Project directory name — encodes VS Code workspace name, use as secondary domain hint
5. Tool sequence (PowerShell / Bash / mcp\_\_*) — for the `tool_sequence` output field

---

## TODO

### Phase 1 — skill-harvester.js
- [ ] Write `scripts/skill-harvester.js` (skeleton above)
- [ ] Add `linux-troubleshooting` keyword rule to `classifyDomain()`
- [ ] Add composite workflow detection (3+ skill loads → `type: workflow`)
- [ ] Add chapter marker extraction (`mcp__ccd_session__mark_chapter` → task summary)
- [ ] Use project dir name as secondary domain hint
- [ ] Drop VS Code `chatSessions` from sources (confirmed stale/irrelevant)
- [ ] Test with `--dry-run --last-n=5`
- [ ] Validate output JSON against real session (6cdd966d… confirmed as test case)

### Phase 2 — `.telegram-config` schema
- [ ] Add `agent_skill_factory` section to `.telegram-config.example`
- [ ] Update `workspace-master-workspace` skill with new schema docs

### Phase 3 — Hermes cron integration
- [ ] Hermes cron job reads `.skill-candidates.json`
- [ ] LLM drafts SKILL.md from candidates
- [ ] Write to `~/.claude/skills/<name>/SKILL.md`
- [ ] git commit + push
- [ ] Telegram notification

### Phase 4 — git
- [ ] `skill-harvester.js` committed to Master_Work_Space
- [ ] `.skill-candidates.json` added to `.gitignore`
- [ ] `.telegram-config.example` updated

---

## Real Session Validation — July 13 2026

Tested the data sources against a real Claude Code session run today to confirm what the harvester can and cannot see.

### Session Summary

**File:** `~/.claude/projects/C--Users-ybohadana-OneDrive---COGNYTE-Documents-code-Cognyte-Workspace-linux-troubleshooting/6cdd966d-5029-434f-b760-dc63043b0f1c.jsonl`  
**Size:** 1,028 KB — 198 events  
**Task:** Investigate `lperpproddb01` performance regression after 2026-07-11 security patch (DB operating at ~25% of normal throughput)

**Skills loaded:**
1. `/linux-troubleshooting` — run remote diagnostics
2. `/workspace-netapp-code` — check NetApp SVM latency
3. `/workspace-mobaxterm` — SSH to host via MobaXterm credential store
4. `/outlook-mail` — draft summary email to KVM manager + DBA manager

**Tool sequence observed:**
```
Skill(linux-troubleshooting)
Skill(workspace-netapp-code)
mcp__ccd_session__mark_chapter  ← Claude Code chapter marker
PowerShell × 15                 ← SSH via MobaXterm module + NetApp ONTAP queries
Write / Edit                    ← MEMORY.md + draft mail body
Skill(workspace-mobaxterm)      ← loaded mid-session when SSH needed
Read(SKILL.md)                  ← workspace-mobaxterm self-read
```

### Root Cause Found (collaboration: user + Hermes + Claude Code)

- `hrzlpolvmh06` naming is misleading — it is actually on the **THC site** (config saved from old naming convention by lazy admin)
- `hrzlpolvmh11` is on **HRZ site**
- On 2026-07-11 19:18, `admin@internal-authz` put `hrzlpolvmh06` into Maintenance for a host upgrade
- oVirt auto-migrated `lperpproddb01` → `hrzlpolvmh11` (HRZ) while **the NetApp SVM (`svm_oracle_`) stays on THC**
- Result: **cross-site NFS over the 2 Gbps inter-site link** instead of local 10 Gbps — explains the ~25% throughput
- The host upgrade on `hrzlpolvmh06` **failed** (pcp-oracle-conf task) — so the VM was never migrated back

### Data Source Validation

| Source | Expected | Result |
|--------|----------|--------|
| `~/.claude/projects/*/JSONL` | ✅ Today's work | ✅ **CONFIRMED** — 1MB session, fully readable |
| VS Code `chatSessions/*.jsonl` | Today's Copilot chat | ❌ **STALE** — newest file is 06/02, not used today |
| Copilot `.copilot-queue.json` | Delegated tasks | N/A — this session ran directly in Claude Code |

**Conclusion:** VS Code `workspaceStorage/chatSessions` should be **dropped entirely** — it only captures Copilot Inline Chat, not Claude Code sessions. Claude Code JSONL is the correct and only source needed for Phase 1.

### What the Harvester Would Detect (Domain Classification Gaps)

The current `classifyDomain()` skeleton would classify this session as `netapp` (svm, nfs, ontap keywords present).  
**Problem:** the real domain is `cross-site-vm-migration` + `linux-troubleshooting` — a **multi-skill composite** pattern.  

Improvements needed:
1. **Composite workflow detection** — sessions with 3+ distinct skill loads should be classified differently from single-domain sessions
2. **`linux` / `ssh` keyword rule** missing from `classifyDomain()` — add `{ keywords: ['ssh', 'linux', 'bash', 'systemd', 'dmesg', 'nfs mountstats'], domain: 'linux-troubleshooting' }`
3. **Chapter markers** (`mcp__ccd_session__mark_chapter`) are a strong signal — if Claude Code marks a chapter, that's the task summary; harvester should prioritize those strings
4. **Project dir → workspace hint** — the project dir name encodes the VS Code workspace path (`Workspace-linux-troubleshooting`). Use this as a secondary domain signal.

### Multi-Skill Pattern — New Skill Candidate Type

Today's session reveals a pattern not covered by the original design:  
**"Investigation + SSH + Storage + Mail" = cross-domain composite skill**

This is a **workflow pattern** rather than a domain skill. The harvester should output a second candidate type:

```json
{
  "type": "workflow",
  "name": "infra-incident-investigation",
  "trigger": "performance regression after change",
  "steps": ["load linux-troubleshooting", "SSH via mobaxterm", "check storage latency", "draft mail"],
  "skills_used": ["linux-troubleshooting", "workspace-mobaxterm", "workspace-netapp-code", "outlook-mail"],
  "occurrences": 1,
  "min_occurrences_override": 1
}
```

Workflow candidates require only 1 occurrence (unique by nature) vs. the `min_occurrences: 2` default for domain skills.

---

## Pitfall Detection — Full Spec

This section defines exactly what the harvester needs to detect, and what the fix looks like.  
Each entry is a **ground truth case** derived from a real session — the harvester must produce this output.

---

### Case 1 — raw SSH fails on Cognyte Linux hosts

**Session:** `6cdd966d` — `linux-troubleshooting` workspace — July 13 2026

**How to detect:**
```
SIGNAL:  tool_use(PowerShell) result contains "Permission denied (publickey,gssapi-keyex)"
         AND the same session has Skill("workspace-mobaxterm") loaded

PATTERN: failed_tool == "PowerShell"
         failed_cmd contains "ssh " and NOT "Invoke-MobaSSH"
         error contains "Permission denied" OR "exit code 255"
         next successful call to same tool: cmd contains "Invoke-MobaSSH"
```

**Failed command:**
```powershell
ssh -o ConnectTimeout=8 -o BatchMode=yes lperpproddb01 "hostnamectl; uptime"
# → Exit code 255 / Permission denied (publickey,gssapi-keyex,gssapi-with-mic)
```

**Working command (found 14 calls later):**
```powershell
Import-Module "...\MobaXtermCredentials.psm1" -Force
Invoke-MobaSSH -ConnectionName "lperpproddb01" -Command "hostnamectl; uptime"
```

**Target skill:** `workspace-mobaxterm` — `~/.claude/skills/workspace-mobaxterm/SKILL.md`

**Existing rule in skill:**
> "NEVER use `sshpass`, `plink`, or raw `ssh` with password — use `Invoke-MobaSSH`."

**Gap:** Rule said "with password" — agent assumed keyless/BatchMode ssh was OK.

**Patch to add:**
```
⚠️ PITFALL: raw `ssh` always fails on Cognyte Linux hosts — even without a password.
`ssh -o BatchMode=yes host` → Permission denied (publickey,gssapi-keyex,gssapi-with-mic)
The hosts don't accept SSH agent keys or publickey from this machine.
ALWAYS use Invoke-MobaSSH — no exceptions, not even for a quick hostname check.
```

---

### Case 2 — `-rows` flag incompatible with `-vserver`/`-volume` filter

**Session:** `6cdd966d` — `linux-troubleshooting` workspace — July 13 2026

**How to detect:**
```
SIGNAL:  tool_use(PowerShell) result contains 'Field "-rows" cannot be used with field'
         AND the same session has Skill("workspace-netapp-code") loaded

PATTERN: failed_tool == "PowerShell"
         failed_cmd contains "qos statistics" AND "-rows" AND "-vserver"
         error: 'Field "-rows" cannot be used with field "-vserver"'
         next successful call: same qos command WITHOUT -rows flag
```

**Failed command:**
```powershell
A1k-ssh -Command "qos statistics volume latency show -vserver svm_oracle_prod -volume PRD_db -iterations 2 -rows 5"
# → Error: Field "-rows" cannot be used with field "-vserver".
```

**Working command (found in same session):**
```powershell
A1k-ssh -Command "statistics volume show -vserver svm_oracle_prod -volume PRD_db"
# → success
```

**Target skill:** `workspace-netapp-code` — `~/.claude/skills/workspace-netapp-code/SKILL.md`

**Existing rule in skill:** nothing about `-rows`.

**Patch to add:**
```
⚠️ PITFALL: `-rows` cannot be combined with `-vserver` or `-volume` field filters.
`qos statistics volume latency show -vserver X -rows 5` → "Field -rows cannot be used with field -vserver"
Remove `-rows` whenever you use any field filter (-vserver, -volume, -node).
Use `-iterations N` for repeated sampling instead.
```

---

## Harvester Detection Logic — Error Pattern Registry

The harvester maintains a registry of error signatures → skill to patch:

```json
[
  {
    "error_pattern": "Permission denied (publickey,gssapi-keyex)",
    "tool": "PowerShell",
    "cmd_pattern": "ssh ",
    "not_cmd_pattern": "Invoke-MobaSSH",
    "target_skill": "workspace-mobaxterm",
    "severity": "critical"
  },
  {
    "error_pattern": "Field \"-rows\" cannot be used with field",
    "tool": "PowerShell",
    "cmd_pattern": "qos statistics",
    "target_skill": "workspace-netapp-code",
    "severity": "warning"
  }
]
```

> **This registry is bootstrapped from real cases.** Every new pitfall the harvester finds gets added here automatically (after user approval).

---

## Open Questions

| # | Question | Recommendation |
|---|----------|---------------|
| 1 | VS Code workspaceStorage — worth adding? | Phase 2 only if there's demand |
| 2 | LLM-generated skill quality — approve before push? | `dry_run: true` as default until quality is proven |
| 3 | `min_occurrences` threshold | 2 — enough to confirm it's not a one-off |
| 4 | Who decides the skill name? | LLM suggests, can override in config |

---

## Files in Git

| File | Repo | Status |
|------|------|--------|
| `scripts/skill-harvester.js` | Master_Work_Space | **new** |
| `.telegram-config.example` | Master_Work_Space | update — add `agent_skill_factory` |
| `docs/agent-skill-factory.md` | Master_Work_Space | **new** (this document) |
| `.skill-candidates.json` | Master_Work_Space | **gitignored** (runtime output) |

---

*Created: July 2026*
