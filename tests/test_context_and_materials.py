from __future__ import annotations

from conftest import load_script

collect = load_script("collect_pr_context", "collect-pr-context.py")
materials = load_script("get_review_material", "get-review-material.py")


def test_remote_for_repo_prefers_matching_remote(monkeypatch, tmp_path):
    def fake_run(args, cwd):
        assert args == ["git", "remote", "-v"]
        assert cwd == tmp_path
        return "\n".join(
            [
                "origin git@github.com:someone/fork.git (fetch)",
                "origin git@github.com:someone/fork.git (push)",
                "upstream https://github.com/owner/repo.git (fetch)",
            ]
        )

    monkeypatch.setattr(collect, "run", fake_run)
    assert collect.remote_for_repo("owner", "repo", tmp_path) == "upstream"


def test_remote_for_repo_falls_back_to_origin(monkeypatch, tmp_path):
    monkeypatch.setattr(collect, "run", lambda _args, _cwd: "")
    assert collect.remote_for_repo("owner", "repo", tmp_path) == "origin"


def test_diff_for_path_selects_exact_file_not_suffix_overlap():
    diff = """diff --git a/foo/a.py b/foo/a.py
index 111..222 100644
--- a/foo/a.py
+++ b/foo/a.py
@@ -1 +1 @@
-old
+new
diff --git a/a.py b/a.py
index 333..444 100644
--- a/a.py
+++ b/a.py
@@ -1 +1 @@
-x
+y
"""

    selected = materials.diff_for_path(diff, "a.py")
    assert "diff --git a/a.py b/a.py" in selected
    assert "diff --git a/foo/a.py b/foo/a.py" not in selected


def test_diff_for_path_includes_renamed_file_new_path():
    diff = """diff --git a/old.py b/new.py
similarity index 90%
rename from old.py
rename to new.py
@@ -1 +1 @@
-old
+new
"""

    assert materials.diff_for_path(diff, "new.py").startswith("diff --git a/old.py b/new.py")
