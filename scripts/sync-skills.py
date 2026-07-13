"""
sync-skills.py
Compares ~/.claude/skills/ (source of truth) against
~\AppData\Local\hermes\skills\ (mirror) and copies any changed/new SKILL.md files.
Designed to run as a Hermes cron job every few minutes.
Prints a diff summary — empty output = nothing changed (cron stays silent).
"""

import os
import shutil
import hashlib
from pathlib import Path

SOURCE = Path.home() / ".claude" / "skills"
MIRROR = Path(os.environ["LOCALAPPDATA"]) / "hermes" / "skills"


def sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except Exception:
        return ""


def sync():
    if not SOURCE.exists():
        print(f"[sync-skills] SOURCE not found: {SOURCE}")
        return

    updated = []
    added = []

    for src_skill_md in SOURCE.rglob("SKILL.md"):
        # Relative path from source root, e.g. devops/jira-cognyte/SKILL.md
        rel = src_skill_md.relative_to(SOURCE)
        dst_skill_md = MIRROR / rel

        src_hash = sha256(src_skill_md)
        dst_hash = sha256(dst_skill_md)

        if src_hash != dst_hash:
            dst_skill_md.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_skill_md, dst_skill_md)

            # Also sync any sibling files (references/, templates/, assets/)
            src_dir = src_skill_md.parent
            dst_dir = dst_skill_md.parent
            for sibling in src_dir.rglob("*"):
                if sibling.is_file() and sibling != src_skill_md:
                    sib_rel = sibling.relative_to(src_dir)
                    dst_sib = dst_dir / sib_rel
                    if sha256(sibling) != sha256(dst_sib):
                        dst_sib.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(sibling, dst_sib)

            skill_name = src_skill_md.parent.name
            if dst_hash == "":
                added.append(skill_name)
            else:
                updated.append(skill_name)

    if added:
        print(f"[sync-skills] NEW skills synced: {', '.join(added)}")
    if updated:
        print(f"[sync-skills] UPDATED skills synced: {', '.join(updated)}")
    # If nothing changed — silent (cron won't send a message)


if __name__ == "__main__":
    sync()
