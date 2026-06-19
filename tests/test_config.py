from __future__ import annotations

import subprocess

from conftest import SCRIPTS_DIR, load_script

config = load_script("pr_review_config", "pr_review_config.py")


def test_parse_default_config_lists():
    cfg = config.parse_simple_yaml((SCRIPTS_DIR.parent / "references/default-config.yaml").read_text())
    assert cfg["posting"]["severities"] == ["must", "should"]
    assert cfg["guidance"]["include_files"] == [
        "AGENTS.md",
        "CLAUDE.md",
        ".github/copilot-instructions.md",
    ]


def test_paths_resolve_relative_to_repo_root(tmp_path):
    cfg = config.parse_simple_yaml((SCRIPTS_DIR.parent / "references/default-config.yaml").read_text())
    assert config.config_path(tmp_path) == tmp_path / ".agents/pr-review/config.yaml"
    assert config.quality_path(tmp_path, cfg) == tmp_path / ".agents/pr-review/quality/code.yaml"
    assert config.tmp_root(tmp_path, cfg) == tmp_path / ".agents/tmp/pr-review"
    assert config.posting_severities(cfg) == {"must", "should"}
    assert config.output_language(cfg) == "en"


def test_simple_yaml_accepts_quoted_scalars_and_inline_lists():
    cfg = config.parse_simple_yaml(
        """version: 1
posting:
  severities: [must, question]
review:
  output_language: "ja"
"""
    )
    assert cfg["posting"]["severities"] == ["must", "question"]
    assert cfg["review"]["output_language"] == "ja"
    assert config.posting_severities(cfg) == {"must", "question"}


def test_bootstrap_creates_config_and_empty_quality(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    proc = subprocess.run(
        [str(SCRIPTS_DIR / "bootstrap-config.py"), "--repo-root", str(tmp_path)],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "config_path" in proc.stdout
    assert (tmp_path / ".agents/pr-review/config.yaml").is_file()
    quality = tmp_path / ".agents/pr-review/quality/code.yaml"
    assert quality.is_file()
    assert "review_dimensions: []" in quality.read_text()


def test_bootstrap_is_idempotent(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    command = [str(SCRIPTS_DIR / "bootstrap-config.py"), "--repo-root", str(tmp_path)]
    subprocess.run(command, check=True, capture_output=True)
    proc = subprocess.run(command, check=True, text=True, capture_output=True)
    assert '"created": []' in proc.stdout
