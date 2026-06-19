# Codex Reviewer Notes

Use this reference when running Codex as a nested reviewer, especially from a Codex session.

## Permission

When running Codex as a nested reviewer from a Codex-hosted session, start `run-review.py --engine codex ...` with escalated sandbox permissions.

Nested `codex exec` needs access to Codex session state and external CLI binaries. Starting with escalation avoids a known fail-then-retry path:

- `Operation not permitted`
- failure to initialize Codex app-server or session state
- failure to create PATH aliases

Use the same `context_dir` created by context collection.

## Timeout

Use matching script and tool timeouts for long reviews. If the script receives `--timeout 600000`, the surrounding tool call should also allow at least 600000 ms.

Long nested reviews are normal. Keep the command attached until one terminal condition occurs:

- `review-codex.json` is written and validation succeeds.
- `run-review.py` exits with a non-zero status.
- the configured timeout expires.

Progress silence is not a terminal condition. Continue waiting while the command is still running.

## Execution

Run one nested reviewer from start to terminal state before starting another. Keep the run attached until it succeeds, fails validation, or times out.

## Common Errors

| Error | Cause | Action |
| --- | --- | --- |
| `Operation not permitted` | Nested Codex ran without required session-state access | Run the nested Codex reviewer with escalated permissions from the first attempt |
| Empty last message | Codex did not produce final output | Report failure and keep context directory |
| JSON schema failure | Reviewer returned invalid structure | Report validation error and keep context directory |
