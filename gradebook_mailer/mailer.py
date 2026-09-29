"""
Envío de emails (Flask-Mail / SMTP). Copia adaptada de `gradebook_api/mailer.py`.

Env-gated: si no hay credenciales de mail (`MAIL_USERNAME`/`MAIL_PASSWORD`) o
`MAIL_SUPPRESS_SEND=true`, no se envía nada: se loguea el link/password (modo dev).

Diferencia con la API: acá los transaccionales (confirmación, bienvenida y
recuperación) NO son fail-safe — propagan la excepción para que el endpoint
responda 5xx y QStash reintente el mensaje.
"""
import logging
from contextlib import contextmanager

from flask import current_app, render_template
from flask_mail import Mail, Message

from .config import (
    MAIL_USERNAME,
    MAIL_PASSWORD,
    MAIL_SUPPRESS_SEND,
)

logger = logging.getLogger(__name__)


def _mail_configurado() -> bool:
    return bool(MAIL_USERNAME and MAIL_PASSWORD) and not MAIL_SUPPRESS_SEND


@contextmanager
def conexion_email():
    """
    Abre una conexión SMTP reusable para enviar un lote de emails, evitando el
    handshake TLS/AUTH por mensaje (que Gmail penaliza cortando la conexión).

    Cede `None` si el mail está deshabilitado o no se pudo abrir: en ese caso los
    envíos caen a una conexión por email. Al salir del `with` la cierra.
    """
    if not _mail_configurado():
        yield None
        return

    try:
        gestor   = Mail(current_app).connect()
        conexion = gestor.__enter__()
    except Exception as error:
        logger.warning(f'[asistencia] Sin conexión SMTP compartida ({error}); se enviará con una por email')
        
        yield None
        return

    try:
        yield conexion
    finally:
        gestor.__exit__(None, None, None)


def enviar_email_qr_asistencia(destinatario: str, nombre: str, clase: dict,
                               codigo: str, qr_png: bytes, apellido: str = '',
                               conexion=None) -> None:
    """
    Envía el email con el QR de asistencia (PNG inline) para una clase.

    Propaga la excepción si el SMTP falla: el service la registra en la base
    (`envio_intentos`/`envio_error`) sin fallar el request a QStash. Si el mail
    no está configurado (dev/tests), loguea y no envía (se toma como ok).
    `conexion` (opcional) es la conexión SMTP compartida del lote; sin ella se
    abre una nueva para este envío.
    """
    if not _mail_configurado():
        logger.warning(f'[asistencia] Email deshabilitado; QR para {destinatario} codigo={codigo}')

        return

    mensaje = Message(
        subject='Clase presencial obligatoria Lanzillota',
        recipients=[destinatario],
        html=_cuerpo_html_qr(nombre, clase, codigo, apellido),
    )
    mensaje.attach(
        'qr-asistencia.png',
        'image/png',
        qr_png,
        disposition='inline',
        headers={'Content-ID': '<qr_asistencia>'},
    )

    if conexion is not None:
        conexion.send(mensaje)
    else:
        Mail(current_app).send(mensaje)


def _cuerpo_html_qr(nombre: str, clase: dict, codigo: str, apellido: str = '') -> str:
    saludo = f"{(apellido or '').strip()} {(nombre or '').strip()}".strip() or 'estudiante'
    fecha = str(clase.get('fecha') or '')[:10]

    return render_template(
        'emails/asistencia_qr.html',
        saludo=saludo,
        fecha=fecha,
        codigo=codigo or '',
    )


def enviar_email_confirmacion_asistencia(destinatario: str, nombre: str, apellido: str,
                                         clase: dict) -> None:
    """
    Envía confirmación de que se registró la asistencia del estudiante a la clase.

    Propaga la excepción si el SMTP falla: el endpoint responde 5xx y QStash
    reintenta el mensaje. Si el mail no está configurado (dev/tests), loguea.
    """
    if not _mail_configurado():
        logger.warning(f'[asistencia] Email deshabilitado; confirmación para {destinatario}')

        return

    mensaje = Message(
        subject='Asistencia registrada',
        recipients=[destinatario],
        html=_cuerpo_html_confirmacion_asistencia(nombre, apellido, clase),
    )

    Mail(current_app).send(mensaje)


def _cuerpo_html_confirmacion_asistencia(nombre: str, apellido: str, clase: dict) -> str:
    saludo = f"{(apellido or '').strip()} {(nombre or '').strip()}".strip() or 'estudiante'
    fecha  = str(clase.get('fecha') or '')[:10]

    return render_template(
        'emails/asistencia_confirmada.html',
        saludo=saludo,
        fecha=fecha,
    )


def enviar_email_nuevo_docente(destinatario: str, nombre: str, apellido: str,
                                rol: str, password: str) -> None:
    """
    Envía el email de bienvenida a un nuevo docente con su contraseña temporal.

    Propaga la excepción si el SMTP falla: el endpoint responde 5xx y QStash
    reintenta el mensaje. Si el mail no está configurado (dev/tests), loguea la
    password (mismo comportamiento de dev que la API).
    """
    if not _mail_configurado():
        logger.warning(f'[nuevo-docente] Email deshabilitado; password para {destinatario}: {password}')

        return

    mensaje = Message(
        subject='Bienvenido a Gradebook Lanzillotta',
        recipients=[destinatario],
        html=_cuerpo_html_nuevo_docente(nombre, apellido, rol, password),
    )

    Mail(current_app).send(mensaje)


def _cuerpo_html_nuevo_docente(nombre: str, apellido: str, rol: str, password: str) -> str:
    saludo = f"{(apellido or '').strip()} {(nombre or '').strip()}".strip() or 'docente'

    return render_template(
        'emails/nuevo_docente.html',
        saludo=saludo,
        rol=rol,
        password=password,
    )


def enviar_email_recuperacion(destinatario: str, link: str,
                              nombre: str = '', apellido: str = '') -> None:
    """
    Envía el email con el link de recuperación de contraseña.

    Propaga la excepción si el SMTP falla: el endpoint responde 5xx y QStash
    reintenta el mensaje. Si el mail no está configurado (dev/tests), loguea el
    link (mismo comportamiento de dev que la API).
    """
    if not _mail_configurado():
        logger.warning(f'[password-reset] Email deshabilitado; link para {destinatario}: {link}')

        return

    mensaje = Message(
        subject='Recuperá tu contraseña',
        recipients=[destinatario],
        html=_cuerpo_html_recuperacion(link, nombre, apellido),
    )

    Mail(current_app).send(mensaje)


def _cuerpo_html_recuperacion(link: str, nombre: str = '', apellido: str = '') -> str:
    saludo = f"{(apellido or '').strip()} {(nombre or '').strip()}".strip() or 'estudiante'

    return render_template(
        'emails/recuperacion.html',
        saludo=saludo,
        link=link,
    )
