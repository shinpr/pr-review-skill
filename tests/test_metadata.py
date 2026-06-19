from __future__ import annotations

import json
from pathlib import Path

from conftest import REPO_ROOT, SKILL_DIR


def _frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text()
    assert text.startswith("---\n")
    end = text.find("\n---", 4)
    assert end != -1
    data: dict[str, object] = {}
    for raw in text[4:end].splitlines():
        if not raw.strip():
            continue
        key, _, value = raw.partition(":")
        value = value.strip()
        if value == "true":
            data[key.strip()] = True
        elif value == "false":
            data[key.strip()] = False
        else:
            data[key.strip()] = value
    return data


def test_skill_is_recipe_pr_review_and_claude_recipe_only():
    frontmatter = _frontmatter(SKILL_DIR / "SKILL.md")
    assert frontmatter["name"] == "recipe-pr-review"
    assert frontmatter["disable-model-invocation"] is True


def test_codex_plugin_points_to_skills_directory():
    manifest = json.loads((REPO_ROOT / "plugins/pr-review/.codex-plugin/plugin.json").read_text())
    assert manifest["name"] == "pr-review"
    assert manifest["skills"] == "./skills/"
    assert manifest["interface"]["displayName"] == "PR Review"


def test_marketplaces_point_to_plugin_directory():
    codex_marketplace = json.loads((REPO_ROOT / ".codex-plugin/marketplace.json").read_text())
    assert codex_marketplace["plugins"][0]["name"] == "pr-review"
    assert codex_marketplace["plugins"][0]["source"]["path"] == "./plugins/pr-review"

    claude_marketplace = json.loads((REPO_ROOT / ".claude-plugin/marketplace.json").read_text())
    assert claude_marketplace["plugins"][0]["source"] == "./plugins/pr-review"


def test_openai_agent_requires_explicit_invocation():
    text = (SKILL_DIR / "agents/openai.yaml").read_text()
    assert "$recipe-pr-review" in text
    assert "allow_implicit_invocation: false" in text
