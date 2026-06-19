#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from pr_review_config import load_context, output_language, read_config

SKILL_DIR = Path(__file__).resolve().parents[1]
SYSTEM_PROMPT = SKILL_DIR / "references/reviewer-system-prompt.md"
SCHEMA = SKILL_DIR / "schemas/review-result.schema.json"
MATERIAL_SCRIPT = SKILL_DIR / "scripts/get-review-material.py"
GUARD_SCRIPT = SKILL_DIR / "scripts/guard-plugin/scripts/require-final-json.py"
GUARD_TEMPLATE = SKILL_DIR / "scripts/guard-plugin/settings.json.template"


def run_process(args: list[str], cwd: Path, stdin: str | None = None, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        input=stdin,
        text=True,
        check=False,
        capture_output=True,
        timeout=timeout / 1000 if timeout else None,
    )


def extract_claude_result(stdout: str) -> str:
    result = ""
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "result":
            result = event.get("result") or result
    return result


def strip_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].strip() in {"```", "```json"} and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).strip()
    return stripped


def write_guard_settings() -> Path:
    body = GUARD_TEMPLATE.read_text().replace("__GUARD_SCRIPT__", str(GUARD_SCRIPT))
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
        tmp.write(body)
        return Path(tmp.name)


def validate(path: Path) -> None:
    proc = run_process(["python3", str(GUARD_SCRIPT), "--cli", str(path)], SKILL_DIR)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())


def reviewer_prompt(context_dir: Path, repo_root: Path, engine: str, language: str) -> str:
    return "\n".join(
        [
            f"CONTEXT_DIR: {context_dir}",
            f"REPO_ROOT: {repo_root}",
            f"MATERIAL_SCRIPT: {MATERIAL_SCRIPT}",
            f"SCHEMA_PATH: {SCHEMA}",
            f"ENGINE: {engine}",
            f"OUTPUT_LANGUAGE: {language}",
        ]
    )


def run_claude(context_dir: Path, repo_root: Path, model: str | None, timeout: int | None, language: str) -> str:
    settings = write_guard_settings()
    prompt = SYSTEM_PROMPT.read_text() + "\n\n" + reviewer_prompt(context_dir, repo_root, "claude", language)
    args = [
        "claude",
        "-p",
        prompt,
        "--settings",
        str(settings),
        "--output-format",
        "stream-json",
        "--verbose",
        "--include-hook-events",
        "--permission-mode",
        "bypassPermissions",
        "--disallowedTools",
        "Write,Edit,MultiEdit,NotebookEdit",
    ]
    if model:
        args = ["claude", "--model", model, *args[1:]]
    try:
        proc = run_process(args, repo_root, timeout=timeout)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr or proc.stdout)
        result = extract_claude_result(proc.stdout)
        if not result.strip():
            raise RuntimeError("claude returned no result text")
        return result
    finally:
        settings.unlink(missing_ok=True)


def run_codex(context_dir: Path, repo_root: Path, model: str | None, timeout: int | None, language: str) -> str:
    prompt = SYSTEM_PROMPT.read_text() + "\n\n" + reviewer_prompt(context_dir, repo_root, "codex", language)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as last_message:
        last_message_path = Path(last_message.name)
    args = [
        "codex",
        "exec",
        "--cd",
        str(repo_root),
        "--sandbox",
        "read-only",
        "--output-schema",
        str(SCHEMA),
        "--output-last-message",
        str(last_message_path),
        "-",
    ]
    if model:
        args.insert(-1, "--model")
        args.insert(-1, model)
    try:
        proc = run_process(args, repo_root, stdin=prompt, timeout=timeout)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr or proc.stdout)
        result = last_message_path.read_text()
        if not result.strip():
            raise RuntimeError("codex returned no last message")
        return result
    finally:
        last_message_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context-dir", required=True)
    parser.add_argument("--engine", choices=["claude", "codex"], required=True)
    parser.add_argument("--model")
    parser.add_argument("--out")
    parser.add_argument("--timeout", type=int)
    args = parser.parse_args()

    context_dir = Path(args.context_dir).resolve()
    context = load_context(context_dir)
    repo_root = Path(context["repo_root"])
    language = output_language(read_config(repo_root))

    if args.engine == "claude":
        result = run_claude(context_dir, repo_root, args.model, args.timeout, language)
    else:
        result = run_codex(context_dir, repo_root, args.model, args.timeout, language)

    out = Path(args.out).resolve() if args.out else context_dir / f"review-{args.engine}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(strip_fence(result) + "\n")
    validate(out)
    print(json.dumps({"review_json": str(out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"run-review failed: {exc}", file=sys.stderr)
        sys.exit(1)
