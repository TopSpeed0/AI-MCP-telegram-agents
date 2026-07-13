# Agent Skill Factory

**Date:** July 2026  
**Status:** DRAFT — no changes implemented yet

---

## Problem

Hermes learns from trial and error but never persists that learning.  
Skills are created manually — nothing is automatic.  
This feature makes Hermes watch agent logs and auto-generate skills from observed patterns.

---

## Idea

Hermes watches Claude Code and Copilot CLI logs, detects recurring task patterns not yet covered by a skill, drafts a `SKILL.md`, and pushes it to git.

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
1. **Task extraction** — extract all `user` messages that are action requests (not questions)
2. **Tool pattern detection** — identify recurring tool call sequences
3. **Success detection** — session ended without error in last message
4. **Domain classification** — cluster by keywords (NetApp/ONTAP, VMware, DNS, CyberArk, etc.)
5. **Dedup against existing skills** — compare keywords against `.skills-index.txt`
6. **Output JSON candidates** — list of candidates with domain, triggers, sample task, tool sequence

### Output format
```json
[
  {
    "domain": "netapp-snapmirror",
    "trigger_words": ["snapmirror", "resync", "dr"],
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

## Code Skeleton — `skill-harvester.js`

```javascript
#!/usr/bin/env node
// skill-harvester.js — reads Claude Code sessions and identifies skill candidates
const fs = require('fs');
const path = require('path');
const os = require('os');

const CLAUDE_PROJECTS = path.join(os.homedir(), '.claude', 'projects');
const SKILLS_INDEX = path.join(os.homedir(), '.claude', 'skills', '.skills-index.txt');

function readJsonlFile(filePath, maxLines = 200) {
  const content = fs.readFileSync(filePath, 'utf8');
  return content.split('\n')
    .filter(l => l.trim())
    .slice(-maxLines)
    .map(l => { try { return JSON.parse(l); } catch { return null; } })
    .filter(Boolean);
}

function extractTasks(events) {
  return events
    .filter(e => e?.message?.role === 'user')
    .map(e => {
      const content = e.message.content;
      if (typeof content === 'string') return content;
      if (Array.isArray(content))
        return content.filter(c => c?.type === 'text').map(c => c.text).join(' ');
      return null;
    })
    .filter(t => t && t.length > 20); // skip short confirmations
}

function extractToolSequence(events) {
  return events
    .filter(e => e?.message?.role === 'assistant')
    .flatMap(e => {
      const content = e.message.content;
      if (!Array.isArray(content)) return [];
      return content.filter(c => c?.type === 'tool_use').map(c => c.name);
    });
}

function classifyDomain(text) {
  const rules = [
    { keywords: ['snapmirror','ontap','svm','volume','nfs','cifs','netapp'], domain: 'netapp' },
    { keywords: ['vmware','vcenter','vm','powercli','vsphere'],              domain: 'vmware' },
    { keywords: ['proxmox','pve','qemu','lxc'],                             domain: 'proxmox' },
    { keywords: ['dns','active directory','ad','ldap','dc'],                domain: 'active-directory' },
    { keywords: ['cyberark','pvwa','certificate','ssl'],                    domain: 'cyberark' },
    { keywords: ['jenkins','pipeline','build'],                             domain: 'jenkins' },
    { keywords: ['kubernetes','openshift','ocp','pod','namespace'],         domain: 'openshift' },
  ];
  const lower = text.toLowerCase();
  for (const r of rules) {
    if (r.keywords.some(k => lower.includes(k))) return r.domain;
  }
  return 'general';
}

async function main() {
  const args = process.argv.slice(2);
  const dryRun = args.includes('--dry-run');
  const lastN = parseInt(args.find(a => a.startsWith('--last-n='))?.split('=')[1] || '10');

  // Load existing skill names to avoid duplicates
  const existingSkills = new Set();
  if (fs.existsSync(SKILLS_INDEX)) {
    fs.readFileSync(SKILLS_INDEX, 'utf8').split('\n')
      .forEach(line => existingSkills.add(line.split(':')[0].trim()));
  }

  const candidates = [];
  for (const dir of fs.readdirSync(CLAUDE_PROJECTS)) {
    const dirPath = path.join(CLAUDE_PROJECTS, dir);
    if (!fs.statSync(dirPath).isDirectory()) continue;

    const jsonlFiles = fs.readdirSync(dirPath)
      .filter(f => f.endsWith('.jsonl'))
      .map(f => ({ name: f, mtime: fs.statSync(path.join(dirPath, f)).mtime }))
      .sort((a, b) => b.mtime - a.mtime)
      .slice(0, lastN)
      .map(f => path.join(dirPath, f.name));

    for (const file of jsonlFiles) {
      const events = readJsonlFile(file);
      const tasks = extractTasks(events);
      const toolSeq = extractToolSequence(events);
      if (tasks.length === 0) continue;
      const domain = classifyDomain(tasks.join(' '));
      candidates.push({ dir, file: path.basename(file), tasks, toolSeq, domain });
    }
  }

  // Group by domain, filter by min_occurrences and existing skills
  const byDomain = {};
  for (const c of candidates) {
    if (!byDomain[c.domain]) byDomain[c.domain] = [];
    byDomain[c.domain].push(c);
  }

  const results = Object.entries(byDomain)
    .filter(([domain, items]) => items.length >= 2)
    .filter(([domain]) => !existingSkills.has(`workspace-${domain}`))
    .map(([domain, items]) => ({
      domain,
      occurrences: items.length,
      sample_tasks: items.slice(0, 2).flatMap(i => i.tasks.slice(0, 1)),
      tool_sequence: [...new Set(items.flatMap(i => i.toolSeq))].slice(0, 5),
      suggested_skill_name: `workspace-${domain}`
    }));

  if (dryRun) {
    console.log(JSON.stringify(results, null, 2));
  } else {
    const outPath = path.join(__dirname, '..', '.skill-candidates.json');
    fs.writeFileSync(outPath, JSON.stringify(results, null, 2));
    console.log(`Wrote ${results.length} candidates to ${outPath}`);
  }
}

main().catch(console.error);
```

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
