#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from pr_review_config import read_config, repo_root, tmp_root


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context-dir", required=True)
    args = parser.parse_args()

    root = repo_root(Path.cwd())
    allowed_root = tmp_root(root, read_config(root)).resolve()
    target = Path(args.context_dir).resolve()

    if target == allowed_root or allowed_root not in target.parents:
        raise ValueError(f"context-dir must be inside {allowed_root}")
    if not target.exists():
        print(f"already clean: {target}")
        return 0
    if not target.is_dir():
        raise ValueError(f"context-dir is not a directory: {target}")

    shutil.rmtree(target)
    print(f"removed: {target}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"cleanup-context failed: {exc}", file=sys.stderr)
        sys.exit(1)
