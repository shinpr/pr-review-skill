# Code Review Conventions

## Severity Labels

Use these labels in reviewer JSON:

| Label | Meaning |
| --- | --- |
| `must` | A bug, broken contract, security issue, data-loss risk, or merge-blocking quality gap. |
| `should` | A strong recommendation that should be addressed before merge and remains below clear correctness-blocker severity. |
| `question` | A raw reviewer concern that needs clarification before the orchestrator can treat it as a recommendation. |
| `nit` | Minor cleanup, style, or maintainability note. |

The reviewer should emit all evidence-backed raw findings it identifies. The orchestrator normalizes raw findings against `posting.severities` before posting.

## Finding Structure

Each finding must include:

1. `title`: short phrase naming the issue.
2. `body`: concise explanation focused on the code issue.
3. `evidence`: concrete code evidence when available.
4. `failure_scenario`: concrete failure or maintenance risk when available.
5. `suggested_fix`: specific change when available.

Use `null` for structured fields that are unavailable. Preserve the best supported raw severity instead of inflating severity to make a finding postable.

## Granularity

Prefer one finding per fix contract. A fix contract is the set of post-fix obligations and verification needed to resolve the issue for downstream LLM repair.

Group nearby issues when one fix contract resolves them. Split findings when obligations can remain broken independently, belong to different owners, or need separate verification. If one code line creates several boundary obligations that must be fixed together, group them in one finding and make `suggested_fix` list the complete post-fix obligations and verification.

Use inline comments for issues anchored to changed lines. Use overall comments for cross-file contracts, missing verification, repeated patterns, and review limitations that create concrete risk.

## Prior Comments

For re-review, read prior issue comments, review comments, and reviews before producing findings.

Suppress repeat comments when a prior reviewer already raised the same issue and the current diff has the same evidence. Record suppressed comments in `suppressed_prior_comments`.

## No Findings

Set the raw reviewer `verdict` to `APPROVE` when there are no evidence-backed raw findings at any severity. The final posting verdict is determined after normalization.
