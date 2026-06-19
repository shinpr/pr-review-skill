from __future__ import annotations

import json
import subprocess

from conftest import SCRIPTS_DIR

GUARD = SCRIPTS_DIR / "guard-plugin/scripts/require-final-json.py"


def review(severity: str = "must") -> dict:
    return {
        "verdict": "COMMENT",
        "confidence": "high",
        "summary": "sample",
        "inspected": {
            "quality_standard": "sample",
            "project_guidance": [],
            "changed_files": ["a.py"],
            "prior_comments_considered": 0,
        },
        "quality_coverage": [
            {
                "criterion": "sample-rule",
                "changed_surface": "a.py",
                "evidence_checked": ["a.py diff"],
            }
        ],
        "inline_comments": [
            {
                "path": "a.py",
                "line": 1,
                "side": "RIGHT",
                "severity": severity,
                "title": "Bug",
                "body": "Body",
                "evidence": "Evidence",
                "failure_scenario": "Failure",
                "suggested_fix": "Fix",
            }
        ],
        "overall_comments": [],
        "suppressed_prior_comments": [],
        "notes": ["checked sample boundary"],
    }


def test_guard_accepts_valid_review_json(tmp_path):
    path = tmp_path / "review.json"
    path.write_text(json.dumps(review()))
    proc = subprocess.run([str(GUARD), "--cli", str(path)], check=True)
    assert proc.returncode == 0


def test_guard_rejects_approve_with_findings(tmp_path):
    data = review()
    data["verdict"] = "APPROVE"
    path = tmp_path / "review.json"
    path.write_text(json.dumps(data))
    proc = subprocess.run([str(GUARD), "--cli", str(path)], text=True, stderr=subprocess.PIPE)
    assert proc.returncode == 2
    assert "APPROVE cannot include findings" in proc.stderr


def test_guard_rejects_comment_without_findings(tmp_path):
    data = review()
    data["inline_comments"] = []
    path = tmp_path / "review.json"
    path.write_text(json.dumps(data))
    proc = subprocess.run([str(GUARD), "--cli", str(path)], text=True, stderr=subprocess.PIPE)
    assert proc.returncode == 2
    assert "COMMENT requires at least one finding" in proc.stderr


def test_guard_rejects_empty_inspected_items(tmp_path):
    data = review()
    data["inspected"]["changed_files"] = [""]
    path = tmp_path / "review.json"
    path.write_text(json.dumps(data))
    proc = subprocess.run([str(GUARD), "--cli", str(path)], text=True, stderr=subprocess.PIPE)
    assert proc.returncode == 2
    assert "changed_files[0]" in proc.stderr


def test_guard_rejects_empty_quality_coverage_evidence(tmp_path):
    data = review()
    data["quality_coverage"][0]["evidence_checked"] = [""]
    path = tmp_path / "review.json"
    path.write_text(json.dumps(data))
    proc = subprocess.run([str(GUARD), "--cli", str(path)], text=True, stderr=subprocess.PIPE)
    assert proc.returncode == 2
    assert "quality_coverage[0].evidence_checked[0]" in proc.stderr


def test_guard_rejects_empty_quality_coverage(tmp_path):
    data = review()
    data["quality_coverage"] = []
    path = tmp_path / "review.json"
    path.write_text(json.dumps(data))
    proc = subprocess.run([str(GUARD), "--cli", str(path)], text=True, stderr=subprocess.PIPE)
    assert proc.returncode == 2
    assert "quality_coverage must contain at least one item" in proc.stderr


def test_guard_rejects_quality_coverage_without_evidence(tmp_path):
    data = review()
    data["quality_coverage"][0]["evidence_checked"] = []
    path = tmp_path / "review.json"
    path.write_text(json.dumps(data))
    proc = subprocess.run([str(GUARD), "--cli", str(path)], text=True, stderr=subprocess.PIPE)
    assert proc.returncode == 2
    assert "quality_coverage[0].evidence_checked must contain at least one item" in proc.stderr
