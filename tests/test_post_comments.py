from __future__ import annotations

import json
import subprocess

from conftest import SCRIPTS_DIR, load_script
from test_guard_and_merge import review

POST_COMMENTS = SCRIPTS_DIR / "post-comments.py"
post_comments = load_script("post_comments", "post-comments.py")


def test_post_comments_dry_run_ignores_question_posting_severity_without_network(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    config_path = tmp_path / ".agents/pr-review"
    config_path.mkdir(parents=True)
    (config_path / "config.yaml").write_text(
        """version: 1
posting:
  severities:
    - question
quality:
  path: .agents/pr-review/quality/code.yaml
workspace:
  tmp_dir: .agents/tmp/pr-review
"""
    )
    context_dir = tmp_path / ".agents/tmp/pr-review/sample"
    context_dir.mkdir(parents=True)
    (context_dir / "context.json").write_text(
        json.dumps(
            {
                "owner": "owner",
                "repo": "repo",
                "number": 1,
                "repo_root": str(tmp_path),
                "pr": {"headRefOid": "abc", "url": "https://github.com/owner/repo/pull/1"},
            }
        )
    )
    data = review("question")
    review_path = context_dir / "review.json"
    review_path.write_text(json.dumps(data))

    proc = subprocess.run(
        [str(POST_COMMENTS), "--context-dir", str(context_dir), "--review-json", str(review_path), "--dry-run"],
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["posting_severities"] == []
    assert payload["inline_comments"] == 0
    assert payload["question"] == 0
    assert "COMMENT review has no postable findings" in proc.stderr


def test_post_comments_dry_run_warns_when_comment_has_no_postable_findings(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    config_path = tmp_path / ".agents/pr-review"
    config_path.mkdir(parents=True)
    (config_path / "config.yaml").write_text(
        """version: 1
posting:
  severities: [must]
quality:
  path: .agents/pr-review/quality/code.yaml
workspace:
  tmp_dir: .agents/tmp/pr-review
"""
    )
    context_dir = tmp_path / ".agents/tmp/pr-review/sample"
    context_dir.mkdir(parents=True)
    (context_dir / "context.json").write_text(
        json.dumps(
            {
                "owner": "owner",
                "repo": "repo",
                "number": 1,
                "repo_root": str(tmp_path),
                "pr": {"headRefOid": "abc", "url": "https://github.com/owner/repo/pull/1"},
            }
        )
    )
    data = review("nit")
    review_path = context_dir / "review.json"
    review_path.write_text(json.dumps(data))

    proc = subprocess.run(
        [str(POST_COMMENTS), "--context-dir", str(context_dir), "--review-json", str(review_path), "--dry-run"],
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(proc.stdout)
    assert payload["inline_comments"] == 0
    assert payload["overall_comments"] == 0
    assert payload["overall"] is None
    assert "COMMENT review has no postable findings" in proc.stderr


def test_post_comments_dry_run_includes_approve_summary(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    config_path = tmp_path / ".agents/pr-review"
    config_path.mkdir(parents=True)
    (config_path / "config.yaml").write_text(
        """version: 1
posting:
  severities: [must, should]
quality:
  path: .agents/pr-review/quality/code.yaml
workspace:
  tmp_dir: .agents/tmp/pr-review
"""
    )
    context_dir = tmp_path / ".agents/tmp/pr-review/sample"
    context_dir.mkdir(parents=True)
    (context_dir / "context.json").write_text(
        json.dumps(
            {
                "owner": "owner",
                "repo": "repo",
                "number": 1,
                "repo_root": str(tmp_path),
                "pr": {"headRefOid": "abc", "url": "https://github.com/owner/repo/pull/1"},
            }
        )
    )
    data = review("must")
    data["verdict"] = "APPROVE"
    data["inline_comments"] = []
    data["overall_comments"] = []
    data["notes"] = ["checked command boundaries"]
    review_path = context_dir / "review.json"
    review_path.write_text(json.dumps(data))

    proc = subprocess.run(
        [str(POST_COMMENTS), "--context-dir", str(context_dir), "--review-json", str(review_path), "--dry-run"],
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(proc.stdout)
    assert payload["inline_comments"] == 0
    assert payload["overall_comments"] == 1
    assert payload["must"] == 0
    assert payload["should"] == 0


def test_post_comments_dry_run_keeps_distinct_findings_on_same_line(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    config_path = tmp_path / ".agents/pr-review"
    config_path.mkdir(parents=True)
    (config_path / "config.yaml").write_text(
        """version: 1
posting:
  severities: [must, should]
quality:
  path: .agents/pr-review/quality/code.yaml
workspace:
  tmp_dir: .agents/tmp/pr-review
"""
    )
    context_dir = tmp_path / ".agents/tmp/pr-review/sample"
    context_dir.mkdir(parents=True)
    (context_dir / "context.json").write_text(
        json.dumps(
            {
                "owner": "owner",
                "repo": "repo",
                "number": 1,
                "repo_root": str(tmp_path),
                "pr": {"headRefOid": "abc", "url": "https://github.com/owner/repo/pull/1"},
            }
        )
    )
    data = review("should")
    other = dict(data["inline_comments"][0])
    other["severity"] = "must"
    other["title"] = "Different root cause"
    other["body"] = "Different body"
    other["failure_scenario"] = "Different failure"
    data["inline_comments"].append(other)
    review_path = context_dir / "review.json"
    review_path.write_text(json.dumps(data))

    proc = subprocess.run(
        [str(POST_COMMENTS), "--context-dir", str(context_dir), "--review-json", str(review_path), "--dry-run"],
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(proc.stdout)
    assert payload["inline_comments"] == 2
    assert payload["must"] == 1
    assert payload["should"] == 1


def test_post_comments_dry_run_deduplicates_same_inline_root_cause(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    config_path = tmp_path / ".agents/pr-review"
    config_path.mkdir(parents=True)
    (config_path / "config.yaml").write_text(
        """version: 1
posting:
  severities: [must, should]
quality:
  path: .agents/pr-review/quality/code.yaml
workspace:
  tmp_dir: .agents/tmp/pr-review
"""
    )
    context_dir = tmp_path / ".agents/tmp/pr-review/sample"
    context_dir.mkdir(parents=True)
    (context_dir / "context.json").write_text(
        json.dumps(
            {
                "owner": "owner",
                "repo": "repo",
                "number": 1,
                "repo_root": str(tmp_path),
                "pr": {"headRefOid": "abc", "url": "https://github.com/owner/repo/pull/1"},
            }
        )
    )
    data = review("should")
    duplicate = dict(data["inline_comments"][0])
    duplicate["severity"] = "must"
    duplicate["body"] = "Same root cause with stronger severity"
    data["inline_comments"].append(duplicate)
    review_path = context_dir / "review.json"
    review_path.write_text(json.dumps(data))

    proc = subprocess.run(
        [str(POST_COMMENTS), "--context-dir", str(context_dir), "--review-json", str(review_path), "--dry-run"],
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(proc.stdout)
    assert payload["inline_comments"] == 1
    assert payload["must"] == 1
    assert payload["should"] == 0


def test_post_overall_does_not_call_network_when_no_findings_match(monkeypatch, tmp_path):
    def fail_post(*_args):
        raise AssertionError("post_issue_comment should not run")

    monkeypatch.setattr(post_comments, "post_issue_comment", fail_post)
    context = {"pr": {"headRefOid": "abc"}}
    assert post_comments.post_overall(context, review("nit"), tmp_path, [], {"must"}, {}, dry_run=False) is None


def test_post_overall_posts_approve_summary_without_findings(monkeypatch, tmp_path):
    posted: list[str] = []

    def fake_post(_context, body, _cwd):
        posted.append(body)
        return "https://example.test/comment"

    monkeypatch.setattr(post_comments, "post_issue_comment", fake_post)
    context = {"pr": {"headRefOid": "abc"}}
    data = review("must")
    data["verdict"] = "APPROVE"
    data["inline_comments"] = []
    data["overall_comments"] = []
    data["notes"] = ["checked command boundaries"]

    assert post_comments.post_overall(context, data, tmp_path, [], {"must"}, {}, dry_run=False) == "https://example.test/comment"
    assert "Agent code review: APPROVE" in posted[0]
    assert "checked command boundaries" in posted[0]


def test_marker_prefix_deduplicates_regenerated_comment():
    body = "first body"
    first = post_comments.marker("inline", "abc:a.py:1:RIGHT", body)
    second = post_comments.marker("inline", "abc:a.py:1:RIGHT", "updated body")
    comments = [{"body": f"posted\n\n{first}", "html_url": "https://example.test/comment"}]
    assert post_comments.existing_url(comments, second) == "https://example.test/comment"


def test_inline_key_distinguishes_distinct_findings_on_same_line():
    first = review("must")["inline_comments"][0]
    second = dict(first)
    second["title"] = "Different root cause"
    second["failure_scenario"] = "Different failure"

    assert post_comments.inline_key(first, "abc") != post_comments.inline_key(second, "abc")


def test_inline_key_is_stable_for_same_root_cause_when_body_changes():
    first = review("must")["inline_comments"][0]
    second = dict(first)
    second["body"] = "Updated wording"

    assert post_comments.inline_key(first, "abc") == post_comments.inline_key(second, "abc")
