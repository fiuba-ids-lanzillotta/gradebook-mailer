"""
Configuración por variables de entorno de gradebook-mailer.

Credenciales de Supabase/SMTP, signing keys de QStash y tunables de reintentos.
`load_dotenv` lee el `.env` local; en Vercel las variables vienen del dashboard.
"""
import os

from dotenv import load_dotenv

load_dotenv()

# --- Supabase ---
# La service_role key es secreta: el worker lee asistencias/estudiantes/clases y
# escribe el estado de envío (enviado, envio_intentos, envio_error, enviado_at).
SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')

# --- Firma de QStash ---
# Signing keys para verificar el JWT del header Upstash-Signature. La NEXT se
# usa durante la rotación de la vigente. Sin keys: verificación en modo dev.
QSTASH_CURRENT_SIGNING_KEY = os.getenv('QSTASH_CURRENT_SIGNING_KEY', '')
QSTASH_NEXT_SIGNING_KEY    = os.getenv('QSTASH_NEXT_SIGNING_KEY', '')

# --- Envío de emails ---
# Pausa entre emails del lote (ms) y reintentos ante errores transitorios de red
# del SMTP (throttling de Gmail) y de Supabase al persistir el estado del envío.
ASISTENCIA_EMAILS_PAUSA_MS       = int(os.getenv('ASISTENCIA_EMAILS_PAUSA_MS', '500'))
ASISTENCIA_EMAILS_MAX_REINTENTOS = int(os.getenv('ASISTENCIA_EMAILS_MAX_REINTENTOS', '2'))
ASISTENCIA_EMAILS_BACKOFF_MS     = int(os.getenv('ASISTENCIA_EMAILS_BACKOFF_MS', '2000'))
ASISTENCIA_DB_MAX_REINTENTOS     = int(os.getenv('ASISTENCIA_DB_MAX_REINTENTOS', '3'))
ASISTENCIA_DB_BACKOFF_MS         = int(os.getenv('ASISTENCIA_DB_BACKOFF_MS', '100'))

# --- Email (Flask-Mail / SMTP) ---
# Si MAIL_USERNAME/MAIL_PASSWORD están vacíos o MAIL_SUPPRESS_SEND=true, no se
# envía nada: se loguea (modo dev/tests). Con Gmail, MAIL_PASSWORD es un
# "App Password" (no la clave de la cuenta).
MAIL_SERVER         = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
MAIL_PORT           = int(os.getenv('MAIL_PORT', '587'))
MAIL_USE_TLS        = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
MAIL_USE_SSL        = os.getenv('MAIL_USE_SSL', 'false').lower() == 'true'
MAIL_USERNAME       = os.getenv('MAIL_USERNAME', '')
MAIL_PASSWORD       = os.getenv('MAIL_PASSWORD', '')
# Remitente. Si se deja vacío, usa MAIL_USERNAME (Gmail exige que el from sea la
# cuenta autenticada).
MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', '') or MAIL_USERNAME
MAIL_SUPPRESS_SEND  = os.getenv('MAIL_SUPPRESS_SEND', 'false').lower() == 'true'
