"""
Verificación del header Upstash-Signature en los requests que manda QStash.

Usa `qstash.Receiver` (SDK oficial): valida la firma HMAC del JWT, los claims
`iss=Upstash`, `sub=<url destino>`, `exp`/`nbf` y el sha256 del body; prueba la
signing key vigente y la next (rotación de keys).

Env-gated para desarrollo: sin signing keys configuradas, la verificación se
saltea con un warning (permite pegarle al worker con curl/Bruno en local).
"""
import logging
from functools import wraps

from flask import request, jsonify
from qstash import Receiver
from qstash.errors import SignatureError

from .config import QSTASH_CURRENT_SIGNING_KEY, QSTASH_NEXT_SIGNING_KEY

logger = logging.getLogger(__name__)


def requiere_firma_qstash():
    """
    Exige un `Upstash-Signature` válido (401 si no verifica). Si no hay signing
    keys configuradas, deja pasar el request con warning (modo dev).
    """
    def decorador(vista):
        @wraps(vista)
        def wrapper(*args, **kwargs):
            if not _firma_configurada():
                logger.warning('[firma] Sin signing keys configuradas; request aceptado sin verificar (modo dev)')
                return vista(*args, **kwargs)

            try:
                _receiver().verify(
                    signature=request.headers.get('Upstash-Signature', ''),
                    body=request.get_data().decode('utf-8'),
                    url=request.url,
                )
            except SignatureError as error:
                logger.warning(f'[firma] Firma inválida: {error}')
                return jsonify({'ok': False, 'error': 'firma inválida'}), 401

            return vista(*args, **kwargs)
        return wrapper
    return decorador


def _firma_configurada() -> bool:
    """Indica si hay signing keys para verificar la firma."""
    return bool(QSTASH_CURRENT_SIGNING_KEY or QSTASH_NEXT_SIGNING_KEY)


def _receiver() -> Receiver:
    """Receiver con la signing key vigente y la next (rotación)."""
    return Receiver(
        current_signing_key=QSTASH_CURRENT_SIGNING_KEY,
        next_signing_key=QSTASH_NEXT_SIGNING_KEY,
    )
