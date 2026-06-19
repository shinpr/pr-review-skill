#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ALLOWED_TOP = {
    "verdict",
    "confidence",
    "summary",
    "inspected",
    "quality_coverage",
    "inline_comments",
    "overall_comments",
    "suppressed_prior_comments",
    "notes",
}


def block(reason: str) -> None:
    print(json.dumps({"decision": "block", "reason": reason, "systemMessage": "Respond again with exactly one JSON object matching review-result.schema.json."}))


def strip_fence(text: str) -> str:
    match = re.match(r"^\s*```(?:json)?\s*\n(?P<body>.*?)\n```\s*$", text, re.S)
    return match.group("body") if match else text


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def nullable_string(value: Any) -> bool:
    return value is None or isinstance(value, str)


def validate(data: Any) -> None:
    require(isinstance(data, dict), "top-level value must be an object")
    require(set(data) == ALLOWED_TOP, f"top-level fields must be exactly {sorted(ALLOWED_TOP)}")
    require(data["verdict"] in {"COMMENT", "APPROVE"}, "verdict must be COMMENT or APPROVE")
    require(data["confidence"] in {"high", "medium", "low"}, "confidence is invalid")
    require(isinstance(data["summary"], str) and data["summary"].strip(), "summary is required")

    inspected = data["inspected"]
    require(isinstance(inspected, dict), "inspected must be an object")
    require(set(inspected) == {"quality_standard", "project_guidance", "changed_files", "prior_comments_considered"}, "inspected fields are invalid")
    require(isinstance(inspected["quality_standard"], str) and inspected["quality_standard"], "inspected.quality_standard is required")
    require(isinstance(inspected["project_guidance"], list), "inspected.project_guidance must be an array")
    for index, value in enumerate(inspected["project_guidance"]):
        require(isinstance(value, str) and value, f"inspected.project_guidance[{index}] must be a non-empty string")
    require(isinstance(inspected["changed_files"], list), "inspected.changed_files must be an array")
    for index, value in enumerate(inspected["changed_files"]):
        require(isinstance(value, str) and value, f"inspected.changed_files[{index}] must be a non-empty string")
    require(isinstance(inspected["prior_comments_considered"], int) and inspected["prior_comments_considered"] >= 0, "inspected.prior_comments_considered must be a non-negative integer")

    coverage = data["quality_coverage"]
    require(isinstance(coverage, list), "quality_coverage must be an array")
    require(bool(coverage), "quality_coverage must contain at least one item")
    for index, item in enumerate(coverage):
        require(isinstance(item, dict), f"quality_coverage[{index}] must be an object")
        require(set(item) == {"criterion", "changed_surface", "evidence_checked"}, f"quality_coverage[{index}] has invalid fields")
        require(isinstance(item["criterion"], str) and item["criterion"].strip(), f"quality_coverage[{index}].criterion is required")
        require(isinstance(item["changed_surface"], str) and item["changed_surface"].strip(), f"quality_coverage[{index}].changed_surface is required")
        require(isinstance(item["evidence_checked"], list), f"quality_coverage[{index}].evidence_checked must be an array")
        require(bool(item["evidence_checked"]), f"quality_coverage[{index}].evidence_checked must contain at least one item")
        for evidence_index, value in enumerate(item["evidence_checked"]):
            require(isinstance(value, str) and value.strip(), f"quality_coverage[{index}].evidence_checked[{evidence_index}] must be a non-empty string")

    inline = data["inline_comments"]
    overall = data["overall_comments"]
    require(isinstance(inline, list), "inline_comments must be an array")
    require(isinstance(overall, list), "overall_comments must be an array")
    for index, comment in enumerate(inline):
        require(isinstance(comment, dict), f"inline_comments[{index}] must be an object")
        require(set(comment) == {"path", "line", "side", "severity", "title", "body", "evidence", "failure_scenario", "suggested_fix"}, f"inline_comments[{index}] has invalid fields")
        require(isinstance(comment["path"], str) and comment["path"], f"inline_comments[{index}].path is required")
        require(isinstance(comment["line"], int) and comment["line"] >= 1, f"inline_comments[{index}].line is invalid")
        require(comment["side"] in {"RIGHT", "LEFT"}, f"inline_comments[{index}].side is invalid")
        require(comment["severity"] in {"must", "should", "question", "nit"}, f"inline_comments[{index}].severity is invalid")
        require(isinstance(comment["title"], str) and comment["title"].strip(), f"inline_comments[{index}].title is required")
        require(isinstance(comment["body"], str) and comment["body"].strip(), f"inline_comments[{index}].body is required")
        for field in ("evidence", "failure_scenario", "suggested_fix"):
            require(nullable_string(comment[field]), f"inline_comments[{index}].{field} must be a string or null")
    for index, comment in enumerate(overall):
        require(isinstance(comment, dict), f"overall_comments[{index}] must be an object")
        require(set(comment) == {"severity", "title", "body", "paths", "evidence", "failure_scenario", "suggested_fix"}, f"overall_comments[{index}] has invalid fields")
        require(comment["severity"] in {"must", "should", "question", "nit"}, f"overall_comments[{index}].severity is invalid")
        require(isinstance(comment["title"], str) and comment["title"].strip(), f"overall_comments[{index}].title is required")
        require(isinstance(comment["body"], str) and comment["body"].strip(), f"overall_comments[{index}].body is required")
        require(comment["paths"] is None or isinstance(comment["paths"], list), f"overall_comments[{index}].paths must be array or null")
        if isinstance(comment["paths"], list):
            for path_index, value in enumerate(comment["paths"]):
                require(isinstance(value, str) and value, f"overall_comments[{index}].paths[{path_index}] must be a non-empty string")
        for field in ("evidence", "failure_scenario", "suggested_fix"):
            require(nullable_string(comment[field]), f"overall_comments[{index}].{field} must be a string or null")

    require(isinstance(data["suppressed_prior_comments"], list), "suppressed_prior_comments must be an array")
    for index, comment in enumerate(data["suppressed_prior_comments"]):
        require(isinstance(comment, dict), f"suppressed_prior_comments[{index}] must be an object")
        require(set(comment) == {"source", "reason"}, f"suppressed_prior_comments[{index}] has invalid fields")
        require(isinstance(comment["source"], str) and comment["source"], f"suppressed_prior_comments[{index}].source is required")
        require(isinstance(comment["reason"], str) and comment["reason"], f"suppressed_prior_comments[{index}].reason is required")
    require(isinstance(data["notes"], list), "notes must be an array")
    for index, note in enumerate(data["notes"]):
        require(isinstance(note, str), f"notes[{index}] must be a string")
    if data["verdict"] == "APPROVE":
        require(not inline and not overall, "verdict APPROVE cannot include findings")
    if data["verdict"] == "COMMENT":
        require(bool(inline or overall), "verdict COMMENT requires at least one finding")


def final_text_from_hook(event: dict[str, Any]) -> str:
    message = event.get("last_assistant_message")
    if isinstance(message, str) and message.strip():
        return message
    transcript = event.get("transcript_path")
    if not transcript:
        return ""
    path = Path(transcript)
    if not path.exists():
        return ""
    for line in reversed(path.read_text(errors="replace").splitlines()[-200:]):
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("type") != "assistant":
            continue
        texts = [part.get("text", "") for part in item.get("message", {}).get("content", []) if isinstance(part, dict) and part.get("type") == "text"]
        if texts:
            return "\n".join(texts)
    return ""


def cli(path: Path) -> int:
    try:
        text = path.read_text().strip()
        if text.startswith("```"):
            raise ValueError("review JSON file must be raw JSON, not fenced Markdown")
        validate(json.loads(text))
    except Exception as exc:
        print(f"review JSON validation failed: {exc}", file=sys.stderr)
        return 2
    return 0


def hook() -> int:
    try:
        event = json.load(sys.stdin)
        validate(json.loads(strip_fence(final_text_from_hook(event)).strip()))
    except Exception as exc:
        block(str(exc))
    return 0


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--cli":
        return cli(Path(sys.argv[2]))
    return hook()


if __name__ == "__main__":
    sys.exit(main())
