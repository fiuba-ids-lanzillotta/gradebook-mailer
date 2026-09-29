---
name: add-email
description: Add a new email type (endpoint + service + mailer + template) following the project's conventions and the QStash contract
argument-hint: "[email type, e.g. 'aviso-falta']"
allowed-tools:
  - read
  - edit
  - write
  - grep
  - glob
  - exec
permissions:
  allow:
    - Read(**)
    - Exec(pytest*)
    - Exec(python -m compileall*)
  ask:
    - Write(gradebook_mailer/**)
    - Write(tests/**)
    - Write(docs/**)
---

Add a new email type: **$ARGUMENTS**. Read `AGENTS.md` first and mirror the existing
`qr-lote`/`confirmacion`/`bienvenida`/`recuperacion` types.

## Checklist

1. **Contract first**: decide the payload (fields, required/optional) and whether it needs
   Supabase reads (like `qr-lote`/`confirmacion`) or carries everything in the payload (like
   `bienvenida`/`recuperacion`). Update `docs/swagger.yaml` here (the contract) and flag
   `docs/flujos.md` in the gradebook-api repo if a diagram depicts the flow.

2. **mailer** (`gradebook_mailer/mailer.py`): `enviar_email_<tipo>(destinatario, ...)` using
   the shared `conexion_email()` pattern if it's a batch, plus the `_mail_configurado()`
   dev-mode log. Template in `gradebook_mailer/templates/emails/<tipo>.html` (mirror the
   existing ones).

3. **service** (`gradebook_mailer/services/emails.py`): `procesar_<tipo>(body) -> dict`.
   Validate the payload: missing/invalid fields → `raise ValueError('Payload inválido: ...')`
   (route turns it into `200` so QStash drops it — never `5xx` for bad input). If it reads
   Supabase, add the query to `gradebook_mailer/db.py` (query builder, no raw SQL).
   `ValueError` also for missing resources (idempotency: a retry for deleted data must not
   retry forever).

4. **route** (`gradebook_mailer/routes/emails.py`): `POST /emails/<tipo>` with
   `@requiere_firma_qstash()` delegating to `_responder(emails.procesar_<tipo>)`.

5. **publisher side** (gradebook-api repo): call `cola.publicar('/emails/<tipo>', {...})`
   from the right service. Keep field names identical on both sides.

6. **tests** (`tests/`): a service-level test (mailer/db mocked via `monkeypatch`), a payload-
   validation test (ValueError), and an endpoint test via `app.test_client()`.

7. **Verify:**
   ```bash
   pytest
   python -m compileall -q gradebook_mailer app.py
   ```

Report the files added/changed, the payload contract, and what needs publishing on the API side.
