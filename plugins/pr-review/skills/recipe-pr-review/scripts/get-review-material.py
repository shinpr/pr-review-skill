#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from pr_review_config import load_context, output_language, posting_severities, quality_path, read_config, run

SKILL_DIR = Path(__file__).resolve().parents[1]


def configured_guidance_paths(root: Path, config: dict, changed_files: list[str]) -> list[Path]:
    names = config.get("guidance", {}).get("include_files", ["AGENTS.md", "CLAUDE.md"])
    candidates: set[Path] = set()
    for name in names if isinstance(names, list) else []:
        path = root / str(name)
        if path.exists():
            candidates.add(path)
    for rel in changed_files:
        current = root / rel
        for parent in [current.parent, *current.parents]:
            if parent != root and root not in parent.parents:
                continue
            for name in ("AGENTS.md", "CLAUDE.md"):
                path = parent / name
                if path.exists():
                    candidates.add(path)
            if parent == root:
                break
    return sorted(candidates)


def print_file(path: Path) -> None:
    if path.exists():
        print(f"--- {path} ---")
        print(path.read_text(errors="replace"))


def diff_for_path(diff_text: str, target_path: str) -> str:
    chunks: list[str] = []
    current: list[str] = []
    include = False
    header_re = re.compile(r"^diff --git a/(.*) b/(.*)$")
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            if include and current:
                chunks.extend(current)
            current = [line]
            match = header_re.match(line)
            include = bool(match and target_path in {match.group(1), match.group(2)})
            continue
        if current:
            current.append(line)
    if include and current:
        chunks.extend(current)
    return "\n".join(chunks) + ("\n" if chunks else "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context-dir", required=True)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--path")
    parser.add_argument("--ref", choices=["base", "head"], default="head")
    args = parser.parse_args()

    context_dir = Path(args.context_dir)
    context = load_context(context_dir)
    root = Path(context["repo_root"])
    config = read_config(root)
    changed_files = context["changed_files"]

    if args.kind == "summary":
        summary = {
            "owner": context["owner"],
            "repo": context["repo"],
            "number": context["number"],
            "url": context["pr"]["url"],
            "title": context["pr"]["title"],
            "base": context["pr"]["baseRefName"],
            "head": context["pr"]["headRefName"],
            "head_sha": context["pr"]["headRefOid"],
            "changed_files": changed_files,
            "changed_file_details": context.get("changed_file_details", []),
            "additions": context["pr"]["additions"],
            "deletions": context["pr"]["deletions"],
            "status_checks": context["pr"].get("statusCheckRollup", []),
            "posting_severities": sorted(posting_severities(config)),
            "output_language": output_language(config),
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    elif args.kind == "quality":
        print_file(quality_path(root, config))
    elif args.kind == "conventions":
        print_file(SKILL_DIR / "references/code-review-conventions.md")
    elif args.kind == "comments":
        print_file(context_dir / "issue-comments.json")
        print_file(context_dir / "review-comments.json")
        print_file(context_dir / "reviews.json")
    elif args.kind == "guidance":
        for path in configured_guidance_paths(root, config, changed_files):
            print_file(path)
    elif args.kind == "diff":
        if args.path:
            print(diff_for_path((context_dir / "diff.patch").read_text(errors="replace"), args.path))
        else:
            print_file(context_dir / "diff.patch")
    elif args.kind == "file":
        if not args.path:
            raise ValueError("--path is required for kind=file")
        ref = context["pr"]["baseRefOid"] if args.ref == "base" else context["pr"]["headRefOid"]
        print(run(["git", "show", f"{ref}:{args.path}"], root))
    else:
        raise ValueError(f"unknown kind: {args.kind}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"get-review-material failed: {exc}", file=sys.stderr)
        sys.exit(1)
