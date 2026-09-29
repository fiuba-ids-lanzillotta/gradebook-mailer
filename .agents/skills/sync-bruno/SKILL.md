---
name: sync-bruno
description: Keep the Bruno collection of this worker in sync with its endpoints and request/response formats
allowed-tools:
  - read
  - edit
  - write
  - grep
  - glob
permissions:
  allow:
    - Read(**)
  ask:
    - Write(**)
---

Keep the Bruno collection in sync with the current worker endpoints. Use this after
adding/changing/removing `/emails/*` endpoints or changing payloads/responses.

## Reference the source of truth

1. Read `docs/swagger.yaml` and `gradebook_mailer/routes/emails.py` for the current endpoints,
   methods and bodies; `gradebook_mailer/services/emails.py` for the validated payload fields
   and response shapes.

## Update the collection

The Bruno collection lives in a separate repo:
`../../bruno-workspace/gradebook-mailer-collection`. For each change:

- **New endpoint** → add a `.bru` request under `Emails/` (sequential `seq`), method POST,
  URL `{{protocol}}://{{host}}/emails/<tipo>`, `auth: none`, a realistic `body:json` example
  matching the validated payload, and a `docs` block with the semantics (what it sends,
  idempotency, response shape).
- **Changed payload/format** → update the `body:json` and the `docs` block.
- **Removed endpoint** → delete the corresponding `.bru`.
- `/health` lives at the collection root.
- Keep environment variables (`protocol`, `host`) consistent; environments are
  `Local` (`localhost:5002`) and `Produccion` (the Vercel URL).

## Notes

- Requests are unsigned on purpose: without signing keys the worker skips signature
  verification (dev mode). With keys configured the requests would get 401 — that is
  expected and documented in `collection.bru`.

## Verify

- Each `.bru` URL/body matches the route and the `procesar_*` payload contract.
- Docs blocks reflect the current response semantics (200/401/5xx).
