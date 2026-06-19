# Quality Profile Authoring

Use this reference when the user asks to create or improve the repository quality profile.

## Purpose

The quality profile gives reviewers repository-specific criteria that are more precise than general code review advice. Treat it as prompt authoring for reviewers: every rule should improve model judgment by adding repository context, concrete evidence targets, or local policy.

## File

Use the path configured in `.agents/pr-review/config.yaml` at `quality.path`. The default is `.agents/pr-review/quality/code.yaml`.

## Schema Shape

```yaml
id: repository-code-quality
version: 1
review_dimensions:
  - id: correctness
    required: true
    pass: Changed behavior satisfies the requested outcome and preserves existing behavior in touched paths.
project_rules:
  - id: stable_contract_name
    pass: Specific repository rule reviewers enforce.
```

## Authoring Steps

1. Inspect repository evidence before proposing changes.
2. Identify recurring review criteria from repository evidence and user policy.
3. Present a proposed profile before writing it. Include each rule, its evidence source, and any intentionally omitted generic rule.
4. Ask for approval and additional repository-specific standards.
5. Write the configured quality file after approval.
6. Report the path written and the evidence used for each rule.

Ask questions after repository inspection when a policy choice affects review behavior, such as strictness, blocking domains, security expectations, external services, generated files, migrations, release constraints, or whether an inferred convention is actually required.

## Prompt Quality Rules

Quality criteria are prompts. Write them so a reviewer can apply them consistently:

- Use positive `pass` statements that describe the accepted state.
- Attach each repository-specific rule to evidence: a doc, test, schema, CI job, code pattern, or user policy.
- Prefer concrete contracts over broad advice.
- Focus on repository evidence beyond general programming knowledge.
- Define when a rule applies and the evidence to inspect.
- Capture the invariant a reviewer should preserve across sibling cases when a rule protects a boundary or contract.
- Use uncertainty explicitly when a likely convention needs confirmation.

Good:

```yaml
project_rules:
  - id: api-error-contract
    pass: API handlers return the repository-standard error envelope and clients parse that envelope through the shared client utilities.
  - id: generated-schema-ownership
    pass: Generated schema files are updated through the documented generator command, with source schema changes in the same PR.
```

Too broad:

```yaml
project_rules:
  - id: quality
    pass: Code is clean and secure.
```

## Evidence Targets

Look for:

- correctness and behavior preservation: requested behavior, regression tests, compatibility notes, existing behavior in touched paths
- public contracts: API routes, DTOs, GraphQL schemas, OpenAPI specs, protobufs, CLI flags, package exports
- producer/consumer pairs: server/client code, event publishers/consumers, schema/generator pairs
- persistence: migrations, indexes, ordering, filtering, pagination, transaction boundaries, rollback notes
- generated code: source-of-truth files, generator commands, committed output ownership
- testing conventions: CI workflows, package scripts, existing regression patterns, required services
- UI contracts: accessibility, responsive states, loading/error/empty states, text overflow, visual verification
- operations: deployment docs, feature flags, observability, logging, rollback, release process
- security: authentication, authorization, input validation, secrets handling, unsafe IO, dependency or supply-chain policy
- architecture and ownership: local module boundaries, import direction, layering rules, package ownership, extension points
- invariants across sibling cases: the same contract applied to fallback paths, empty or missing values, retries, lifecycle states, adjacent fields, and producer/consumer pairs

## Boundaries

Add criteria only when repository evidence supports them. Put product-specific policy in the profile after the repository provides that evidence.

General LLM knowledge already covers common review basics such as type safety, error handling, readable structure, and ordinary test expectations. Add a general-looking dimension only when it tells the reviewer how this repository applies that knowledge.

Security criteria should be language-independent unless the repository evidence is language-specific. Prefer boundaries and evidence targets over technology slogans:

```yaml
review_dimensions:
  - id: security-boundaries
    required: true
    pass: Changes touching auth, authorization, secrets, external input, file/network IO, dependency loading, or deployment config include evidence that the repository-owned security boundary remains intact.
project_rules:
  - id: secret-handling
    pass: Configuration changes keep secrets in the repository-approved secret source and expose only safe placeholder values in committed files.
```

## Proposal Format

Before writing the profile, present:

```markdown
Quality profile proposal:
- path: <quality.path>
- review dimensions:
  - <id>: <pass statement>
- project rules:
  - <id>: <pass statement>

Evidence:
- <repo file or user answer>: <profile decision>

Omitted candidates:
- <candidate rule>: <why it is generic, unsupported, or irrelevant>

Write this quality profile?
```
