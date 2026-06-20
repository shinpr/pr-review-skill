#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from pr_review_config import load_context, posting_severities, read_config

POSTING_SEVERITIES = ("must", "should", "nit")


def finding_label(comment: dict[str, Any]) -> str:
    target = "PR"
    if "path" in comment:
        target = f"{comment.get('path')}:{comment.get('line')}"
    elif comment.get("paths"):
        target = ", ".join(str(path) for path in comment["paths"])
    return f"[{str(comment.get('severity', '')).upper()}] {comment.get('title', 'Untitled')} ({target})"


def note_for_moved(comment: dict[str, Any], reason: str) -> str:
    return f"{reason}: {finding_label(comment)}"


def split_comments(comments: list[dict[str, Any]], severities: set[str]) -> tuple[list[dict[str, Any]], list[str]]:
    kept: list[dict[str, Any]] = []
    notes: list[str] = []
    for comment in comments:
        severity = str(comment.get("severity", ""))
        if severity == "question":
            notes.append(note_for_moved(comment, "Moved unresolved question out of final findings"))
            continue
        if severity not in severities:
            notes.append(note_for_moved(comment, f"Moved non-posting {severity or 'unknown'} finding out of final findings"))
            continue
        kept.append(comment)
    return kept, notes


def normalize(review: dict[str, Any], severities: set[str]) -> dict[str, Any]:
    normalized = dict(review)
    inline, inline_notes = split_comments(list(review.get("inline_comments") or []), severities)
    overall, overall_notes = split_comments(list(review.get("overall_comments") or []), severities)
    notes = list(review.get("notes") or [])
    notes.extend(inline_notes)
    notes.extend(overall_notes)

    normalized["inline_comments"] = inline
    normalized["overall_comments"] = overall
    normalized["notes"] = notes
    normalized["verdict"] = "COMMENT" if inline or overall else "APPROVE"
    return normalized


def validate(path: Path) -> None:
    guard = Path(__file__).resolve().parent / "guard-plugin/scripts/require-final-json.py"
    proc = subprocess.run(["python3", str(guard), "--cli", str(path)], check=False, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())


def severity_counts(comments: list[dict[str, Any]]) -> dict[str, int]:
    return {severity: len([comment for comment in comments if comment.get("severity") == severity]) for severity in POSTING_SEVERITIES}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context-dir", required=True)
    parser.add_argument("--review-json", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    context_dir = Path(args.context_dir).resolve()
    context = load_context(context_dir)
    repo_root = Path(context["repo_root"])
    severities = posting_severities(read_config(repo_root))

    source = Path(args.review_json).resolve()
    review = json.loads(source.read_text())
    normalized = normalize(review, severities)

    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n")
    validate(out)

    comments = normalized["inline_comments"] + normalized["overall_comments"]
    print(
        json.dumps(
            {
                "review_json": str(out),
                "posting_severities": sorted(severities),
                "verdict": normalized["verdict"],
                "inline_comments": len(normalized["inline_comments"]),
                "overall_comments": len(normalized["overall_comments"]),
                **severity_counts(comments),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"normalize-review failed: {exc}", file=sys.stderr)
        sys.exit(1)
