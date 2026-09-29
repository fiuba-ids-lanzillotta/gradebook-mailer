---
name: sync-docs
description: Audit and update README.md and docs/swagger.yaml so the documentation matches the current code
allowed-tools:
  - read
  - edit
  - grep
  - glob
permissions:
  allow:
    - Read(**)
  ask:
    - Write(README.md)
    - Write(docs/**)
---

Keep the documentation in sync with the code. **Only touch documentation** (`README.md`,
`docs/swagger.yaml`) — never change application code from this skill.

## Sources of truth

Read the code and compare it against the docs:
- `gradebook_mailer/routes/emails.py` — endpoints, methods, the signature decorator.
- `gradebook_mailer/services/emails.py` — payload fields each message type expects/validates
  and the response dicts returned.
- `gradebook_mailer/firma.py` — signature semantics (401, dev mode without keys).
- `gradebook_mailer/config.py` / `.env.example` — the full set of environment variables.
- `gradebook_mailer/mailer.py` — the senders and which fields they consume.
- `app.py` — registered blueprints, `/health`, `ProxyFix`.
- Payload contract cross-check: `docs/swagger.yaml` here is the contract — the
  `cola.publicar` call sites in `gradebook_api/services/` (gradebook-api repo) must match
  it field by field.
  If a payload/path/step changes, flag that `docs/flujos.md` in the `gradebook-api` repo
  needs the same update (the flow diagrams live there).

## What to check and fix

### `docs/swagger.yaml`
- Every route in `routes/emails.py` (+ `/health`) has a matching path/method; no stale paths.
- Request schemas match the payload each `procesar_*` validates (required fields, types).
- Response schemas match the dicts returned, and the `200` responses keep both shapes
  (success + `ErrorNoReintentable`). `401` and `5xx` semantics as documented in the routes
  docstring.

### `README.md`
- **Endpoints table** matches the routes and their payloads.
- **Env vars** section lists exactly what `config.py` reads (and `.env.example`), incl. dev
  behaviors (no signing keys → signature skipped; no `MAIL_*` → emails logged).
- No stale references (removed features, old names).

## Method

1. Build the real list of endpoints + payloads + responses from `routes/` and `services/`.
2. Build the real env var list from `config.py` + `.env.example`.
3. Cross-check against the docs and apply fixes. Do not invent behavior — if unsure, inspect
   the code (or the publisher side in `gradebook-api`).

## Deliverable

Report the mismatches found and the fixes applied, grouped by file (`README.md`,
`docs/swagger.yaml`). If everything was already consistent, say so explicitly.
