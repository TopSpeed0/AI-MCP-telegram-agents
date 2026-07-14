#!/usr/bin/env python3
"""
diff_engine.py -- Agent Skill Factory, Phase 3a (mechanical diff engine, NO LLM).

Generic, registry-FREE pitfall detection. For any command that errored and was
followed by a token-similar sibling that succeeded, compute the command diff and
emit a candidate describing exactly what changed to fix it.

Deterministic. No LLM. Dry-run: never patches a skill.

Recon findings (baked in — see docs/agent-skill-factory.md "Phase 3a Recon"):
  * Similarity is a BAND, not a floor:  0.4 <= sim < 1.0
  * The normalized diff MUST be non-empty (empty diff = retry, not a fix -> reject)
  * Path/module noise is the DOMINANT noise source -> normalize aggressively,
    and reject pairs whose ONLY change is a path/module.

Reuses the session parsing already proven in skill-harvester.py.
"""
import re
import difflib

# ---- generic error markers (config-driven list, not per-error signatures) ----
ERROR_MARKERS = [
    "error", "permission denied", "cannot", "invalid", "not recognized",
    "exit code 255", "failed", "no such", "unexpected", "denied",
]

SIM_LOW = 0.40      # inclusive floor
SIM_HIGH = 1.00     # EXCLUSIVE ceiling (1.0 == identical retry, reject)
PAIR_WINDOW = 8     # how many later same-tool calls to consider


def normalize(cmd: str) -> str:
    """
    Aggressively strip noise so diffs reflect real command changes, not paths/times.
    Path/module collapsing is priority #1 per recon.
    """
    c = cmd.lower()
    # module imports -> single token (kills the Import-Module re-import false pairs)
    c = re.sub(r'import-module\s+"[^"]+"', 'import-module MOD', c)
    c = re.sub(r'import-module\s+\S+', 'import-module MOD', c)
    # windows + posix paths -> PATH
    c = re.sub(r'[a-z]:\\[^\s"]+', 'PATH', c)
    c = re.sub(r'"[a-z]:\\[^"]+"', 'PATH', c)
    c = re.sub(r'/[^\s"]+', 'PATH', c)
    # timestamps / dates
    c = re.sub(r'\d{1,2}/\d{1,2}/\d{2,4}', 'DATE', c)
    c = re.sub(r'\d{1,2}:\d{2}(:\d{2})?', 'TIME', c)
    # guids / long hex ids
    c = re.sub(r'[0-9a-f]{8}[-_][0-9a-f]{4}.*?(?=["\s]|$)', 'ID', c)
    c = re.sub(r'\s+', ' ', c).strip()
    return c


def tokens(cmd: str):
    return set(re.findall(r'[\w\-]+', normalize(cmd)))


def similarity(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)  # jaccard on normalized tokens


def is_error(text: str) -> bool:
    tl = text.lower()
    return any(m in tl for m in ERROR_MARKERS)


def is_success(text: str) -> bool:
    return bool(text) and not is_error(text)


def command_delta(failed: str, working: str):
    """
    Token/flag-level delta on NORMALIZED commands.
    Returns dict {removed, added} or None if the normalized diff is empty
    (empty == not a real fix -> reject, per recon noise-trap #1).
    """
    nf, nw = normalize(failed), normalize(working)
    if nf == nw:
        return None  # only difference was noise (path/time) -> not a fix
    fa, wa = nf.split(), nw.split()
    sm = difflib.SequenceMatcher(a=fa, b=wa, autojunk=False)
    removed, added = [], []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op in ("replace", "delete"):
            removed.extend(fa[i1:i2])
        if op in ("replace", "insert"):
            added.extend(wa[j1:j2])
    if not removed and not added:
        return None
    return {"removed": removed, "added": added}


def _first_line(cmd: str) -> str:
    return cmd.strip().splitlines()[0][:200] if cmd.strip() else ""


def detect_diff_pitfalls(sess, tools=("PowerShell", "Bash")):
    """
    Registry-FREE, INTER-block mechanical detection. sess from extract_session():
      {order: [(line, id, tool, cmd)], results: {id: text}, skills: set}

    Scope (Phase 3a build finding — Path 1): mechanical pairing works ONLY across
    separate tool_use blocks, where each command has its own result. Intra-block
    fixes (fix inside the same multi-line block) are NOT resolvable mechanically —
    one block emits one merged result blob with no per-sub-command signal — and are
    deferred to Layer B (LLM). See docs/agent-skill-factory.md.

    Returns a list of inter-block diff candidate dicts.
    """
    order = sess["order"]
    results = sess["results"]
    candidates = []
    seen = set()

    for idx, (ln, eid, tool, cmd) in enumerate(order):
        if not cmd or tool not in tools:
            continue
        res = results.get(eid, "")
        if not res or not is_error(res):
            continue

        # INTER-block: best token-similar later same-tool SUCCESS in the window
        best = None
        for j in range(idx + 1, min(idx + 1 + PAIR_WINDOW, len(order))):
            ln2, eid2, tool2, cmd2 = order[j]
            if tool2 != tool or not cmd2:
                continue
            if not is_success(results.get(eid2, "")):
                continue
            s = similarity(cmd, cmd2)
            if best is None or s > best[0]:
                best = (s, cmd2)

        if not best:
            continue
        sim, working = best

        # BAND guard (recon noise-trap #1): 0.4 <= sim < 1.0
        if not (SIM_LOW <= sim < SIM_HIGH):
            continue

        delta = command_delta(cmd, working)
        if delta is None:   # empty normalized diff = retry/path-only, not a fix
            continue

        loaded = list(sess["skills"])
        skill = loaded[0] if len(loaded) == 1 else None

        key = (normalize(cmd), tuple(delta["removed"]), tuple(delta["added"]))
        if key in seen:
            continue
        seen.add(key)

        candidates.append({
            "type": "diff_pitfall",
            "mode": "inter",
            "skill": skill,
            "candidate_skills": loaded,
            "similarity": round(sim, 2),
            "failed_cmd": _first_line(cmd),
            "working_cmd": _first_line(working),
            "error_excerpt": res.strip()[:160],
            "delta_removed": delta["removed"],
            "delta_added": delta["added"],
        })
    return candidates
