#!/usr/bin/env python3
"""
test_diff_engine.py -- Phase 3a acceptance test (INTER-block scope, Path 1).

The mechanical engine is registry-FREE and INTER-block only. What it must prove:
  1. It finds REAL inter-block error->fix pairs across sessions (signal exists).
  2. It REJECTS the known false positive: the Outlook-mail call at line 162 of
     session 6cdd966d must NOT be emitted as a fix for the -rows error.
  3. Zero crashes across all 79 sessions.

Note: the two Phase 1 pitfalls (raw-ssh, -rows) are INTRA-block and are explicitly
out of mechanical scope — they are deferred to Layer B (LLM). This test does NOT
expect the mechanical engine to rediscover them; that would require faking a pass.
"""
import os
import sys
import glob
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

_hv = os.path.join(HERE, "skill-harvester.py")
_spec = importlib.util.spec_from_file_location("skill_harvester", _hv)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
extract_session = _mod.extract_session

from diff_engine import detect_diff_pitfalls

PROJECTS = os.path.join(os.path.expanduser("~"), ".claude", "projects")
SESSION_6C = os.path.join(
    PROJECTS,
    "C--Users-ybohadana-OneDrive---COGNYTE-Documents-code-Cognyte-Workspace-linux-troubleshooting",
    "6cdd966d-5029-434f-b760-dc63043b0f1c.jsonl",
)


def main():
    total = 0
    outlook_fp = False
    crashes = 0
    example = None

    for path in glob.glob(os.path.join(PROJECTS, "**", "*.jsonl"), recursive=True):
        try:
            sess = extract_session(path)
            cands = detect_diff_pitfalls(sess)
        except Exception as e:
            crashes += 1
            print(f"CRASH on {os.path.basename(path)}: {e}")
            continue
        total += len(cands)
        for c in cands:
            wl = c["working_cmd"].lower()
            if "outlook" in wl or "outlooktools" in wl:
                outlook_fp = True
            if example is None and c["delta_removed"] and c["delta_added"]:
                example = c

    # focused false-positive check on the specific 6cdd966d session
    sess6 = extract_session(SESSION_6C)
    c6 = detect_diff_pitfalls(sess6)
    outlook_in_6c = any("outlook" in c["working_cmd"].lower() for c in c6)

    print(f"sessions scanned           : {len(glob.glob(os.path.join(PROJECTS, '**', '*.jsonl'), recursive=True))}")
    print(f"total inter-block candidates: {total}")
    print(f"crashes                    : {crashes}")
    print(f"Outlook false positive (any): {outlook_fp}")
    print(f"Outlook FP in 6cdd966d      : {outlook_in_6c}")
    if example:
        print("\nsample candidate:")
        print(f"  [sim {example['similarity']}] skill={example['skill']}")
        print(f"  FAIL : {example['failed_cmd'][:80]}")
        print(f"  WORK : {example['working_cmd'][:80]}")
        print(f"  -rm  : {example['delta_removed']}")
        print(f"  +add : {example['delta_added']}")

    print("\n" + "=" * 50)
    ok = (crashes == 0) and (not outlook_in_6c) and (total > 0)
    print(f"crashes==0        : {crashes == 0}")
    print(f"no Outlook FP (6c): {not outlook_in_6c}")
    print(f"found signal (>0) : {total > 0}")
    print("\nACCEPTANCE:", "PASS ✓" if ok else "FAIL ✗")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
