from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = SKILL_DIR / "references/default-config.yaml"
DEFAULT_QUALITY = SKILL_DIR / "references/default-quality.yaml"


def run(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(
        args,
        cwd=cwd,
        check=False,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    return proc.stdout


def repo_root(cwd: Path) -> Path:
    return Path(run(["git", "rev-parse", "--show-toplevel"], cwd).strip()).resolve()


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(item) for item in inner.split(",")]
    if value in {"true", "false"}:
        return value == "true"
    if value in {"null", "~"}:
        return None
    if value in {"[]", "{}"}:
        return [] if value == "[]" else {}
    try:
        return int(value)
    except ValueError:
        pass
    return value


def parse_simple_yaml(text: str) -> dict[str, Any]:
    lines = [
        (len(raw) - len(raw.lstrip(" ")), raw.strip())
        for raw in text.splitlines()
        if raw.strip() and not raw.lstrip().startswith("#")
    ]

    def parse_block(index: int, indent: int) -> tuple[Any, int]:
        is_list = index < len(lines) and lines[index][0] == indent and lines[index][1].startswith("- ")
        if is_list:
            values: list[Any] = []
            while index < len(lines):
                current_indent, line = lines[index]
                if current_indent < indent:
                    break
                if current_indent != indent or not line.startswith("- "):
                    break
                item = line[2:].strip()
                if item:
                    values.append(parse_scalar(item))
                    index += 1
                else:
                    child, index = parse_block(index + 1, indent + 2)
                    values.append(child)
            return values, index

        values: dict[str, Any] = {}
        while index < len(lines):
            current_indent, line = lines[index]
            if current_indent < indent:
                break
            if current_indent != indent:
                raise ValueError(f"unexpected indentation: {line}")
            key, sep, raw_value = line.partition(":")
            if not sep:
                raise ValueError(f"expected key/value mapping: {line}")
            key = key.strip()
            raw_value = raw_value.strip()
            if raw_value:
                values[key] = parse_scalar(raw_value)
                index += 1
                continue
            if index + 1 >= len(lines) or lines[index + 1][0] <= current_indent:
                values[key] = {}
                index += 1
                continue
            child, index = parse_block(index + 1, lines[index + 1][0])
            values[key] = child
        return values, index

    parsed, final_index = parse_block(0, 0)
    if final_index != len(lines) or not isinstance(parsed, dict):
        raise ValueError("invalid simple YAML")
    return parsed


def read_config(root: Path) -> dict[str, Any]:
    path = config_path(root)
    if not path.exists():
        return parse_simple_yaml(DEFAULT_CONFIG.read_text())
    try:
        import yaml  # type: ignore
    except ModuleNotFoundError:
        return parse_simple_yaml(path.read_text())
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except Exception as exc:
        print(f"failed to parse config with PyYAML at {path}: {exc}", file=sys.stderr)
        raise ValueError(f"failed to parse config: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"config must be a mapping: {path}")
    return data


def load_context(context_dir: Path) -> dict[str, Any]:
    return json.loads((context_dir / "context.json").read_text())


def gh_api_paginated(path: str, cwd: Path) -> list[dict]:
    raw = run(["gh", "api", path, "--paginate", "--slurp"], cwd)
    pages = json.loads(raw)
    if isinstance(pages, list) and all(isinstance(page, list) for page in pages):
        return [item for page in pages for item in page]
    if isinstance(pages, list):
        return pages
    return [pages]


def config_path(root: Path) -> Path:
    return root / ".agents/pr-review/config.yaml"


def resolve_repo_path(root: Path, raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else root / path


def quality_path(root: Path, config: dict[str, Any]) -> Path:
    raw = str(config.get("quality", {}).get("path", ".agents/pr-review/quality/code.yaml"))
    return resolve_repo_path(root, raw)


def tmp_root(root: Path, config: dict[str, Any]) -> Path:
    raw = str(config.get("workspace", {}).get("tmp_dir", ".agents/tmp/pr-review"))
    return resolve_repo_path(root, raw)


def posting_severities(config: dict[str, Any]) -> set[str]:
    values = config.get("posting", {}).get("severities", ["must", "should"])
    if not isinstance(values, list):
        return {"must", "should"}
    return {str(value) for value in values if str(value) in {"must", "should", "nit"}}


def output_language(config: dict[str, Any]) -> str:
    return str(config.get("review", {}).get("output_language", "en"))


def print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False))
