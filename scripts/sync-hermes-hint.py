#!/usr/bin/env python3
"""Synchronize the canonical Overmind prompt into Hermes runtime config.

Source:  <workspace>/.hermes.md (Git-tracked, portable)
Target:  %LOCALAPPDATA%/hermes/config.yaml -> agent.environment_hint

Only the environment_hint scalar is replaced. The remainder of config.yaml is
left byte-for-byte intact.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import yaml


WORKSPACE = Path(__file__).resolve().parent.parent
SOURCE = WORKSPACE / ".hermes.md"


def runtime_config() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise RuntimeError("LOCALAPPDATA is not set")
    return Path(local_app_data) / "hermes" / "config.yaml"


def desired_hint() -> str:
    if not SOURCE.is_file():
        raise RuntimeError(f"Canonical prompt not found: {SOURCE}")
    return SOURCE.read_text(encoding="utf-8").strip().replace(
        "<WORKSPACE>", str(WORKSPACE)
    )


def current_hint(config_path: Path) -> str:
    parsed = yaml.safe_load(config_path.read_text(encoding="utf-8-sig")) or {}
    agent = parsed.get("agent") or {}
    return agent.get("environment_hint") or ""


def sync(config_path: Path, hint: str) -> None:
    text = config_path.read_text(encoding="utf-8-sig")
    replacement = "  environment_hint: " + json.dumps(hint, ensure_ascii=False) + "\n"
    pattern = re.compile(
        r"(?ms)^  environment_hint: .*?(?=^  [A-Za-z_][A-Za-z0-9_-]*:|\Z)"
    )
    updated, count = pattern.subn(lambda _match: replacement, text, count=1)
    if count != 1:
        raise RuntimeError("Could not locate agent.environment_hint in config.yaml")

    temp_path = config_path.with_suffix(".yaml.tmp")
    temp_path.write_text(updated, encoding="utf-8")
    try:
        actual = current_hint(temp_path)
        if actual != hint:
            raise RuntimeError("Generated config did not preserve environment_hint exactly")
        temp_path.replace(config_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="verify without writing")
    args = parser.parse_args()

    config_path = runtime_config()
    if not config_path.is_file():
        raise RuntimeError(f"Hermes config not found: {config_path}")

    hint = desired_hint()
    if args.check:
        if current_hint(config_path) != hint:
            print("environment_hint is out of sync", file=sys.stderr)
            return 1
        print(f"environment_hint is synchronized ({len(hint)} chars)")
        return 0

    sync(config_path, hint)
    print(f"synchronized environment_hint from {SOURCE.name} ({len(hint)} chars)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"sync-hermes-hint: {exc}", file=sys.stderr)
        raise SystemExit(1)
