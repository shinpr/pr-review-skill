from __future__ import annotations

import subprocess

from conftest import load_script

run_review = load_script("run_review", "run-review.py")


def test_run_claude_uses_bypass_permissions_with_write_tools_disallowed(monkeypatch, tmp_path):
    captured = {}

    def fake_run_process(args, cwd, stdin=None, timeout=None):
        captured["args"] = args
        captured["cwd"] = cwd
        return subprocess.CompletedProcess(args, 0, stdout='{"type":"result","result":"{}"}\n', stderr="")

    monkeypatch.setattr(run_review, "run_process", fake_run_process)

    run_review.run_claude(tmp_path / "context", tmp_path, None, 1000, "en")

    args = captured["args"]
    assert args[0:2] == ["claude", "-p"]
    assert args[args.index("--permission-mode") + 1] == "bypassPermissions"
    assert args[args.index("--disallowedTools") + 1] == "Write,Edit,MultiEdit,NotebookEdit"
