from __future__ import annotations

import json
import subprocess

from conftest import SCRIPTS_DIR
from test_guard_and_merge import review

NORMALIZE = SCRIPTS_DIR / "normalize-review.py"


def write_config(root, severities: str) -> None:
    config_path = root / ".agents/pr-review"
    config_path.mkdir(parents=True)
    (config_path / "config.yaml").write_text(
        f"""version: 1
posting:
  severities: [{severities}]
quality:
  path: .agents/pr-review/quality/code.yaml
workspace:
  tmp_dir: .agents/tmp/pr-review
"""
    )


def write_context(root):
    context_dir = root / ".agents/tmp/pr-review/sample"
    context_dir.mkdir(parents=True)
    (context_dir / "context.json").write_text(
        json.dumps(
            {
                "owner": "owner",
                "repo": "repo",
                "number": 1,
                "repo_root": str(root),
                "pr": {"headRefOid": "abc", "url": "https://github.com/owner/repo/pull/1"},
            }
        )
    )
    return context_dir


def run_normalize(context_dir, review_path, out_path):
    proc = subprocess.run(
        [str(NORMALIZE), "--context-dir", str(context_dir), "--review-json", str(review_path), "--out", str(out_path)],
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(proc.stdout), json.loads(out_path.read_text())


def test_normalize_moves_question_to_notes_and_approves_when_not_postable(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    write_config(tmp_path, "must, should")
    context_dir = write_context(tmp_path)
    review_path = context_dir / "review.json"
    out_path = context_dir / "review-normalized.json"
    review_path.write_text(json.dumps(review("question")))

    summary, data = run_normalize(context_dir, review_path, out_path)

    assert summary["verdict"] == "APPROVE"
    assert data["verdict"] == "APPROVE"
    assert data["inline_comments"] == []
    assert data["overall_comments"] == []
    assert any("Moved unresolved question" in note for note in data["notes"])


def test_normalize_requires_separate_output_path(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    write_config(tmp_path, "must, should")
    context_dir = write_context(tmp_path)
    review_path = context_dir / "review.json"
    review_path.write_text(json.dumps(review("question")))

    proc = subprocess.run(
        [str(NORMALIZE), "--context-dir", str(context_dir), "--review-json", str(review_path)],
        text=True,
        capture_output=True,
    )

    assert proc.returncode != 0
    assert "--out" in proc.stderr


def test_normalize_moves_non_posting_should_to_notes_and_approves(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    write_config(tmp_path, "must")
    context_dir = write_context(tmp_path)
    review_path = context_dir / "review.json"
    out_path = context_dir / "review-normalized.json"
    review_path.write_text(json.dumps(review("should")))

    summary, data = run_normalize(context_dir, review_path, out_path)

    assert summary["verdict"] == "APPROVE"
    assert data["verdict"] == "APPROVE"
    assert data["inline_comments"] == []
    assert data["overall_comments"] == []
    assert any("Moved non-posting should" in note for note in data["notes"])


def test_normalize_keeps_postable_must_and_moves_question(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    write_config(tmp_path, "must, should")
    context_dir = write_context(tmp_path)
    data = review("must")
    question = dict(data["inline_comments"][0])
    question["severity"] = "question"
    question["title"] = "Needs clarification"
    data["inline_comments"].append(question)
    review_path = context_dir / "review.json"
    out_path = context_dir / "review-normalized.json"
    review_path.write_text(json.dumps(data))

    summary, normalized = run_normalize(context_dir, review_path, out_path)

    assert summary["verdict"] == "COMMENT"
    assert normalized["verdict"] == "COMMENT"
    assert len(normalized["inline_comments"]) == 1
    assert normalized["inline_comments"][0]["severity"] == "must"
    assert any("Moved unresolved question" in note for note in normalized["notes"])
    assert "checked sample boundary" in normalized["notes"]


def test_normalize_moves_question_to_notes_even_when_configured_postable(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    write_config(tmp_path, "question")
    context_dir = write_context(tmp_path)
    review_path = context_dir / "review.json"
    out_path = context_dir / "review-normalized.json"
    review_path.write_text(json.dumps(review("question")))

    summary, data = run_normalize(context_dir, review_path, out_path)

    assert summary["verdict"] == "APPROVE"
    assert data["verdict"] == "APPROVE"
    assert data["inline_comments"] == []
    assert any("Moved unresolved question" in note for note in data["notes"])


def test_normalize_moves_non_posting_overall_to_notes(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    write_config(tmp_path, "must")
    context_dir = write_context(tmp_path)
    data = review("must")
    overall = {
        "paths": ["a.py"],
        "severity": "should",
        "title": "Overall recommendation",
        "body": "Body",
        "evidence": "Evidence",
        "failure_scenario": "Failure",
        "suggested_fix": "Fix",
    }
    data["inline_comments"] = []
    data["overall_comments"] = [overall]
    review_path = context_dir / "review.json"
    out_path = context_dir / "review-normalized.json"
    review_path.write_text(json.dumps(data))

    summary, normalized = run_normalize(context_dir, review_path, out_path)

    assert summary["verdict"] == "APPROVE"
    assert normalized["overall_comments"] == []
    assert any("Moved non-posting should" in note for note in normalized["notes"])


def test_normalize_keeps_postable_overall_comment(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    write_config(tmp_path, "must")
    context_dir = write_context(tmp_path)
    data = review("must")
    overall = {
        "paths": ["a.py"],
        "severity": "must",
        "title": "Overall blocker",
        "body": "Body",
        "evidence": "Evidence",
        "failure_scenario": "Failure",
        "suggested_fix": "Fix",
    }
    data["inline_comments"] = []
    data["overall_comments"] = [overall]
    review_path = context_dir / "review.json"
    out_path = context_dir / "review-normalized.json"
    review_path.write_text(json.dumps(data))

    summary, normalized = run_normalize(context_dir, review_path, out_path)

    assert summary["verdict"] == "COMMENT"
    assert normalized["inline_comments"] == []
    assert len(normalized["overall_comments"]) == 1
    assert normalized["overall_comments"][0]["severity"] == "must"
