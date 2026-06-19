#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pr_review_config import (
    DEFAULT_CONFIG,
    DEFAULT_QUALITY,
    config_path,
    print_json,
    quality_path,
    read_config,
    repo_root,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve() if args.repo_root else repo_root(Path.cwd())
    cfg_path = config_path(root)
    created: list[str] = []
    if not cfg_path.exists():
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(DEFAULT_CONFIG.read_text())
        created.append(str(cfg_path))

    config = read_config(root)
    q_path = quality_path(root, config)
    if not q_path.exists():
        q_path.parent.mkdir(parents=True, exist_ok=True)
        q_path.write_text(DEFAULT_QUALITY.read_text())
        created.append(str(q_path))

    print_json({"config_path": str(cfg_path), "quality_path": str(q_path), "created": created})
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"bootstrap-config failed: {exc}", file=sys.stderr)
        sys.exit(1)
