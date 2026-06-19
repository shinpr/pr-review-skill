#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from pr_review_config import gh_api_paginated, print_json, read_config, repo_root, run, tmp_root


def git_object_exists(oid: str, cwd: Path) -> bool:
    proc = subprocess.run(
        ["git", "cat-file", "-e", f"{oid}^{{commit}}"],
        cwd=cwd,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc.returncode == 0


def remote_matches_repo(url: str, owner: str, repo: str) -> bool:
    normalized = url.removesuffix(".git")
    return normalized.endswith(f"github.com/{owner}/{repo}") or normalized.endswith(f"github.com:{owner}/{repo}")


def remote_for_repo(owner: str, repo: str, cwd: Path) -> str:
    remotes = run(["git", "remote", "-v"], cwd)
    for line in remotes.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[2] == "(fetch)" and remote_matches_repo(parts[1], owner, repo):
            return parts[0]
    return "origin"


def fetch_pr_commits(pr_view: dict, cwd: Path, remote: str) -> None:
    number = int(pr_view["number"])
    base_oid = pr_view["baseRefOid"]
    head_oid = pr_view["headRefOid"]
    if git_object_exists(base_oid, cwd) and git_object_exists(head_oid, cwd):
        return
    run(["git", "fetch", "--no-tags", remote, pr_view["baseRefName"], f"refs/pull/{number}/head"], cwd)
    missing = [oid for oid in (base_oid, head_oid) if not git_object_exists(oid, cwd)]
    if missing:
        raise RuntimeError(f"fetched PR refs but missing commits: {', '.join(missing)}")


def parse_owner_repo(url: str, cwd: Path) -> tuple[str, str]:
    match = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/#]+)", url)
    if match:
        return match.group("owner"), match.group("repo").removesuffix(".git")
    remote = run(["gh", "repo", "view", "--json", "owner,name"], cwd)
    data = json.loads(remote)
    return data["owner"]["login"], data["name"]


def context_dir(root: Path, config: dict, owner: str, repo: str, number: int) -> Path:
    safe = f"{owner}-{repo}-{number}".replace("/", "-")
    return tmp_root(root, config) / safe


def build_context(root: Path, config: dict, owner: str, repo: str, number: int, pr_view: dict, out: Path) -> dict:
    changed_file_details = [
        {"path": f["path"], "additions": f.get("additions", 0), "deletions": f.get("deletions", 0)}
        for f in pr_view.get("files", [])
    ]
    return {
        "owner": owner,
        "repo": repo,
        "number": number,
        "repo_root": str(root),
        "config": config,
        "pr": pr_view,
        "changed_files": [f["path"] for f in changed_file_details],
        "changed_file_details": changed_file_details,
        "review_comments_path": str(out / "review-comments.json"),
        "issue_comments_path": str(out / "issue-comments.json"),
        "reviews_path": str(out / "reviews.json"),
        "diff_path": str(out / "diff.patch"),
    }


def write_context_files(out: Path, context: dict, diff: str, review_comments: list[dict], issue_comments: list[dict], reviews: list[dict]) -> None:
    (out / "context.json").write_text(json.dumps(context, ensure_ascii=False, indent=2) + "\n")
    (out / "diff.patch").write_text(diff)
    (out / "review-comments.json").write_text(json.dumps(review_comments, ensure_ascii=False, indent=2) + "\n")
    (out / "issue-comments.json").write_text(json.dumps(issue_comments, ensure_ascii=False, indent=2) + "\n")
    (out / "reviews.json").write_text(json.dumps(reviews, ensure_ascii=False, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr-url", required=True)
    parser.add_argument("--out-dir")
    args = parser.parse_args()

    root = repo_root(Path.cwd())
    config = read_config(root)
    owner, repo = parse_owner_repo(args.pr_url, root)
    pr_view = json.loads(
        run(
            [
                "gh",
                "pr",
                "view",
                args.pr_url,
                "--json",
                "number,title,author,state,url,headRefName,headRefOid,baseRefName,baseRefOid,body,files,additions,deletions,comments,reviews,statusCheckRollup",
            ],
            root,
        )
    )
    number = int(pr_view["number"])
    out = Path(args.out_dir).resolve() if args.out_dir else context_dir(root, config, owner, repo, number)
    out.mkdir(parents=True, exist_ok=True)

    fetch_pr_commits(pr_view, root, remote_for_repo(owner, repo, root))
    diff = run(["gh", "pr", "diff", args.pr_url, "--patch"], root)
    review_comments = gh_api_paginated(f"/repos/{owner}/{repo}/pulls/{number}/comments", root)
    issue_comments = gh_api_paginated(f"/repos/{owner}/{repo}/issues/{number}/comments", root)
    reviews = gh_api_paginated(f"/repos/{owner}/{repo}/pulls/{number}/reviews", root)

    context = build_context(root, config, owner, repo, number, pr_view, out)
    write_context_files(out, context, diff, review_comments, issue_comments, reviews)

    print_json({"context_dir": str(out), "context_path": str(out / "context.json")})
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"collect-pr-context failed: {exc}", file=sys.stderr)
        sys.exit(1)
