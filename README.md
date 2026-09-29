# gradebook-mailer

Worker serverless de emails para gradebook-api: consume mensajes de **Upstash
QStash** y envía los emails por SMTP (Flask-Mail): QRs de asistencia,
confirmación de asistencia, bienvenida a docentes y recuperación de contraseña.

El contexto y las decisiones de diseño están en `docs/worker-asincrono-qrs.md` del
repo `gradebook-api`; los flujos end-to-end en `docs/flujos.md` del mismo repo.

## Endpoints

Todos `POST`, autenticados por la firma `Upstash-Signature` (401 si no verifica):

| Endpoint | Payload |
|---|---|
| `/emails/qr-lote` | `{"clase_id": 5, "asistencia_ids": [1,2,3,4,5]}` |
| `/emails/confirmacion` | `{"asistencia_id": 123}` |
| `/emails/bienvenida` | `{"destinatario", "nombre?", "apellido?", "rol", "password"}` |
| `/emails/recuperacion` | `{"destinatario", "nombre?", "apellido?", "link"}` |
| `GET /health` | liveness (sin firma) |

Semántica de respuestas: `200` = procesado o error no-reintentable (payload
inválido → se descarta); `5xx` = falla transitoria → QStash reintenta.

Contrato completo (OpenAPI 3.0) en `docs/swagger.yaml`.

Colección Bruno para probar los endpoints en local:
`../../bruno-workspace/gradebook-mailer-collection` (misma estructura que la del API;
las requests van sin firma — el modo dev del worker la saltea).

## Setup

```bash
scripts\setup_virtualenv.bat   # Windows          (también: scripts\setup_pipenv.bat)
scripts/setup_virtualenv.sh    # Linux / macOS    (también: scripts/setup_pipenv.sh)
# o manualmente
python -m venv .venv && .venv\Scripts\activate   # (source .venv/bin/activate en Linux/macOS)
pip install -r requirements.txt
python app.py    # levanta en :5002
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest                                          # servicios con db/mailer mockeados
python -m compileall -q gradebook_mailer app.py # syntax check
```

## Variables de entorno

Ver `.env.example`. Para correr el worker contra la **base local** de Supabase
(`supabase start` en `gradebook-api`): `.env.local` copia el `.env` y solo cambia
`SUPABASE_URL`/`SUPABASE_KEY`; `scripts\use_local_db.bat` / `scripts\use_prod_db.bat`
swappean el `.env` (ambos archivos gitignored). Con `MAIL_*` configuradas el worker envía
emails reales. Si además querés que **QStash le entregue los mensajes al worker local**
(en vez del deploy de Vercel), exponelo con un túnel (`npx localtunnel --port 5002` o
`ngrok http 5002`) y poné esa URL en `MAIL_WORKER_URL` de la API.

Puntos clave:

- Sin `QSTASH_*_SIGNING_KEY` la verificación de firma se saltea (modo dev, con
  warning) — permite pegarle a los endpoints con curl/Bruno en local.
- Sin credenciales `MAIL_*` (o `MAIL_SUPPRESS_SEND=true`) los emails se loguean
  en vez de enviarse (modo dev/tests).
- `SUPABASE_KEY` es la **service_role** (misma base que gradebook-api).

## Deploy

Vercel (`vercel.json`, función Python sobre `app.py`). Las variables de entorno
se configuran en el dashboard de Vercel. En la consola de Upstash → QStash hay
que copiar las signing keys a `QSTASH_CURRENT_SIGNING_KEY`/`_NEXT_SIGNING_KEY`.
