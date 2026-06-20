#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from pr_review_config import gh_api_paginated, load_context, posting_severities, read_config

SEVERITY_RANK = {"nit": 0, "question": 1, "should": 2, "must": 3}


def run(args: list[str], cwd: Path, input_text: str | None = None) -> str:
    proc = subprocess.run(
        args,
        cwd=cwd,
        input=input_text,
        check=False,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    return proc.stdout


def marker(kind: str, key: str, body: str) -> str:
    digest = hashlib.sha256(body.encode()).hexdigest()[:16]
    return f"<!-- pr-review:v1 kind={kind} key={key} hash={digest} -->"


def marker_prefix(marker_text: str) -> str:
    return marker_text.split("hash=", 1)[0]


def existing_url(comments: list[dict], marker_text: str) -> str | None:
    prefix = marker_prefix(marker_text)
    for comment in comments:
        body = comment.get("body") or ""
        if marker_text in body or prefix in body:
            return comment.get("html_url")
    return None


def post_issue_comment(context: dict, body: str, cwd: Path) -> str | None:
    owner = context["owner"]
    repo = context["repo"]
    number = context["number"]
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump({"body": body}, fh, ensure_ascii=False)
        payload_path = fh.name
    try:
        out = run(["gh", "api", f"/repos/{owner}/{repo}/issues/{number}/comments", "--method", "POST", "--input", payload_path], cwd)
    finally:
        Path(payload_path).unlink(missing_ok=True)
    data = json.loads(out)
    return data.get("html_url")


def text_value(comment: dict, field: str) -> str:
    value = comment.get(field)
    return value.strip() if isinstance(value, str) else ""


def postable_comments(review: dict, severities: set[str]) -> tuple[list[dict], list[dict]]:
    inline = dedupe_inline_comments([comment for comment in review["inline_comments"] if comment["severity"] in severities])
    overall = [comment for comment in review["overall_comments"] if comment["severity"] in severities]
    return inline, overall


def richer_comment(left: dict, right: dict) -> dict:
    left_score = sum(1 for field in ("evidence", "failure_scenario", "suggested_fix") if left.get(field))
    right_score = sum(1 for field in ("evidence", "failure_scenario", "suggested_fix") if right.get(field))
    return right if right_score > left_score else left


def merge_inline_comment(existing: dict, incoming: dict) -> dict:
    existing_rank = SEVERITY_RANK[existing["severity"]]
    incoming_rank = SEVERITY_RANK[incoming["severity"]]
    base = incoming if incoming_rank > existing_rank else existing
    if incoming_rank == existing_rank:
        base = richer_comment(existing, incoming)
    merged = dict(base)
    other = existing if base is incoming else incoming
    for field in ("evidence", "failure_scenario", "suggested_fix"):
        if not merged.get(field) and other.get(field):
            merged[field] = other[field]
    if other.get("body") and other.get("body") != merged.get("body"):
        merged["body"] = f"{merged['body']}\n\nAdditional reviewer note: {other['body']}"
    return merged


def dedupe_inline_comments(comments: list[dict]) -> list[dict]:
    merged: dict[tuple, dict] = {}
    for comment in comments:
        key = (
            comment["path"],
            comment["line"],
            comment["side"],
            text_value(comment, "title"),
            text_value(comment, "failure_scenario"),
        )
        merged[key] = merge_inline_comment(merged[key], comment) if key in merged else comment
    return list(merged.values())


def severity_counts(comments: list[dict]) -> dict[str, int]:
    return {severity: len([c for c in comments if c["severity"] == severity]) for severity in ("must", "should", "question", "nit")}


def target_text(comment: dict) -> str:
    if "path" in comment:
        return f"`{comment['path']}:{comment['line']}`"
    paths = comment.get("paths") or []
    return ", ".join(f"`{path}`" for path in paths) if paths else "PR"


def inline_body(comment: dict) -> str:
    parts = [f"**{comment['severity'].upper()}: {comment['title']}**", "", comment["body"]]
    structured = [
        ("Evidence", text_value(comment, "evidence")),
        ("Failure scenario", text_value(comment, "failure_scenario")),
        ("Suggested fix", text_value(comment, "suggested_fix")),
    ]
    for label, value in structured:
        if value:
            parts.extend(["", f"**{label}**: {value}"])
    return "\n".join(parts)


def inline_key(comment: dict, commit_id: str) -> str:
    parts = [
        commit_id,
        comment["path"],
        str(comment["line"]),
        comment["side"],
        text_value(comment, "title"),
        text_value(comment, "failure_scenario"),
    ]
    digest = hashlib.sha256("\n".join(parts).encode()).hexdigest()[:16]
    return f"{commit_id}:{comment['path']}:{comment['line']}:{comment['side']}:{digest}"


def overall_body(review: dict, severities: set[str], inline_urls: dict[str, str]) -> str:
    inline, overall = postable_comments(review, severities)
    all_findings = inline + overall
    counts = severity_counts(all_findings)
    lines = [
        f"## Agent code review: {review['verdict']}",
        "",
        f"posting severities: {', '.join(sorted(severities)) if severities else 'none'}",
        f"must: {counts['must']} / should: {counts['should']} / question: {counts['question']} / nit: {counts['nit']}",
        "",
    ]
    if review["verdict"] == "APPROVE":
        lines.extend(["No findings matched the review criteria.", ""])
        changed_files = review.get("inspected", {}).get("changed_files") or []
        if changed_files:
            lines.extend(["### Checked files", ""])
            lines.extend(f"- `{path}`" for path in changed_files)
            lines.append("")
        quality_coverage = review.get("quality_coverage") or []
        if quality_coverage:
            lines.extend(["### Quality coverage", ""])
            for item in quality_coverage:
                evidence = item.get("evidence_checked") or []
                evidence_text = "; ".join(str(value) for value in evidence)
                lines.append(f"- `{item.get('criterion')}` on {item.get('changed_surface')}: {evidence_text}")
            lines.append("")
        notes = review.get("notes") or []
        if notes:
            lines.extend(["### Review notes", ""])
            lines.extend(f"- {note}" for note in notes)
            lines.append("")
        return "\n".join(lines).rstrip()

    lines.extend(["### Findings", ""])
    for index, comment in enumerate(all_findings, start=1):
        details = ""
        if "path" in comment:
            url = inline_urls.get(inline_key(comment, review["commit_id"]))
            details = f"  \n   Details: [inline comment]({url})" if url else ""
        lines.append(f"{index}. [{comment['severity'].upper()}] {comment['title']}  \n   Target: {target_text(comment)}{details}")
    if overall:
        lines.extend(["", "<details>", "<summary>Overall findings</summary>", ""])
        for comment in overall:
            lines.extend([f"### [{comment['severity'].upper()}] {comment['title']}", "", f"Target: {target_text(comment)}", "", comment["body"], ""])
        lines.append("</details>")
    return "\n".join(lines)


def post_pull_review(context: dict, comments: list[dict], cwd: Path) -> None:
    owner = context["owner"]
    repo = context["repo"]
    number = context["number"]
    payload = {"commit_id": context["pr"]["headRefOid"], "event": "COMMENT", "comments": comments}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(payload, fh, ensure_ascii=False)
        payload_path = fh.name
    try:
        run(["gh", "api", f"/repos/{owner}/{repo}/pulls/{number}/reviews", "--method", "POST", "--input", payload_path], cwd)
    finally:
        Path(payload_path).unlink(missing_ok=True)


def post_single_inline_fallback(context: dict, comment: dict, marker_text: str, cwd: Path) -> str | None:
    owner = context["owner"]
    repo = context["repo"]
    number = context["number"]
    payload = {
        "body": f"{inline_body(comment)}\n\n{marker_text}",
        "commit_id": context["pr"]["headRefOid"],
        "path": comment["path"],
        "line": comment["line"],
        "side": comment["side"],
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(payload, fh, ensure_ascii=False)
        payload_path = fh.name
    try:
        try:
            out = run(["gh", "api", f"/repos/{owner}/{repo}/pulls/{number}/comments", "--method", "POST", "--input", payload_path], cwd)
        finally:
            Path(payload_path).unlink(missing_ok=True)
        return json.loads(out).get("html_url")
    except Exception as exc:
        print(f"inline comment API failed for {comment['path']}:{comment['line']}; posting issue-comment fallback: {exc}", file=sys.stderr)
        fallback = f"Inline comment fallback for `{comment['path']}:{comment['line']}`\n\n{inline_body(comment)}\n\n{marker_text}"
        return post_issue_comment(context, fallback, cwd)


def post_inline(context: dict, review: dict, cwd: Path, existing_comments: dict[str, list[dict]], severities: set[str], dry_run: bool) -> dict[str, str]:
    urls: dict[str, str] = {}
    pending: list[tuple[dict, str, str]] = []
    batch_comments: list[dict] = []
    normalized_inline, _ = postable_comments(review, severities)
    commit_id = context["pr"]["headRefOid"]
    for comment in normalized_inline:
        key = inline_key(comment, commit_id)
        marker_text = marker("inline", key, comment["body"])
        existing = existing_url(existing_comments["review"], marker_text) or existing_url(existing_comments["issue"], marker_text)
        if existing:
            urls[key] = existing
            continue
        pending.append((comment, key, marker_text))
        batch_comments.append({"body": f"{inline_body(comment)}\n\n{marker_text}", "path": comment["path"], "line": comment["line"], "side": comment["side"]})
    if dry_run or not pending:
        return urls
    try:
        post_pull_review(context, batch_comments, cwd)
        refreshed = gh_api_paginated(f"/repos/{context['owner']}/{context['repo']}/pulls/{context['number']}/comments", cwd)
        for _comment, key, marker_text in pending:
            posted = existing_url(refreshed, marker_text)
            if posted:
                urls[key] = posted
    except Exception as exc:
        print(f"batch inline review failed; posting inline fallbacks individually: {exc}", file=sys.stderr)
        for comment, key, marker_text in pending:
            posted = post_single_inline_fallback(context, comment, marker_text, cwd)
            if posted:
                urls[key] = posted
    return urls


def post_overall(context: dict, review: dict, cwd: Path, issue_comments: list[dict], severities: set[str], inline_urls: dict[str, str], dry_run: bool) -> str | None:
    inline, overall = postable_comments(review, severities)
    if review["verdict"] != "APPROVE" and not inline and not overall:
        print("warning: COMMENT review has no postable findings; run normalize-review.py before posting", file=sys.stderr)
        return None
    body = overall_body({**review, "commit_id": context["pr"]["headRefOid"]}, severities, inline_urls)
    key = f"{context['pr']['headRefOid']}:overall"
    marker_text = marker("overall", key, body)
    existing = existing_url(issue_comments, marker_text)
    if existing or dry_run:
        return existing
    return post_issue_comment(context, f"{body}\n\n{marker_text}", cwd)


def load_existing_comments(context: dict, cwd: Path) -> dict[str, list[dict]]:
    owner = context["owner"]
    repo = context["repo"]
    number = context["number"]
    return {
        "review": gh_api_paginated(f"/repos/{owner}/{repo}/pulls/{number}/comments", cwd),
        "issue": gh_api_paginated(f"/repos/{owner}/{repo}/issues/{number}/comments", cwd),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context-dir", required=True)
    parser.add_argument("--review-json", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    context_dir = Path(args.context_dir)
    context = load_context(context_dir)
    review = json.loads(Path(args.review_json).read_text())
    cwd = Path(context["repo_root"])
    severities = posting_severities(read_config(cwd))
    existing_comments = {"review": [], "issue": []} if args.dry_run else load_existing_comments(context, cwd)
    inline_urls = post_inline(context, review, cwd, existing_comments, severities, args.dry_run)
    overall_url = post_overall(context, review, cwd, existing_comments["issue"], severities, inline_urls, args.dry_run)
    inline, overall = postable_comments(review, severities)
    counts = severity_counts(inline + overall)
    overall_count = len(overall) + (1 if review["verdict"] == "APPROVE" else 0)
    print(json.dumps({
        "dry_run": args.dry_run,
        "posting_severities": sorted(severities),
        "inline_comments": len(inline),
        "inline_urls": list(inline_urls.values()),
        "overall": overall_url,
        "overall_comments": overall_count,
        **counts,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"post-comments failed: {exc}", file=sys.stderr)
        sys.exit(1)
