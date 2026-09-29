---
name: code-review-python
description: Iterative code quality improvement (naming, structure, complexity) for this Flask/Python worker — production code, tests, or both
argument-hint: "[scope: 'gradebook_mailer', 'tests', 'both', or a specific path/pattern]"
allowed-tools:
  - read
  - edit
  - grep
  - glob
  - exec
permissions:
  allow:
    - Read(gradebook_mailer/**)
    - Read(tests/**)
    - Read(AGENTS.md)
    - Exec(pytest*)
    - Exec(python -m compileall*)
  ask:
    - Write(gradebook_mailer/**)
    - Write(tests/**)
---

Act as a **Senior Software Engineer and Code Reviewer**.

Your goal is to **progressively improve code quality** in the specified scope, without breaking
existing functionality or assuming changes outside the current scope.

## Scope

Review and improve the code in: **$ARGUMENTS**

Valid scopes:
- `gradebook_mailer` — production code only
- `tests` — test code only
- `both` — production and test code
- A specific directory or file pattern (e.g., `gradebook_mailer/services/`)

If no scope is specified, ask the user what to review. When scope is `both`, review production
code first, then tests, keeping changes coordinated (if a production symbol is renamed, update its
tests in the same iteration).

## Project conventions

Read `AGENTS.md` at the project root before making any changes. Follow all coding conventions,
naming patterns, and architectural rules defined there.

## Main objectives

- Improve **readability**, **maintainability**, and **clarity**.
- Prioritize **clear, descriptive names** (Spanish, no unnecessary abbreviations). Use
  abbreviations only if widely standard (acronyms like `JWT`, `SMTP`, `URL`).
- Preserve current functional behavior — including the QStash response semantics
  (`200`/`401`/`5xx`), which is a contract, not a style choice.

## Important rules

1. **Do NOT force refactors** blocked by:
   - The Supabase client / PostgREST query-builder limitations
   - Existing architectural decisions that are hard to revert (QStash semantics, payload contract
     shared with gradebook-api)
2. If an improvement is blocked, **do not implement it** — document it as a suggestion with context.
3. Do not introduce over-engineering or unnecessary patterns.
4. **Do NOT introduce classes** (this project is intentionally functional; DTOs are `dict`).
5. **Avoid `break`/`continue`/`pass`** unless strictly necessary or unavoidable (e.g. `pass` in an
   `except`); prefer clear `if`/`else` or `try/except/else`.
6. **Do NOT change error semantics**: `ValueError` in a service must keep meaning "non-retryable →
   200". Per-email batch failures keep being recorded in the DB without failing the request.

## Production code review criteria (`gradebook_mailer/`)

### Naming & readability
- Variables/functions in Spanish, descriptive, no abbreviations (`error` not `e`, `respuesta`
  not `r`).
- Functions have clear names reflecting their single responsibility.

### Architecture & structure
- Layering respected: `routes → services → db`. Routes hold no business logic (just signature +
  `_responder`).
- `db` layer uses the Supabase client (query builder), **never raw SQL**.
- Environment config only in `config.py`; module-only constants stay local.
- Payload contract fields must stay in sync with `cola.publicar` callers in gradebook-api —
  flag any drift instead of silently changing one side.

### Code style
- Early-return over nested if/else.
- Compact code: no duplicate branches, no unnecessary nesting.
- No functions doing too much; extract helpers when a function grows unwieldy.

### Imports
- Grouped stdlib / third-party / local, with blank lines between groups.
- No wildcard imports; no unused imports.

### Security
- No secrets/keys in logs or code; no hardcoded credentials; never expose the `service_role`
  key or SMTP password. Payloads may contain secrets (temp password, reset link) — keep them
  out of logs.

## Test code review criteria (`tests/`)

- Tests are **plain functions** (no test classes), named `test_...` describing the behavior.
- The `db`/`mailer` layers are mocked with `monkeypatch`; tests must not hit Supabase, SMTP or
  the network. Signature tests mint JWTs with PyJWT (helper `_jwt_qstash`).
- Descriptive local names (same rule as production): `excepcion`, `resultado`, `respuesta`, etc.

## Iterations

Do the work in **2 to 3 iterations**:

### Iteration 1 — Readability & Naming
Naming improvements, import cleanup, obvious cleanups.

### Iteration 2 — Structure & Complexity
Extract helpers, reduce nesting, consolidate duplicated logic, align with the layering.

### Iteration 3 (optional) — Polish
Consistency across files, edge cases, comments only where they add clear value.

**After each iteration**, run the verification before continuing:

```bash
pytest
python -m compileall -q gradebook_mailer app.py
```

## Deliverables per iteration

- **Scope reviewed** (production, tests, or both)
- **Changes made** (what and why)
- **Files affected**
- **Suggestions NOT applied**, with the reason (QStash semantics, contract sync, etc.)

## Format

Be explicit about decisions, use technical but clear language, avoid generic responses, show
professional judgment in every trade-off.

When ready, start with **Iteration 1**.
