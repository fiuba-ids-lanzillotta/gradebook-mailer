"""
Procesamiento de los mensajes encolados por gradebook-api en QStash.

Una función por tipo de email (contrato en `docs/swagger.yaml`; decisiones en
`docs/worker-asincrono-qrs.md` de gradebook-api). Semántica de errores:

- `ValueError` = error no-reintentable (payload inválido, recurso inexistente):
  el route lo traduce a 200 para que QStash no reintente en vano.
- Errores por email individual del lote de QRs: se registran en la base
  (`envio_intentos`/`envio_error`) y no cortan el lote ni fallan el request.
- Cualquier otra excepción (Supabase caída, SMTP caído en un transaccional)
  propaga → el route responde 5xx → QStash reintenta el mensaje.
"""
import io
import logging
import time

import qrcode

from ..config import (
    ASISTENCIA_EMAILS_PAUSA_MS,
    ASISTENCIA_EMAILS_MAX_REINTENTOS,
    ASISTENCIA_EMAILS_BACKOFF_MS,
)
from .. import db, mailer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------
# Lote de QRs de asistencia
# ---------------------------------------------------------------

def procesar_qr_lote(body: dict) -> dict:
    """
    Envía los QRs de las asistencias indicadas (lote chico, ~5 por mensaje,
    para entrar en el presupuesto de duración serverless).

    Idempotente: solo procesa las que siguen `enviado=false`, así un reintento
    de QStash no duplica envíos ya registrados.
    """
    clase_id = body.get('clase_id')
    ids      = body.get('asistencia_ids')

    if not isinstance(clase_id, int) or not isinstance(ids, list) or not ids \
            or not all(isinstance(asistencia_id, int) for asistencia_id in ids):
        raise ValueError('Payload inválido: se esperan clase_id (int) y asistencia_ids (lista de ints no vacía)')

    clase = db.obtener_clase_por_id(clase_id)

    if not clase:
        raise ValueError(f"Clase {clase_id} no encontrada")

    pendientes = db.buscar_asistencias_por_ids(ids)
    enviados   = _enviar_lote(clase, pendientes)

    return {
        'ok':         True,
        'clase_id':   clase_id,
        'recibidas':  len(ids),
        'pendientes': len(pendientes),
        'enviados':   enviados,
    }


def _enviar_lote(clase: dict, pendientes: list[dict]) -> int:
    """Envía cada asistencia del lote y registra el resultado. Retorna cuántas se enviaron ok."""
    enviados = 0

    with mailer.conexion_email() as conexion:
        for indice, asistencia in enumerate(pendientes):
            if indice > 0:
                time.sleep(ASISTENCIA_EMAILS_PAUSA_MS / 1000)

            estudiante = asistencia['estudiantes']
            intentos   = asistencia['envio_intentos'] + 1

            try:
                png      = _generar_qr_png(asistencia['codigo'])
                conexion = _enviar_email_qr_con_reintento(
                    estudiante['email'],
                    estudiante['nombre'],
                    clase,
                    asistencia['codigo'],
                    png,
                    estudiante.get('apellido') or '',
                    conexion,
                )
                
                try:
                    db.registrar_envio_asistencia(asistencia['id'], True, intentos, None)
                    enviados += 1
                except Exception as error_registro:
                    logger.error(f"[asistencia] No se pudo registrar el envío exitoso en DB para {estudiante.get('email')}: {error_registro}")
                    
                    return enviados
            except Exception as error:
                logger.error(f"[asistencia] Falló el envío del QR a {estudiante.get('email')}: {error}")
                
                _registrar_error_envio(asistencia['id'], intentos, error)

    return enviados


def _enviar_email_qr_con_reintento(destinatario: str, nombre: str, clase: dict,
                                   codigo: str, qr_png: bytes, apellido: str, conexion):
    """
    Envía el email QR reintentando ante errores transitorios de red del SMTP.

    Retorna la conexión SMTP a seguir usando en el lote: si la compartida se
    rompió (error transitorio), retorna None para que el reintento y el resto del
    lote abran conexiones nuevas.
    """
    intento = 0

    while True:
        try:
            mailer.enviar_email_qr_asistencia(destinatario, nombre, clase, codigo, qr_png, apellido, conexion)
            return conexion
        except Exception as error:
            intento += 1
            
            if intento > ASISTENCIA_EMAILS_MAX_REINTENTOS or not _es_error_transitorio_de_email(error):
                raise
            
            logger.warning(f"[asistencia] Reintentando envío a {destinatario} (intento {intento}/{ASISTENCIA_EMAILS_MAX_REINTENTOS}): {error}")
            conexion = None
            time.sleep(ASISTENCIA_EMAILS_BACKOFF_MS / 1000 * (2 ** (intento - 1)))


def _registrar_error_envio(asistencia_id: int, intentos: int, error: Exception) -> None:
    """Registra un intento fallido de envío, sin propagar errores de la base."""
    try:
        db.registrar_envio_asistencia(asistencia_id, False, intentos, str(error)[:300])
    except Exception as error_registro:
        logger.error(f"[asistencia] No se pudo registrar el error de envío en DB para asistencia {asistencia_id}: {error_registro}")


def _es_error_transitorio_de_email(error) -> bool:
    """Indica si un error de SMTP parece transitorio de red/transporte."""
    mensaje = str(error).lower()

    return (
        'broken pipe' in mensaje
        or 'connection unexpectedly closed' in mensaje
        or 'connection reset' in mensaje
        or 'timed out' in mensaje
        or 'server disconnected' in mensaje
        or 'temporary failure' in mensaje
    )


def _generar_qr_png(dato: str) -> bytes:
    """Genera el PNG de un QR que codifica `dato` (el código de asistencia)."""
    imagen  = qrcode.make(dato)
    buffer  = io.BytesIO()
    imagen.save(buffer, format='PNG')

    return buffer.getvalue()


# ---------------------------------------------------------------
# Confirmación de asistencia
# ---------------------------------------------------------------

def procesar_confirmacion(body: dict) -> dict:
    """Envía la confirmación de asistencia registrada (lee estudiante y clase de Supabase)."""
    asistencia_id = body.get('asistencia_id')

    if not isinstance(asistencia_id, int):
        raise ValueError('Payload inválido: se espera asistencia_id (int)')

    asistencia = db.obtener_asistencia_para_email(asistencia_id)

    if not asistencia:
        raise ValueError(f'Asistencia {asistencia_id} no encontrada')

    estudiante = asistencia['estudiantes']

    mailer.enviar_email_confirmacion_asistencia(
        estudiante['email'],
        estudiante['nombre'],
        estudiante.get('apellido') or '',
        asistencia['clases'],
    )

    return {'ok': True, 'asistencia_id': asistencia_id}


# ---------------------------------------------------------------
# Transaccionales sin Supabase (el secreto viaja en el payload)
# ---------------------------------------------------------------

def procesar_bienvenida(body: dict) -> dict:
    """Envía el email de bienvenida a un docente con su contraseña temporal."""
    faltantes = [campo for campo in ('destinatario', 'rol', 'password') if not body.get(campo)]

    if faltantes:
        raise ValueError(f"Payload inválido: faltan {', '.join(faltantes)}")

    mailer.enviar_email_nuevo_docente(
        body['destinatario'],
        body.get('nombre') or '',
        body.get('apellido') or '',
        body['rol'],
        body['password'],
    )

    return {'ok': True, 'destinatario': body['destinatario']}


def procesar_recuperacion(body: dict) -> dict:
    """Envía el email con el link de recuperación de contraseña."""
    faltantes = [campo for campo in ('destinatario', 'link') if not body.get(campo)]

    if faltantes:
        raise ValueError(f"Payload inválido: faltan {', '.join(faltantes)}")

    mailer.enviar_email_recuperacion(
        body['destinatario'],
        body['link'],
        nombre=body.get('nombre') or '',
        apellido=body.get('apellido') or '',
    )

    return {'ok': True, 'destinatario': body['destinatario']}
