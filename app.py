import logging
import os

# Usar el almacén de certificados del sistema operativo para verificar TLS.
# Necesario en entornos con inspección SSL corporativa (root CA propio en la
# cadena). Debe ejecutarse antes de crear el cliente de Supabase (httpx).
import truststore
truststore.inject_into_ssl()

from flask import Flask, jsonify
from flask_mail import Mail
from werkzeug.middleware.proxy_fix import ProxyFix

from gradebook_mailer.config import (
    MAIL_SERVER,
    MAIL_PORT,
    MAIL_USE_TLS,
    MAIL_USE_SSL,
    MAIL_USERNAME,
    MAIL_PASSWORD,
    MAIL_DEFAULT_SENDER,
    MAIL_SUPPRESS_SEND,
)
from gradebook_mailer.routes.emails import emails_bp

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(name)s - %(message)s')

_BASE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(_BASE, 'gradebook_mailer', 'templates'))

# Detrás de Vercel: honrar X-Forwarded-Proto/Host para que request.url sea la URL
# pública (https), que es lo que QStash firma en el claim `sub` del JWT.
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Email (Flask-Mail): si no hay credenciales, el mailer loguea en vez de enviar
# (modo dev).
app.config.update(
    MAIL_SERVER=MAIL_SERVER,
    MAIL_PORT=MAIL_PORT,
    MAIL_USE_TLS=MAIL_USE_TLS,
    MAIL_USE_SSL=MAIL_USE_SSL,
    MAIL_USERNAME=MAIL_USERNAME,
    MAIL_PASSWORD=MAIL_PASSWORD,
    MAIL_DEFAULT_SENDER=MAIL_DEFAULT_SENDER,
    MAIL_SUPPRESS_SEND=MAIL_SUPPRESS_SEND,
)
Mail(app)

app.register_blueprint(emails_bp)


@app.route('/health')
def health():
    """Liveness para monitoreo; no consume mensajes ni requiere firma."""
    return jsonify({'ok': True, 'servicio': 'gradebook-mailer'})


if __name__ == '__main__':
    app.run(debug=True, port=5002)
