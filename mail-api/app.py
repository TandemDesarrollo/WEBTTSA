"""API interna del formulario TTSA; Nginx publica únicamente /api/contact."""
import ipaddress
import os
import re
import smtplib
import ssl
import unicodedata
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024

FIELD_LIMITS = {
    "nombre": 120,
    "empresa": 160,
    "email": 254,
    "telefono": 60,
    "industria": 80,
    "mensaje": 5000,
}
INDUSTRIES = {"Banca", "Fintech", "Retail", "Telecomunicaciones", "Servicios", "Otra"}
SEND_ERROR = (
    "No pudimos confirmar el envío de tu consulta. Podés escribirnos a "
    "info@tandemtech.com.ar."
)


def valid_email(value):
    """Un único buzón, sin nombre visible ni encabezados adicionales."""
    if not isinstance(value, str) or len(value) > 254:
        return False
    local, separator, domain = value.rpartition("@")
    if not separator or not 1 <= len(local) <= 64 or "." not in domain:
        return False
    if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+", local):
        return False
    if local.startswith(".") or local.endswith(".") or ".." in local:
        return False
    return all(
        re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
        for label in domain.split(".")
    )


def valid_smtp_host(value):
    """Hostname o IP, sin protocolo, ruta ni puerto adjunto."""
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        pass
    try:
        hostname = value.encode("idna").decode("ascii")
    except UnicodeError:
        return False
    if hostname.endswith("."):
        hostname = hostname[:-1]
    return 1 <= len(hostname) <= 253 and all(
        re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
        for label in hostname.split(".")
    )


def mail_settings():
    """Configuración exclusiva del entorno del contenedor API."""
    host = os.environ.get("SMTP_HOST", "").strip()
    username = os.environ.get("SMTP_USERNAME", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "")
    sender = os.environ.get("MAIL_FROM", "").strip()
    recipient = os.environ.get("CONTACT_TO", "info@tandemtech.com.ar").strip()
    security = os.environ.get("SMTP_SECURITY", "starttls").strip().lower()
    port_setting = os.environ.get("SMTP_PORT", "").strip()
    port = int(port_setting or ("465" if security == "ssl" else "587"))
    timeout = float(os.environ.get("SMTP_TIMEOUT", "15"))
    if (
        not valid_smtp_host(host)
        or not valid_email(sender)
        or not valid_email(recipient)
        or security not in {"starttls", "ssl"}
        or not 1 <= port <= 65535
        or not 1 <= timeout <= 60
        or bool(username) != bool(password)
    ):
        raise ValueError("Configuración SMTP incompleta o inválida")
    return host, port, username, password, sender, recipient, security, timeout


def send_contact(fields, settings):
    host, port, username, password, sender, recipient, security, timeout = settings
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Reply-To"] = fields["email"]
    message["Subject"] = f"Consulta web TTSA — {fields['empresa']}"
    message["Date"] = formatdate(localtime=False)
    message["Message-ID"] = make_msgid(domain=sender.rpartition("@")[2])
    message.set_content(
        "Nueva consulta desde el sitio web TTSA\n\n"
        f"Nombre: {fields['nombre']}\n"
        f"Empresa: {fields['empresa']}\n"
        f"Email: {fields['email']}\n"
        f"Teléfono: {fields['telefono'] or 'No indicado'}\n"
        f"Industria: {fields['industria'] or 'No indicada'}\n\n"
        f"Mensaje:\n{fields['mensaje'] or 'Sin mensaje adicional'}\n"
    )
    context = ssl.create_default_context()
    smtp_class = smtplib.SMTP_SSL if security == "ssl" else smtplib.SMTP
    options = {"timeout": timeout}
    if security == "ssl":
        options["context"] = context
    smtp = smtp_class(host, port, **options)
    try:
        if security == "starttls":
            smtp.starttls(context=context)
        if username:
            smtp.login(username, password)
        refused = smtp.send_message(message, from_addr=sender, to_addrs=[recipient])
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)
    finally:
        # Cerrar no debe convertir un correo aceptado en un falso error.
        try:
            smtp.close()
        except OSError:
            pass


def contact_error(message, status):
    return jsonify(ok=False, message=message, error=message), status


@app.after_request
def prevent_response_caching(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@app.errorhandler(HTTPException)
def http_error(error):
    messages = {
        400: "Revisá los datos del formulario.",
        404: "El recurso solicitado no existe.",
        405: "La consulta debe enviarse mediante POST.",
        413: "La consulta supera el tamaño permitido.",
        415: "La consulta debe enviarse en formato JSON.",
        500: SEND_ERROR,
    }
    response = error.get_response()
    payload, _status = contact_error(messages.get(error.code, SEND_ERROR), error.code)
    response.set_data(payload.get_data())
    response.content_type = "application/json"
    return response


@app.get("/healthz")
def health():
    # Liveness/readiness HTTP; nunca abre conexiones SMTP ni valida credenciales.
    return jsonify(ok=True, message="Servicio disponible.")


@app.post("/api/contact", provide_automatic_options=False)
def contact():
    if not request.is_json:
        return contact_error("La consulta debe enviarse en formato JSON.", 415)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return contact_error("La consulta debe enviarse en formato JSON.", 400)
    if not isinstance(data.get("website", ""), str) or data.get("website", "").strip():
        return contact_error("No pudimos validar la consulta.", 400)

    fields = {}
    for name, limit in FIELD_LIMITS.items():
        value = data.get(name, "")
        if not isinstance(value, str) or len(value) > limit:
            return contact_error("Revisá los datos del formulario.", 400)
        if any(
            unicodedata.category(char) in {"Cc", "Cs"}
            and (name != "mensaje" or char not in "\t\r\n")
            for char in value
        ):
            return contact_error("Revisá los datos del formulario.", 400)
        fields[name] = value.strip()
    if (
        not fields["nombre"]
        or not fields["empresa"]
        or not valid_email(fields["email"])
        or (fields["industria"] and fields["industria"] not in INDUSTRIES)
    ):
        return contact_error("Revisá los campos obligatorios y el email.", 400)

    try:
        settings = mail_settings()
    except (ValueError, OverflowError):
        app.logger.error("El formulario de contacto requiere configurar las variables SMTP.")
        return contact_error(SEND_ERROR, 503)
    try:
        send_contact(fields, settings)
    except (OSError, ValueError) as error:
        # No registrar direcciones, cuerpos, credenciales ni respuestas del proveedor.
        app.logger.error("Falló el envío del formulario de contacto (%s).", type(error).__name__)
        return contact_error(SEND_ERROR, 502)
    return jsonify(
        ok=True,
        message="¡Gracias! Enviamos tu consulta y te vamos a contactar a la brevedad.",
    )


if __name__ == "__main__":
    from waitress import serve

    serve(app, host=os.environ.get("HOST", "0.0.0.0"), port=int(os.environ.get("PORT", "8000")))
