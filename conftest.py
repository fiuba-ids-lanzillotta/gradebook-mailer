"""
Config compartida de pytest.

Fija credenciales dummy de Supabase antes de importar la app, para que el
cliente se pueda construir sin depender del entorno real. Los tests cubren
funciones puras (servicios con la db mockeada) y no hacen llamadas de red.

Sin signing keys de QStash, la verificación de firma queda en modo dev (se
saltea con warning), así los tests de rutas pueden pegarle a los endpoints.
"""
import os

os.environ.setdefault('SUPABASE_URL', 'http://localhost:54321')
os.environ.setdefault('SUPABASE_KEY', 'test-key')

# Suprimir el envío de emails en los tests (ningún test debe abrir conexión SMTP,
# ni siquiera la compartida de un lote).
os.environ['MAIL_SUPPRESS_SEND'] = 'true'

# Deshabilitar la verificación de firma QStash en los tests (modo dev); los tests
# que la cubren setean sus propias keys con monkeypatch. Se fija explícitamente
# para que `load_dotenv` no tome las keys reales del .env.
os.environ['QSTASH_CURRENT_SIGNING_KEY'] = ''
os.environ['QSTASH_NEXT_SIGNING_KEY'] = ''

# Tests: acelerar pausas y backoffs de envío de QRs para no ralentizar la suite.
os.environ['ASISTENCIA_EMAILS_PAUSA_MS'] = '0'
os.environ['ASISTENCIA_EMAILS_BACKOFF_MS'] = '0'
os.environ['ASISTENCIA_DB_BACKOFF_MS'] = '0'
