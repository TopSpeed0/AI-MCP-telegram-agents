# Agent Skill Factory — Roadmap

Public-safe summary of what exists, what's proven, and what's still local-only.
This file is tracked in Git and must never contain hostnames, credentials,
session IDs, candidate output, or other internal/private data. For deep design
detail (recon data, phase history, noise-trap findings), see the local-only
design doc referenced in `.gitignore`.

## Completed & implemented

- **Phase 1 — Registry-driven pitfall detection (dry-run).** Matches known
  error patterns from a local registry against session logs and proposes
  pitfall fixes. Never patches a skill automatically.
- **Phase 2 — Config schema.** `agent_skill_factory` block added to the
  project's example config so the factory's settings are documented and
  versionable.
- **Phase 3a, Layer A — Mechanical diff engine (`scripts/diff_engine.py`).**
  Registry-free, deterministic detection: finds error → later-success command
  pairs (same tool, inter-block), normalizes noise (paths, modules, timestamps,
  IDs), and computes a token-level diff. No LLM involved. Covered by
  `scripts/test_diff_engine.py`, which checks for zero crashes, rejection of a
  known false-positive case, and presence of real signal across scanned local
  session logs.

## Needs validation before further claims

- **End-to-end integration.** The diff engine runs standalone; it is **not**
  yet wired into the harvester's CLI or into the production candidate-output
  pipeline used by Phase 1/2.
- **Agent-driven verification.** No agent (Hermes or otherwise) has yet run
  the diff engine's output through the IRON RULE fix-and-commit workflow
  end-to-end. Until that happens, "diff engine tested" means unit/acceptance
  tested in isolation — not production-verified.
- **Layer B (LLM interpretation).** Not built. Layer A only detects and
  computes diffs; drafting human-readable pitfall wording from a diff, and
  gating it behind user approval, is still future work.
- **Noise refinement.** The `Import-Module` adjacency filter and similar
  noise-reduction passes are partially tuned; further false-positive
  reduction is expected as more sessions are scanned.

## Local-only artifacts (never tracked here)

These exist as part of the working system but stay off Git because they
reference internal infrastructure, contain runtime output, or are
environment-specific:

- Local design/progress doc with full recon data and phase history.
- Error-pattern registry (references internal hostnames/paths).
- Generated candidate output from harvester/diff-engine runs.
- Any session logs, credentials, tokens, or user-specific configuration.

See `.gitignore` for the authoritative list of what stays local.
