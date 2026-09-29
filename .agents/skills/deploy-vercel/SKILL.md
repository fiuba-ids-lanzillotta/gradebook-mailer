---
name: deploy-vercel
description: Checklist to deploy this email worker to Vercel (config, QStash wiring and required environment variables)
allowed-tools:
  - read
  - grep
  - glob
permissions:
  allow:
    - Read(**)
---

Guide the deploy of gradebook-mailer to Vercel. This is mostly a checklist; do not commit
secrets.

## Config

- `vercel.json` defines a Python function over `app.py` (`includeFiles: "gradebook_mailer/**"`
  so the email templates ship) with `maxDuration: 60` — enough for a QR batch of ~5 with SMTP
  pauses/retries.
- The entry point is `app.py`, which exposes the WSGI `app` (with `ProxyFix` so `request.url`
  is the public https URL that QStash signs).

## Environment variables (Vercel dashboard, NOT .env)

Required:
- `SUPABASE_URL`, `SUPABASE_KEY` — same project as gradebook-api; **service_role** key.
- `MAIL_USERNAME`, `MAIL_PASSWORD` — Gmail account + App Password.
- `QSTASH_CURRENT_SIGNING_KEY`, `QSTASH_NEXT_SIGNING_KEY` — Upstash console → QStash →
  signing keys. Without them the endpoints accept unsigned requests (dev mode) — do NOT
  leave them empty in production.

Recommended/optional:
- `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`, `MAIL_USE_SSL`, `MAIL_DEFAULT_SENDER`
  (defaults: smtp.gmail.com:587 TLS, sender = MAIL_USERNAME).
- Tunables: `ASISTENCIA_EMAILS_PAUSA_MS` (500), `ASISTENCIA_EMAILS_MAX_REINTENTOS` (2),
  `ASISTENCIA_EMAILS_BACKOFF_MS` (2000), `ASISTENCIA_DB_MAX_REINTENTOS` (3),
  `ASISTENCIA_DB_BACKOFF_MS` (100).

## QStash wiring (in gradebook-api's environment)

- `MAIL_WORKER_URL` = this deployment's URL (e.g. `https://gradebook-mailer.vercel.app`).
- `QSTASH_TOKEN` (publish token) and `QSTASH_URL` (regional base from the console) go in the
  **API**, not here.

## Smoke test after deploy

- `GET /health` → `{"ok": true}`.
- `POST /emails/bienvenida` without signature → must be `401` (proves verification is on).
- Trigger a real email from the API (e.g. create a docente) and check QStash console
  delivery + logs.

## Notes

- The database is external (Supabase): same project as the API; no schema of its own.
- `truststore` is only relevant for local corporate-TLS networks; harmless on Vercel.
