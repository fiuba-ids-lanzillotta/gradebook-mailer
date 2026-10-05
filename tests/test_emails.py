"""
Tests de los servicios de emails y los endpoints, con db y mailer mockeados
(sin red ni SMTP). La verificación de firma queda en modo dev (sin signing keys).
"""
import base64
import hashlib
import json
import smtplib
import time

import jwt
import pytest

from app import app
from gradebook_mailer import db, firma, mailer
from gradebook_mailer.services import emails


def _jwt_qstash(cuerpo: bytes, url: str, clave: str) -> str:
    """Firma un JWT como el que QStash manda en el header Upstash-Signature."""
    ahora  = int(time.time())
    digest = base64.urlsafe_b64encode(hashlib.sha256(cuerpo).digest()).decode().rstrip('=')

    return jwt.encode(
        {'iss': 'Upstash', 'sub': url, 'exp': ahora + 60, 'nbf': ahora - 60,
         'iat': ahora - 60, 'body': digest},
        clave, algorithm='HS256')


# ---------------------------------------------------------------
# Lote de QRs
# ---------------------------------------------------------------

def test_procesar_qr_lote_envia_y_registra(monkeypatch):
    monkeypatch.setattr(db, 'obtener_clase_por_id', lambda cid: {'id': 5, 'cursada_id': 9, 'fecha': '2026-09-01', 'titulo': 'C1', 'estado': 'abierta'})
    monkeypatch.setattr(db, 'buscar_asistencias_por_ids', lambda ids: [
        {'id': 1, 'codigo': 'AAAA2345', 'envio_intentos': 0, 'estudiantes': {'nombre': 'Ana', 'email': 'a@fi.uba.ar'}},
        {'id': 2, 'codigo': 'BBBB2345', 'envio_intentos': 0, 'estudiantes': {'nombre': 'Beto', 'email': 'b@fi.uba.ar'}},
    ])
    enviados = []
    monkeypatch.setattr(mailer, 'enviar_email_qr_asistencia', lambda *a, **k: enviados.append(a[0]))
    registros = []
    monkeypatch.setattr(db, 'registrar_envio_asistencia', lambda aid, ok, intentos, err: registros.append((aid, ok)))

    resultado = emails.procesar_qr_lote({'clase_id': 5, 'asistencia_ids': [1, 2, 3]})

    assert resultado['enviados'] == 2 and resultado['recibidas'] == 3 and resultado['pendientes'] == 2
    assert registros == [(1, True), (2, True)]


def test_procesar_qr_lote_registra_error_sin_cortar(monkeypatch):
    monkeypatch.setattr(db, 'obtener_clase_por_id', lambda cid: {'id': 5, 'cursada_id': 9, 'fecha': '2026-09-01', 'titulo': None, 'estado': 'abierta'})
    monkeypatch.setattr(db, 'buscar_asistencias_por_ids', lambda ids: [
        {'id': 1, 'codigo': 'AAAA2345', 'envio_intentos': 0, 'estudiantes': {'nombre': 'Ana', 'email': 'mala'}},
    ])

    def explota(*a, **k):
        raise RuntimeError('smtp caido')

    monkeypatch.setattr(mailer, 'enviar_email_qr_asistencia', explota)
    registros = []
    monkeypatch.setattr(db, 'registrar_envio_asistencia', lambda aid, ok, intentos, err: registros.append((ok, intentos, err)))

    resultado = emails.procesar_qr_lote({'clase_id': 5, 'asistencia_ids': [1]})

    assert resultado['enviados'] == 0
    assert registros[0][0] is False and registros[0][1] == 1 and 'smtp' in registros[0][2]


def test_procesar_qr_lote_reintenta_error_smtp_transitorio(monkeypatch):
    monkeypatch.setattr(db, 'obtener_clase_por_id', lambda cid: {'id': 5, 'cursada_id': 9, 'fecha': '2026-09-01', 'titulo': None, 'estado': 'abierta'})
    monkeypatch.setattr(db, 'buscar_asistencias_por_ids', lambda ids: [
        {'id': 1, 'codigo': 'AAAA2345', 'envio_intentos': 0, 'estudiantes': {'nombre': 'Ana', 'email': 'a@fi.uba.ar'}},
    ])
    monkeypatch.setattr(time, 'sleep', lambda *_: None)

    llamadas = {'n': 0}

    def falla_una_vez(*a, **k):
        llamadas['n'] += 1
        if llamadas['n'] == 1:
            raise smtplib.SMTPDataError(421, b'4.3.0 Temporary System Problem. Try again later.')

    monkeypatch.setattr(mailer, 'enviar_email_qr_asistencia', falla_una_vez)
    monkeypatch.setattr(db, 'registrar_envio_asistencia', lambda aid, ok, intentos, err: None)

    resultado = emails.procesar_qr_lote({'clase_id': 5, 'asistencia_ids': [1]})

    assert resultado['enviados'] == 1 and llamadas['n'] == 2


def test_procesar_qr_lote_no_reintenta_error_smtp_permanente(monkeypatch):
    monkeypatch.setattr(db, 'obtener_clase_por_id', lambda cid: {'id': 5, 'cursada_id': 9, 'fecha': '2026-09-01', 'titulo': None, 'estado': 'abierta'})
    monkeypatch.setattr(db, 'buscar_asistencias_por_ids', lambda ids: [
        {'id': 1, 'codigo': 'AAAA2345', 'envio_intentos': 0, 'estudiantes': {'nombre': 'Ana', 'email': 'a@fi.uba.ar'}},
    ])
    monkeypatch.setattr(time, 'sleep', lambda *_: None)

    llamadas = {'n': 0}

    def siempre_falla(*a, **k):
        llamadas['n'] += 1
        raise smtplib.SMTPDataError(550, b'5.7.1 Mailbox unavailable')

    monkeypatch.setattr(mailer, 'enviar_email_qr_asistencia', siempre_falla)
    monkeypatch.setattr(db, 'registrar_envio_asistencia', lambda aid, ok, intentos, err: None)

    resultado = emails.procesar_qr_lote({'clase_id': 5, 'asistencia_ids': [1]})

    assert resultado['enviados'] == 0 and llamadas['n'] == 1


def test_procesar_qr_lote_payload_invalido():
    with pytest.raises(ValueError):
        emails.procesar_qr_lote({'clase_id': 5})

    with pytest.raises(ValueError):
        emails.procesar_qr_lote({'clase_id': 'x', 'asistencia_ids': [1]})


def test_procesar_qr_lote_clase_inexistente(monkeypatch):
    monkeypatch.setattr(db, 'obtener_clase_por_id', lambda cid: {})

    with pytest.raises(ValueError):
        emails.procesar_qr_lote({'clase_id': 99, 'asistencia_ids': [1]})


# ---------------------------------------------------------------
# Confirmación de asistencia
# ---------------------------------------------------------------

def test_procesar_confirmacion_envia_con_datos_de_db(monkeypatch):
    monkeypatch.setattr(db, 'obtener_asistencia_para_email', lambda aid: {
        'id': 7,
        'clase_id': 5,
        'estudiantes': {'nombre': 'Ana', 'apellido': 'Paz', 'email': 'a@fi.uba.ar'},
        'clases': {'fecha': '2026-09-01', 'titulo': 'C1'},
    })
    enviados = []
    monkeypatch.setattr(mailer, 'enviar_email_confirmacion_asistencia', lambda *a, **k: enviados.append(a))

    resultado = emails.procesar_confirmacion({'asistencia_id': 7})

    assert resultado == {'ok': True, 'asistencia_id': 7}
    assert enviados[0][0] == 'a@fi.uba.ar'


def test_procesar_confirmacion_inexistente(monkeypatch):
    monkeypatch.setattr(db, 'obtener_asistencia_para_email', lambda aid: {})

    with pytest.raises(ValueError):
        emails.procesar_confirmacion({'asistencia_id': 99})


# ---------------------------------------------------------------
# Transaccionales (payload completo, sin Supabase)
# ---------------------------------------------------------------

def test_procesar_bienvenida_ok(monkeypatch):
    enviados = []
    monkeypatch.setattr(mailer, 'enviar_email_nuevo_docente', lambda *a: enviados.append(a))

    resultado = emails.procesar_bienvenida({
        'destinatario': 'doc@fi.uba.ar', 'nombre': 'Ana', 'apellido': 'Paz',
        'rol': 'Ayudante', 'password': 'secreto',
    })

    assert resultado['ok'] is True and enviados[0][0] == 'doc@fi.uba.ar'


def test_procesar_bienvenida_falta_campo():
    with pytest.raises(ValueError):
        emails.procesar_bienvenida({'destinatario': 'doc@fi.uba.ar'})


def test_procesar_recuperacion_ok(monkeypatch):
    enviados = []
    monkeypatch.setattr(mailer, 'enviar_email_recuperacion', lambda *a, **k: enviados.append(a))

    resultado = emails.procesar_recuperacion({
        'destinatario': 'est@fi.uba.ar', 'link': 'http://x/reset?token=t',
    })

    assert resultado['ok'] is True and enviados[0][0] == 'est@fi.uba.ar'


def test_procesar_recuperacion_falta_link():
    with pytest.raises(ValueError):
        emails.procesar_recuperacion({'destinatario': 'est@fi.uba.ar'})


# ---------------------------------------------------------------
# Endpoints (firma en modo dev: sin keys → se saltea)
# ---------------------------------------------------------------

def test_endpoint_bienvenida_ok(monkeypatch):
    monkeypatch.setattr(mailer, 'enviar_email_nuevo_docente', lambda *a: None)

    respuesta = app.test_client().post('/emails/bienvenida', json={
        'destinatario': 'doc@fi.uba.ar', 'rol': 'Ayudante', 'password': 'secreto',
    })

    assert respuesta.status_code == 200
    assert respuesta.get_json()['ok'] is True


def test_endpoint_payload_invalido_responde_200(monkeypatch):
    respuesta = app.test_client().post('/emails/recuperacion', json={'foo': 'bar'})

    assert respuesta.status_code == 200
    assert respuesta.get_json()['ok'] is False


def test_endpoint_rechaza_sin_firma_cuando_hay_keys(monkeypatch):
    monkeypatch.setattr(firma, 'QSTASH_CURRENT_SIGNING_KEY', 'clave-test')

    respuesta = app.test_client().post('/emails/bienvenida', json={
        'destinatario': 'doc@fi.uba.ar', 'rol': 'Ayudante', 'password': 'secreto',
    })

    assert respuesta.status_code == 401


def test_endpoint_acepta_firma_valida(monkeypatch):
    monkeypatch.setattr(firma, 'QSTASH_CURRENT_SIGNING_KEY', 'clave-test')
    monkeypatch.setattr(mailer, 'enviar_email_nuevo_docente', lambda *a: None)

    cuerpo    = json.dumps({'destinatario': 'doc@fi.uba.ar', 'rol': 'Ayudante', 'password': 'secreto'})
    firma_jwt = _jwt_qstash(cuerpo.encode(), 'http://localhost/emails/bienvenida', 'clave-test')

    respuesta = app.test_client().post(
        '/emails/bienvenida', data=cuerpo, content_type='application/json',
        headers={'Upstash-Signature': firma_jwt},
    )

    assert respuesta.status_code == 200
    assert respuesta.get_json()['ok'] is True
