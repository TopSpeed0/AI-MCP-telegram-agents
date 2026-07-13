# KB Skill — Local Knowledge Base

**Date:** July 2026  
**Status:** DRAFT — planning only, no changes implemented

---

## Problem

Skills today embed two types of knowledge that don't belong together:

1. **How to do something** — procedures, syntax, tool patterns → belongs in the skill
2. **What we know about our environment** — known issues, observed failures, infra quirks → currently scattered or lost

Environment knowledge is:
- Specific to this org (not portable)
- Grows over time (incidents, investigations, pitfall discoveries)
- Needed cross-skill (the same NFS issue might be relevant to linux-troubleshooting, workspace-netapp-code, and workspace-kvm-manager simultaneously)

Putting it inside individual skills creates duplication and drift.

---

## Idea

A local SQLite database (`kb.db`) acts as a queryable knowledge base for environment-specific findings.  
Each skill gets a one-liner hint: *"before investigating, check KB for known issues on this topic."*

The KB is:
- **Local only** — gitignored, never pushed
- **Queryable by keyword** — FTS5 full-text search
- **Structured** — each record has category, tags, date, severity, summary, detail
- **Agent-readable** — one skill (`KB`) exposes query/insert via simple interface

---

## Data Model

```sql
CREATE VIRTUAL TABLE kb USING fts5(
    id,           -- unique slug: "lperpproddb01-cross-site-nfs-2026-07"
    category,     -- netapp | kvm | linux | vmware | dns | general
    tags,         -- space-separated: "nfs latency migration cross-site"
    severity,     -- info | warning | critical
    title,        -- short description
    summary,      -- 2-3 sentences: what happened, root cause, fix
    detail,       -- full investigation notes (optional)
    source,       -- "session 6cdd966d July 13 2026" or "manual"
    date          -- YYYY-MM-DD
);
```

---

## KB Skill Interface

A skill named `KB` (or `kb-lookup`) exposes two operations:

### Query
```
kb search "nfs latency"         → returns matching records ranked by relevance
kb search "cross-site migration" --category kvm
kb search "lperpproddb01"
```

### Insert (agent adds new finding)
```
kb add --category netapp --tags "qos rows vserver" --severity warning \
       --title "-rows incompatible with -vserver in QoS commands" \
       --summary "Field -rows cannot be used with field -vserver. Remove -rows when using any field filter. Use -iterations instead."
```

---

## Example Records (seed data from today)

### Record 1
```
id:       lperpproddb01-cross-site-nfs-2026-07
category: kvm
tags:     migration cross-site nfs latency lperpproddb01 hrzlpolvmh06 hrzlpolvmh11
severity: critical
title:    lperpproddb01 cross-site NFS after KVM migration
summary:  hrzlpolvmh06 is physically on THC despite its HRZ-prefix name (lazy admin).
          hrzlpolvmh11 is on HRZ. On 2026-07-11 admin put hrzlpolvmh06 into Maintenance,
          oVirt migrated lperpproddb01 to hrzlpolvmh11 (HRZ). NetApp SVM svm_oracle_prod
          stays on THC → cross-site NFS over 2Gbps link → 25% throughput.
          Fix: migrate VM back to a THC host, or migrate SVM to HRZ.
source:   session 6cdd966d July 13 2026
date:     2026-07-13
```

### Record 2
```
id:       netapp-qos-rows-vserver-incompatible
category: netapp
tags:     qos statistics rows vserver volume filter ontap
severity: warning
title:    -rows flag incompatible with -vserver/-volume filters
summary:  "qos statistics volume latency show -vserver X -rows 5" fails with
          "Field -rows cannot be used with field -vserver".
          Remove -rows when using any field filter. Use -iterations N instead.
source:   session 6cdd966d July 13 2026
date:     2026-07-13
```

### Record 3
```
id:       cognyte-linux-ssh-no-publickey
category: linux
tags:     ssh publickey gssapi permission-denied linux mobaxterm
severity: critical
title:    raw ssh always fails on Cognyte Linux hosts
summary:  Cognyte Linux hosts reject all publickey and gssapi-keyex auth from this
          machine (exit 255, "Permission denied (publickey,gssapi-keyex,gssapi-with-mic)").
          ALWAYS use Invoke-MobaSSH via MobaXtermCredentials.psm1 — no exceptions.
source:   session 6cdd966d July 13 2026
date:     2026-07-13
```

---

## Skill Hint — What Gets Added to Each Skill (One Line)

When KB is ready, each relevant skill gets **one line added** to its PITFALLS section:

```markdown
> Before investigating, run: `kb search "<topic>"` to check for known issues.
```

Examples by skill:
- `workspace-netapp-code` → `kb search "ontap nfs latency"`
- `linux-troubleshooting` → `kb search "linux ssh <hostname>"`
- `workspace-kvm-manager` → `kb search "migration kvm <vm-name>"`
- `workspace-mobaxterm` → `kb search "ssh auth"`

This is the **only change** to existing skills. No env-specific data goes into skills.

---

## Agent Skill Factory Integration

The harvester (Phase 2) writes to the KB instead of patching skills directly:

```
Trial-and-error detected
    ↓
Is this env-specific? (hostname, IP, org-specific tool)
    → YES → insert into KB
    → NO  → patch the skill PITFALLS section (generic syntax rule)
```

**Rule of thumb:**
- Generic syntax error (`-rows` + `-vserver`) → patch the skill
- Env-specific finding (this VM is cross-site, this host rejects SSH) → insert into KB

---

## File Layout

```
Master_Work_Space/
  kb/
    kb.db           ← SQLite FTS5 database (gitignored)
    kb.py           ← CLI: kb search / kb add / kb list
    kb-schema.sql   ← schema definition (tracked in git)
    README.md       ← usage docs (tracked)
  docs/
    kb-skill.md     ← this document (tracked)
```

`.gitignore` additions:
```
kb/kb.db
```

---

## TODO

- [ ] Create `kb/kb-schema.sql`
- [ ] Write `kb/kb.py` — FTS5 search + insert CLI (< 100 lines)
- [ ] Create `KB` skill pointing to `kb.py`
- [ ] Seed with the 3 records above
- [ ] Add one-liner hint to: `workspace-netapp-code`, `linux-troubleshooting`, `workspace-kvm-manager`, `workspace-mobaxterm`
- [ ] Update `agent-skill-factory.md` — route env-specific findings to KB instead of skill patches
- [ ] Add `kb/kb.db` to `.gitignore`

---

## Open Questions

| # | Question | Recommendation |
|---|----------|---------------|
| 1 | SQLite vs plain markdown files? | SQLite — FTS5 is fast, agent can query without reading all files |
| 2 | Who inserts records — agent or user? | Both. Agent inserts candidates with `dry_run=true`; user confirms |
| 3 | Expiry / cleanup? | Add `expires` field — infra findings older than 1 year flagged for review |
| 4 | One DB or per-category? | One DB, filter by `category` field |

---

*Created: July 2026*
