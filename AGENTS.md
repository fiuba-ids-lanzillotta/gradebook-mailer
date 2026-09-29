# AGENTS.md

Guide for agents (and people) working on **gradebook-mailer**. Keep it short and actionable.

## Overview

Serverless email worker for **gradebook-api**: a small Flask app that consumes messages the
API publishes to **Upstash QStash** and sends the emails over SMTP (Flask-Mail). It covers
the four platform emails: attendance QR batches, attendance confirmation, docente welcome
(temporary password) and password reset.

- Endpoints: `POST /emails/qr-lote`, `/emails/confirmacion`, `/emails/bienvenida`,
  `/emails/recuperacion` (+ `GET /health` liveness, unsigned).
- **Auth**: the `Upstash-Signature` header (a JWT signed by QStash) is verified with
  `qstash.Receiver` in `gradebook_mailer/firma.py` — signature, `iss`, `sub` (the request
  URL, honoring `X-Forwarded-*` via `ProxyFix` in `app.py`), `exp`/`nbf` and the body
  sha256. Without signing keys the check is skipped with a warning (**dev mode**: you can
  hit the endpoints directly with curl/Bruno).
- **Data**: Supabase with the **service_role** key — reads `asistencias`/`estudiantes`/
  `clases` and writes the send state (`enviado`, `envio_intentos`, `envio_error`,
  `enviado_at`) in `gradebook_mailer/db.py`.
- **Response semantics are for QStash**: `200` = processed or non-retryable error (invalid
  payload / missing resource → logged and discarded; per-email failures in a QR batch are
  recorded in the DB and never fail the request); `401` = bad signature; `5xx` = transient
  infra failure (QStash retries with backoff, then DLQ).

Context and design decisions live in `docs/worker-asincrono-qrs.md` of the
`gradebook-api` repo; the payload contract lives in `docs/swagger.yaml` here.

## How to run

```bash
# setup + run (crea el venv, instala deps y levanta el worker en :5002)
scripts\setup_virtualenv.bat   # Windows          (variante pipenv: scripts\setup_pipenv.bat)
scripts/setup_virtualenv.sh    # Linux / macOS    (variante pipenv: scripts/setup_pipenv.sh)

# o manualmente
python -m venv .venv && .venv\Scripts\activate   # (source .venv/bin/activate on Linux/macOS)
pip install -r requirements.txt
python app.py                                  # serves on :5002
```

Requires a `.env` (see `.env.example`): `SUPABASE_URL` + `SUPABASE_KEY` (service_role, same
project as gradebook-api), `MAIL_*` (SMTP — without credentials or with
`MAIL_SUPPRESS_SEND=true` emails are logged, not sent), and
`QSTASH_CURRENT_SIGNING_KEY`/`QSTASH_NEXT_SIGNING_KEY` (without them, signature check is
skipped — dev mode).

## Verification (run before considering a change done)

```bash
pip install -r requirements-dev.txt
pytest                                          # services + endpoints, db/mailer mocked (no network)
python -m compileall -q gradebook_mailer app.py # syntax check
```

`conftest.py` sets dummy Supabase creds, suppresses SMTP and clears the signing keys, so
tests never hit the network. Signature tests mint real QStash-style JWTs with PyJWT.

## Code conventions

Same as gradebook-api:
- **Functional style: do NOT use classes.** Payloads/results are `dict`.
- **Avoid `break`/`continue`/`pass`** unless strictly necessary or unavoidable.
- **Spanish naming, no abbreviations** (`error` not `e`, `respuesta` not `r`).
- **Layers**: `routes → services → db`. Payload validation lives in the service — a bad
  payload is a non-retryable error: raise `ValueError(...)` and the route answers `200` so
  QStash drops the message instead of retrying pointlessly.
- `db` uses the Supabase client (query builder), **never raw SQL**.
- `config.py` = environment configuration; module-only constants stay local.
- Don't add/remove comments needlessly; mirror the existing style.

## How to add a new email type

1. Define the payload contract first (it must match what `gradebook_api/cola.py` will
   publish — update `docs/swagger.yaml` here (the contract) and flag `docs/flujos.md`
   in the gradebook-api repo if a diagram depicts it).
2. `gradebook_mailer/mailer.py`: `enviar_email_<tipo>(...)` + template
   `gradebook_mailer/templates/emails/<tipo>.html`.
3. `gradebook_mailer/services/emails.py`: `procesar_<tipo>(body)` — validate the payload
   (`ValueError` if invalid), send, return a dict.
4. `gradebook_mailer/routes/emails.py`: `POST /emails/<tipo>` with `@requiere_firma_qstash()`.
5. gradebook-api side: call `cola.publicar('/emails/<tipo>', payload)` at the trigger point.
6. Tests: service-level (mailer/db mocked) + an endpoint test.

There is an `add-email` skill in `.agents/skills/` that automates this checklist.

## Skills

Project skills live in `.agents/skills/` (committed; tool-agnostic `.agents` standard):
`verify`, `add-email`, `sync-docs`, `sync-bruno`, `deploy-vercel`, `code-review-python`.

## Deploy

Vercel (`vercel.json`, Python function over `app.py`, `maxDuration: 60`). Environment
variables are set in the Vercel dashboard (not via `.env`): Supabase creds, `MAIL_*`, and
the QStash signing keys (Upstash console → QStash). On key rotation set the new key as
`QSTASH_NEXT_SIGNING_KEY` first, promote it to `CURRENT`, then update `NEXT`.

## Do not

- Do not introduce classes.
- Do not run raw SQL (use the Supabase client).
- Do not expose or commit secrets (`.env`, signing keys, `service_role`, SMTP password).
- Do not return `5xx` for per-email or payload errors — QStash would retry forever.
- Do not change a payload contract without updating the `cola.publicar` callers in
  gradebook-api (and vice versa).

## Git

- Commit messages in Spanish, focused on the "why".
- Do not push unless explicitly asked.

## Pointers

- Context + design decisions: `docs/worker-asincrono-qrs.md` (gradebook-api repo);
  end-to-end flow diagrams in `docs/flujos.md` there.
- OpenAPI (the payload contract): `docs/swagger.yaml`.
- Bruno collection: `../../bruno-workspace/gradebook-mailer-collection` (kept in sync via
  the `sync-bruno` skill).
- Publisher side: `gradebook_api/cola.py` (gradebook-api repo).
