"""
Endpoints que reciben los mensajes de QStash (un endpoint por tipo de email).

Semántica de respuestas (contrato en `docs/swagger.yaml`; decisiones en
`docs/worker-asincrono-qrs.md` de gradebook-api):

- `200` si el mensaje se procesó, o si tiene un error no-reintentable (payload
  inválido, recurso inexistente): se loguea y se descarta, reintentar no arregla
  nada.
- `401` si la firma `Upstash-Signature` no verifica.
- `5xx` ante fallas transitorias (Supabase/SMTP caídos) para que QStash
  reintente el mensaje.
"""
import logging

from flask import Blueprint, request, jsonify

from ..firma import requiere_firma_qstash
from ..services import emails

logger = logging.getLogger(__name__)

emails_bp = Blueprint('emails', __name__)


@emails_bp.route('/emails/qr-lote', methods=['POST'])
@requiere_firma_qstash()
def post_qr_lote():
    """Lote de QRs de asistencia: {clase_id, asistencia_ids}."""
    return _responder(emails.procesar_qr_lote)


@emails_bp.route('/emails/confirmacion', methods=['POST'])
@requiere_firma_qstash()
def post_confirmacion():
    """Confirmación de asistencia registrada: {asistencia_id}."""
    return _responder(emails.procesar_confirmacion)


@emails_bp.route('/emails/bienvenida', methods=['POST'])
@requiere_firma_qstash()
def post_bienvenida():
    """Bienvenida a docente con password temporal: {destinatario, nombre?, apellido?, rol, password}."""
    return _responder(emails.procesar_bienvenida)


@emails_bp.route('/emails/recuperacion', methods=['POST'])
@requiere_firma_qstash()
def post_recuperacion():
    """Link de recuperación de contraseña: {destinatario, nombre?, apellido?, link}."""
    return _responder(emails.procesar_recuperacion)


def _responder(procesar):
    """
    Ejecuta el procesamiento del mensaje y traduce el resultado a la semántica de
    QStash: ValueError → 200 (no-reintentable); el resto propaga → 500.
    """
    body = request.get_json(silent=True) or {}

    try:
        return jsonify(procesar(body)), 200
    except ValueError as error:
        logger.warning(f'[emails] Mensaje descartado (no reintentable): {error}')
        
        return jsonify({'ok': False, 'error': str(error)}), 200
