#!/usr/bin/env python3
"""
skill-harvester.py  --  Agent Skill Factory, Phase 1 (Pitfall Detection, dry-run only)

Reads Claude Code JSONL session logs, detects trial-and-error sequences where a
command failed with a known error signature and a corrected command succeeded,
cross-references the Skill() loaded in that session, and emits pitfall candidates
to .skill-candidates.json.

DRY-RUN ONLY: this script NEVER writes/patches/modifies any skill file. No git.
No side effects other than writing the candidates JSON output file.

All paths come from config or CLI args -- nothing hardcoded.

Usage:
    python skill-harvester.py --dry-run --last-n 5
    python skill-harvester.py --dry-run --session 6cdd966d
    python skill-harvester.py --dry-run --projects-dir <dir> --registry <file> --out <file>
"""
import argparse
import glob
import json
import os
import sys
from pathlib import Path

# ---- default paths (overridable via CLI / config) -------------------------
HOME = Path(os.path.expanduser("~"))
DEFAULTS = {
    "projects_dir": str(HOME / ".claude" / "projects"),
    "registry": str(Path(__file__).resolve().parent / "error-patterns.json"),
    "out": str(Path(__file__).resolve().parent.parent / ".skill-candidates.json"),
    "skills_dir": str(HOME / ".claude" / "skills"),
}


def load_config(path):
    """Optional config file (agent_skill_factory block). Falls back to DEFAULTS."""
    cfg = dict(DEFAULTS)
    if path and os.path.isfile(path):
        try:
            raw = json.load(open(path, encoding="utf-8"))
            block = raw.get("agent_skill_factory", raw)
            src = block.get("sources", {})
            cfg["projects_dir"] = os.path.expanduser(src.get("claude_projects_dir", cfg["projects_dir"]))
            cfg["skills_dir"] = os.path.expanduser(src.get("skills_dir", cfg["skills_dir"]))
            cfg["out"] = os.path.expanduser(block.get("output_candidates", cfg["out"]))
        except Exception as e:
            print(f"[warn] could not parse config {path}: {e}", file=sys.stderr)
    return cfg


def iter_events(jsonl_path):
    """Yield (line_index, parsed_event) for each valid JSONL line."""
    with open(jsonl_path, encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            try:
                yield i, json.loads(line)
            except json.JSONDecodeError:
                continue


def extract_session(jsonl_path):
    """
    Parse a session into ordered tool calls, a result map, and loaded skills.
    Returns dict: {order: [(line, id, tool, cmd)], results: {id: text}, skills: set}
    """
    order = []
    results = {}
    skills = set()
    for i, ev in iter_events(jsonl_path):
        content = ev.get("message", {}).get("content")
        if not isinstance(content, list):
            continue
        for b in content:
            if not isinstance(b, dict):
                continue
            btype = b.get("type")
            if btype == "tool_use":
                name = b.get("name")
                inp = b.get("input", {}) or {}
                cmd = inp.get("command") or inp.get("cmd") or ""
                if name == "Skill":
                    sk = inp.get("skill")
                    if sk:
                        skills.add(sk)
                order.append((i, b.get("id"), name, str(cmd)))
            elif btype == "tool_result":
                txt = b.get("content")
                if isinstance(txt, list):
                    txt = " ".join(
                        str(x.get("text", x)) for x in txt if isinstance(x, dict)
                    )
                results[b.get("tool_use_id")] = str(txt)
    return {"order": order, "results": results, "skills": skills}


def cmd_matches(cmd, contains, not_contains):
    for c in contains:
        if c not in cmd:
            return False
    for nc in not_contains:
        if nc in cmd:
            return False
    return True


def find_working_cmd(sess, fail_line, fail_tool, pat):
    """
    Locate the corrected command per the pattern's working_cmd_scope.
      - same_block_or_later: check the failing cmd's own multi-line block first,
        then later same-tool calls.
      - later_same_tool: only later same-tool calls.
    Returns the matched working command string, or None.
    """
    needle = pat["working_cmd_pattern"]
    scope = pat.get("working_cmd_scope", "later_same_tool")

    # same-block: the failing tool_use command may itself contain the fix
    if scope == "same_block_or_later":
        for (ln, _id, tool, cmd) in sess["order"]:
            if ln == fail_line and needle in cmd:
                return needle  # fix present in same block

    # later same-tool successful call
    for (ln, eid, tool, cmd) in sess["order"]:
        if ln <= fail_line or tool != fail_tool:
            continue
        if needle in cmd:
            res = sess["results"].get(eid, "")
            failed_again = ("cannot be used" in res) or ("Permission denied" in res)
            if not failed_again:
                return cmd.strip().splitlines()[0][:200] if cmd else needle
    return None


def detect_pitfalls(sess, registry):
    """Match registry error signatures against session results. Returns candidates."""
    candidates = []
    seen = set()
    for (ln, eid, tool, cmd) in sess["order"]:
        res = sess["results"].get(eid, "")
        if not res:
            continue
        for pat in registry["patterns"]:
            if tool not in pat.get("tools", []):
                continue
            sig = pat["error_pattern"]
            sig_alt = pat.get("error_pattern_alt")
            if sig not in res and not (sig_alt and sig_alt in res):
                continue
            if not cmd_matches(cmd, pat.get("failed_cmd_contains", []),
                               pat.get("failed_cmd_not_contains", [])):
                continue
            # require the target skill to have been loaded (avoids false positives)
            if pat["target_skill"] not in sess["skills"]:
                continue
            working = find_working_cmd(sess, ln, tool, pat)
            if not working:
                continue
            key = (pat["id"], pat["target_skill"])
            if key in seen:
                continue
            seen.add(key)
            failed_first_line = cmd.strip().splitlines()[0][:200] if cmd else ""
            candidates.append({
                "type": "pitfall",
                "pattern_id": pat["id"],
                "skill": pat["target_skill"],
                "severity": pat.get("severity", "warning"),
                "failed_cmd": failed_first_line,
                "working_cmd": working,
                "error_msg": sig,
                "proposed_patch": pat["proposed_patch"],
            })
    return candidates


def resolve_sessions(cfg, args):
    files = []
    if args.session:
        files = glob.glob(os.path.join(cfg["projects_dir"], "**", f"{args.session}*.jsonl"),
                          recursive=True)
    else:
        files = glob.glob(os.path.join(cfg["projects_dir"], "**", "*.jsonl"),
                          recursive=True)
        files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        if args.last_n:
            files = files[:args.last_n]
    return files


def main():
    ap = argparse.ArgumentParser(description="Agent Skill Factory harvester (Phase 1, dry-run)")
    ap.add_argument("--dry-run", action="store_true", default=True,
                    help="print/emit candidates only, never write skills (always on in Phase 1)")
    ap.add_argument("--session", help="session id prefix, e.g. 6cdd966d")
    ap.add_argument("--last-n", type=int, default=5, help="scan N most recent sessions")
    ap.add_argument("--projects-dir", help="override claude projects dir")
    ap.add_argument("--registry", help="override error-patterns.json path")
    ap.add_argument("--out", help="override candidates output path")
    ap.add_argument("--config", help="optional config json with agent_skill_factory block")
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.projects_dir:
        cfg["projects_dir"] = os.path.expanduser(args.projects_dir)
    if args.registry:
        cfg["registry"] = os.path.expanduser(args.registry)
    if args.out:
        cfg["out"] = os.path.expanduser(args.out)

    if not os.path.isfile(cfg["registry"]):
        print(f"[error] registry not found: {cfg['registry']}", file=sys.stderr)
        return 2
    registry = json.load(open(cfg["registry"], encoding="utf-8"))

    sessions = resolve_sessions(cfg, args)
    if not sessions:
        print(f"[error] no sessions found under {cfg['projects_dir']}", file=sys.stderr)
        return 2

    all_candidates = []
    for jf in sessions:
        sess = extract_session(jf)
        cands = detect_pitfalls(sess, registry)
        for c in cands:
            c["source_session"] = os.path.basename(jf)
        all_candidates.extend(cands)

    # DRY-RUN GUARD: only ever write the candidates file; never touch skills.
    with open(cfg["out"], "w", encoding="utf-8") as fh:
        json.dump(all_candidates, fh, indent=2, ensure_ascii=False)

    print(f"[dry-run] scanned {len(sessions)} session(s)")
    print(f"[dry-run] {len(all_candidates)} pitfall candidate(s) -> {cfg['out']}")
    for c in all_candidates:
        print(f"  - {c['skill']}: {c['pattern_id']} ({c['severity']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
