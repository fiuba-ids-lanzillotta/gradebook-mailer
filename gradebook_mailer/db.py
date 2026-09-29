"""
Acceso a Supabase (PostgREST) para lo que necesita el worker: leer asistencias
pendientes de envío (con estudiante y clase) y registrar el resultado de cada
envío. Es el subconjunto de `gradebook_api/db.py` que usa el envío de emails.
"""
import logging
import time
from datetime import datetime, timezone

from supabase import create_client, Client

from .config import (
    SUPABASE_URL,
    SUPABASE_KEY,
    ASISTENCIA_DB_MAX_REINTENTOS,
    ASISTENCIA_DB_BACKOFF_MS,
)

logger = logging.getLogger(__name__)


def _crear_cliente_supabase() -> Client:
    """Crea un cliente de Supabase (PostgREST)."""
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# Cliente de Supabase compartido por toda la aplicación (habla PostgREST).
cliente: Client = _crear_cliente_supabase()


def _ahora_iso() -> str:
    """Timestamp actual en ISO-8601 (UTC)."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------
# Lecturas
# ---------------------------------------------------------------

CAMPOS_CLASE = 'id, cursada_id, fecha, titulo, estado, created_at, updated_at'


def buscar_asistencias_por_ids(asistencia_ids: list[int]) -> list[dict]:
    """
    Retorna las asistencias dadas que siguen pendientes de envío (enviado=false),
    con datos del estudiante. Filtrar por enviado vuelve idempotente el reintento
    de un mensaje de QStash (at-least-once).
    """
    def consulta(cliente_actual):
        return (cliente_actual.table('asistencias')
                .select('id, clase_id, codigo, envio_intentos, estudiantes!inner(nombre, apellido, email)')
                .in_('id', asistencia_ids)
                .eq('enviado', False)
                .order('id'))

    return _ejecutar_con_reintento(consulta).data


def obtener_clase_por_id(clase_id: int) -> dict:
    """Retorna la clase con el id dado, o un dict vacío si no existe."""
    def consulta(cliente_actual):
        return cliente_actual.table('clases').select(CAMPOS_CLASE).eq('id', clase_id)

    filas = _ejecutar_con_reintento(consulta).data

    return filas[0] if filas else {}


def obtener_asistencia_para_email(asistencia_id: int) -> dict:
    """Retorna la asistencia con su estudiante y su clase (para la confirmación), o {}."""
    def consulta(cliente_actual):
        return (cliente_actual.table('asistencias')
                .select('id, clase_id, estudiantes!inner(nombre, apellido, email), clases!inner(fecha, titulo)')
                .eq('id', asistencia_id))

    filas = _ejecutar_con_reintento(consulta).data

    return filas[0] if filas else {}


# ---------------------------------------------------------------
# Escrituras
# ---------------------------------------------------------------

def registrar_envio_asistencia(asistencia_id: int, enviado: bool, intentos: int, error: str) -> int:
    """Registra el resultado de un intento de envío del QR. Retorna filas afectadas."""
    payload = {
        'enviado':        enviado,
        'envio_intentos': intentos,
        'envio_error':    error,
        'updated_at':     _ahora_iso(),
    }

    if enviado:
        payload['enviado_at'] = _ahora_iso()

    def consulta(cliente_actual):
        return cliente_actual.table('asistencias').update(payload).eq('id', asistencia_id)

    filas = _ejecutar_con_reintento(consulta).data

    return len(filas)


# ---------------------------------------------------------------
# Reintentos de red hacia Supabase
# ---------------------------------------------------------------

def _es_error_de_red(error) -> bool:
    """Indica si el error parece transitorio de red/transporte hacia Supabase."""
    mensaje = str(error).lower()

    return (
        'broken pipe' in mensaje
        or 'connection unexpectedly closed' in mensaje
        or 'connection reset' in mensaje
        or 'remote protocol error' in mensaje
        or 'network is unreachable' in mensaje
        or 'read error' in mensaje
    )


def _recrear_cliente_supabase() -> None:
    """Recrea el cliente global de Supabase ante errores de conexión."""
    global cliente
    cliente = _crear_cliente_supabase()


def _ejecutar_con_reintento(constructor):
    """Ejecuta una consulta de Supabase reintentando en errores de red."""
    intento = 0

    while True:
        try:
            return constructor(cliente).execute()
        except Exception as error:
            intento += 1
            
            if intento >= ASISTENCIA_DB_MAX_REINTENTOS or not _es_error_de_red(error):
                raise
            
            logger.warning(f'[db] Error de red en Supabase (intento {intento}/{ASISTENCIA_DB_MAX_REINTENTOS}): {error}')
            time.sleep(ASISTENCIA_DB_BACKOFF_MS / 1000 * (2 ** (intento - 1)))
            _recrear_cliente_supabase()
