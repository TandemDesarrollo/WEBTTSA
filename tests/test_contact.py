"""Pruebas del formulario: nunca abren una conexión SMTP real."""
import os
import smtplib
import ssl
import unittest
from html.parser import HTMLParser
from unittest.mock import MagicMock, patch

from _support import API_PATH, PROJECT_ROOT, load_mail_api

server = load_mail_api()


class FormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.form = None
        self.fields = {}
        self.in_contact = False

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "form":
            self.in_contact = attrs.get("id") == "contactForm"
            if self.in_contact:
                self.form = attrs
        if self.in_contact and attrs.get("name"):
            self.fields[attrs["name"]] = attrs

    def handle_endtag(self, tag):
        if tag == "form":
            self.in_contact = False


class ContactTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {
            "SMTP_HOST": "smtp.example.com",
            "MAIL_FROM": "web@tandemtech.com.ar",
        }, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.smtp_patch = patch.object(server.smtplib, "SMTP")
        self.ssl_patch = patch.object(server.smtplib, "SMTP_SSL")
        self.smtp_constructor = self.smtp_patch.start()
        self.ssl_constructor = self.ssl_patch.start()
        self.addCleanup(self.smtp_patch.stop)
        self.addCleanup(self.ssl_patch.stop)
        network_patch = patch("socket.create_connection", side_effect=AssertionError("Las pruebas no permiten conexiones reales"))
        network_patch.start()
        self.addCleanup(network_patch.stop)
        self.smtp = MagicMock()
        self.smtp.__enter__.return_value = self.smtp
        self.smtp.send_message.return_value = {}
        self.smtp_constructor.return_value = self.smtp
        self.ssl_constructor.return_value = self.smtp
        self.client = server.app.test_client()
        self.payload = {
            "nombre": "María Pérez",
            "empresa": "Compañía Ñandú",
            "email": "maria@example.com",
            "telefono": "+54 11 5555 1234",
            "industria": "Fintech",
            "mensaje": "Quiero información sobre sus servicios.\nGracias.",
        }

    def post(self, payload=None):
        return self.client.post("/api/contact", json=self.payload if payload is None else payload)

    def assert_error(self, response, status):
        self.assertEqual(response.status_code, status)
        self.assertTrue(response.is_json)
        result = response.get_json()
        self.assertIs(result.get("ok"), False)
        self.assert_message(result)
        if "error" in result:
            self.assertIsInstance(result["error"], str)
            self.assertTrue(result["error"].strip())

    def assert_message(self, result):
        self.assertIsInstance(result.get("message"), str)
        self.assertTrue(result["message"].strip())

    def assert_no_smtp(self):
        self.smtp_constructor.assert_not_called()
        self.ssl_constructor.assert_not_called()

    def test_success_sends_unicode_message_with_safe_headers(self):
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertIs(response.get_json()["ok"], True)
        self.assert_message(response.get_json())
        self.smtp_constructor.assert_called_once()
        self.assertEqual(self.smtp_constructor.call_args.args, ("smtp.example.com", 587))
        self.assertGreater(self.smtp_constructor.call_args.kwargs["timeout"], 0)
        self.ssl_constructor.assert_not_called()
        self.smtp.starttls.assert_called_once()
        context = self.smtp.starttls.call_args.kwargs["context"]
        self.assertIsInstance(context, ssl.SSLContext)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        self.smtp.login.assert_not_called()
        self.smtp.send_message.assert_called_once()
        message = self.smtp.send_message.call_args.args[0]
        self.assertEqual(str(message["From"]), "web@tandemtech.com.ar")
        self.assertEqual(str(message["To"]), "info@tandemtech.com.ar")
        self.assertEqual(str(message["Reply-To"]), self.payload["email"])
        self.assertIn(self.payload["empresa"], str(message["Subject"]))
        self.assertIsNotNone(message["Date"])
        self.assertIsNotNone(message["Message-ID"])
        self.assertEqual(self.smtp.send_message.call_args.kwargs, {
            "from_addr": "web@tandemtech.com.ar", "to_addrs": ["info@tandemtech.com.ar"],
        })
        body = message.get_body(preferencelist=("plain",)).get_content()
        for value in self.payload.values():
            self.assertIn(value, body)
        names = [call[0] for call in self.smtp.method_calls]
        self.assertLess(names.index("starttls"), names.index("send_message"))

    def test_required_values_are_trimmed_and_optional_fields_can_be_omitted(self):
        response = self.post({
            "nombre": "  Ana  ", "empresa": "  Empresa  ", "email": "  ana@example.com  ",
        })
        self.assertEqual(response.status_code, 200)
        message = self.smtp.send_message.call_args.args[0]
        self.assertEqual(str(message["Reply-To"]), "ana@example.com")
        self.assertIn("Nombre: Ana\n", message.get_content())
        self.assertIn("Empresa: Empresa\n", message.get_content())
        self.assertIn("Email: ana@example.com\n", message.get_content())

    def test_starttls_authenticates_before_sending(self):
        os.environ.update(SMTP_USERNAME="smtp-user", SMTP_PASSWORD="smtp-password")
        self.assertEqual(self.post().status_code, 200)
        self.smtp.login.assert_called_once_with("smtp-user", "smtp-password")
        names = [call[0] for call in self.smtp.method_calls]
        self.assertLess(names.index("starttls"), names.index("login"))
        self.assertLess(names.index("login"), names.index("send_message"))

    def test_ssl_uses_configured_port_sender_and_recipient(self):
        os.environ.update(
            SMTP_SECURITY="ssl", SMTP_PORT="465",
            MAIL_FROM="consultas@example.com", CONTACT_TO="ventas@example.com",
        )
        self.assertEqual(self.post().status_code, 200)
        self.smtp_constructor.assert_not_called()
        self.ssl_constructor.assert_called_once()
        args, kwargs = self.ssl_constructor.call_args
        self.assertEqual(args, ("smtp.example.com", 465))
        self.assertGreater(kwargs["timeout"], 0)
        self.assertIsInstance(kwargs["context"], ssl.SSLContext)
        self.assertEqual(kwargs["context"].verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(kwargs["context"].check_hostname)
        self.smtp.starttls.assert_not_called()
        message = self.smtp.send_message.call_args.args[0]
        self.assertEqual(str(message["From"]), "consultas@example.com")
        self.assertEqual(str(message["To"]), "ventas@example.com")
        self.assertEqual(self.smtp.send_message.call_args.kwargs, {
            "from_addr": "consultas@example.com", "to_addrs": ["ventas@example.com"],
        })

    def test_configuration_is_read_per_request_and_ssl_has_secure_default_port(self):
        self.assertEqual(self.post().status_code, 200)
        os.environ.update(
            SMTP_HOST="other.example.com", SMTP_SECURITY="ssl", CONTACT_TO="other@example.com",
        )
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(self.ssl_constructor.call_args.args, ("other.example.com", 465))
        self.assertEqual(self.smtp.send_message.call_args.kwargs["to_addrs"], ["other@example.com"])

    def test_blank_port_uses_the_documented_transport_default(self):
        # Compose intentionally forwards an empty SMTP_PORT when not configured.
        # The production contract chooses the default from the TLS transport.
        for security, port in (("starttls", 587), ("ssl", 465)):
            with self.subTest(security=security), patch.dict(os.environ, {
                "SMTP_SECURITY": security, "SMTP_PORT": "",
            }):
                response = self.post()
                self.assertEqual(response.status_code, 200)
                self.assertIs(response.get_json()["ok"], True)
                self.assert_message(response.get_json())
                constructor = self.ssl_constructor if security == "ssl" else self.smtp_constructor
                self.assertEqual(constructor.call_args.args, ("smtp.example.com", port))
        self.assertEqual(self.smtp.send_message.call_count, 2)

    def test_payload_cannot_override_sender_or_recipient(self):
        response = self.post({
            **self.payload, "from": "visitor@example.com", "to": "attacker@example.com",
            "MAIL_FROM": "visitor@example.com", "CONTACT_TO": "attacker@example.com",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.smtp.send_message.call_args.kwargs, {
            "from_addr": "web@tandemtech.com.ar", "to_addrs": ["info@tandemtech.com.ar"],
        })

    def test_sender_is_required_even_with_username(self):
        os.environ.pop("MAIL_FROM")
        os.environ.update(SMTP_USERNAME="sender@example.com", SMTP_PASSWORD="password")
        self.assert_error(self.post(), 503)
        self.assert_no_smtp()

    def test_required_fields_are_nonempty_strings(self):
        for field in ("nombre", "empresa", "email"):
            for invalid in (None, "", " \t ", 42, [], {}):
                with self.subTest(field=field, value=invalid):
                    payload = {**self.payload, field: invalid}
                    self.assert_error(self.post(payload), 400)
            with self.subTest(field=field, value="missing"):
                payload = dict(self.payload)
                del payload[field]
                self.assert_error(self.post(payload), 400)
        self.assert_no_smtp()

    def test_optional_fields_must_be_strings(self):
        for field in ("telefono", "industria", "mensaje"):
            for invalid in (None, 42, [], {}):
                with self.subTest(field=field, value=invalid):
                    self.assert_error(self.post({**self.payload, field: invalid}), 400)
        self.assert_no_smtp()

    def test_field_length_limits(self):
        for field, limit in (
            ("nombre", 120), ("empresa", 160), ("email", 254),
            ("telefono", 60), ("industria", 80), ("mensaje", 5000),
        ):
            with self.subTest(field=field):
                self.assert_error(self.post({**self.payload, field: "x" * (limit + 1)}), 400)
        self.assert_no_smtp()

    def test_maximum_name_company_phone_and_message_lengths_are_accepted(self):
        self.assertEqual(self.post({
            **self.payload, "nombre": "n" * 120, "empresa": "e" * 160,
            "telefono": "1" * 60, "mensaje": "m" * 5000,
        }).status_code, 200)

    def test_only_supported_industries_are_accepted(self):
        for industry in ("Banca", "Fintech", "Retail", "Telecomunicaciones", "Servicios", "Otra", ""):
            with self.subTest(industry=industry):
                self.assertEqual(self.post({**self.payload, "industria": industry}).status_code, 200)
        self.assert_error(self.post({**self.payload, "industria": "Desconocida"}), 400)

    def test_email_must_be_one_bare_address(self):
        for invalid in (
            "no-es-email", "a@@example.com", "a b@example.com", "a@example..com",
            "Nombre <a@example.com>", "a@example.com,b@example.com", "a@example.com; b@example.com",
            ".a@example.com", "a.@example.com", "a..b@example.com", "a@-example.com",
            "a@example-.com", "a" * 65 + "@example.com",
        ):
            with self.subTest(email=invalid):
                self.assert_error(self.post({**self.payload, "email": invalid}), 400)
        self.assert_no_smtp()

    def test_header_fields_reject_newlines(self):
        for field in ("nombre", "empresa", "email", "telefono", "industria"):
            for newline in ("\r", "\n", "\r\n"):
                with self.subTest(field=field, newline=repr(newline)):
                    self.assert_error(self.post({**self.payload, field: "valor" + newline + "Bcc: x@example.com"}), 400)
        self.assert_no_smtp()

    def test_non_object_json_and_malformed_json_are_rejected(self):
        for value in ([], "texto", 42, True):
            with self.subTest(value=value):
                self.assert_error(self.post(value), 400)
        self.assert_error(self.client.post("/api/contact", data="null", content_type="application/json"), 400)
        self.assert_error(self.client.post("/api/contact", data="{", content_type="application/json"), 400)
        self.assert_no_smtp()

    def test_non_json_request_is_rejected(self):
        self.assert_error(self.client.post("/api/contact", data=self.payload), 415)
        self.assert_no_smtp()

    def test_oversized_request_is_rejected_as_json(self):
        self.assert_error(self.post({**self.payload, "padding": "x" * 33000}), 413)
        self.assert_no_smtp()

    def test_honeypot_rejects_nonempty_or_nonstring_values(self):
        for value in ("https://spam.example.com", True, 42, [], {}, None):
            with self.subTest(value=value):
                self.assert_error(self.post({**self.payload, "website": value}), 400)
        self.assert_no_smtp()

    def test_honeypot_can_be_empty(self):
        self.assertEqual(self.post({**self.payload, "website": ""}).status_code, 200)

    def test_nul_and_control_characters_are_rejected(self):
        for field in self.payload:
            for control in ("\x00", "\x7f", "\x85", "\ud800"):
                with self.subTest(field=field, control=repr(control)):
                    self.assert_error(self.post({**self.payload, field: "text" + control + "text"}), 400)
        self.assert_error(self.post({**self.payload, "mensaje": "text\x01text"}), 400)
        self.assert_no_smtp()

    def test_post_is_required_for_email_submission(self):
        response = self.client.get("/api/contact")
        self.assertGreaterEqual(response.status_code, 400)
        self.assert_no_smtp()

    def test_legacy_alias_if_present_obeys_the_same_contract(self):
        if "/api/contacto" not in {rule.rule for rule in server.app.url_map.iter_rules()}:
            self.skipTest("El backend no conserva el alias opcional /api/contacto")
        response = self.client.post("/api/contacto", json=self.payload)
        self.assertEqual(response.status_code, 200)
        self.assertIs(response.get_json()["ok"], True)
        self.assert_message(response.get_json())
        self.assert_error(self.client.post("/api/contacto", json={}), 400)

    def test_missing_configuration_is_unavailable(self):
        for missing in ("SMTP_HOST", "MAIL_FROM"):
            with self.subTest(missing=missing), patch.dict(os.environ, dict(os.environ), clear=True):
                del os.environ[missing]
                self.assert_error(self.post(), 503)
        self.assert_no_smtp()

    def test_partial_credentials_are_unavailable(self):
        for credentials in ({"SMTP_USERNAME": "user"}, {"SMTP_PASSWORD": "password"}):
            with self.subTest(credentials=tuple(credentials)), patch.dict(os.environ, credentials):
                self.assert_error(self.post(), 503)
        self.assert_no_smtp()

    def test_plaintext_transport_is_rejected(self):
        os.environ["SMTP_SECURITY"] = "none"
        self.assert_error(self.post(), 503)
        self.assert_no_smtp()

    def test_invalid_ports_sender_and_recipient_fail_before_smtp(self):
        settings = [
            {"SMTP_PORT": value} for value in ("invalid", "0", "-1", "65536")
        ] + [
            {name: value}
            for name in ("MAIL_FROM", "CONTACT_TO")
            for value in ("", "invalid", "a@example.com,b@example.com", "a@example.com\r\nBcc: x@example.com")
        ]
        for setting in settings:
            with self.subTest(setting=setting), patch.dict(os.environ, setting):
                self.assert_error(self.post(), 503)
        self.assert_no_smtp()

    def test_smtp_connection_errors_return_sanitized_json(self):
        for error in (OSError("smtp-secret-password"), smtplib.SMTPException("smtp-secret-password")):
            with self.subTest(error=type(error).__name__):
                self.smtp_constructor.side_effect = error
                response = self.post()
                self.assert_error(response, 502)
                self.assertNotIn("smtp-secret-password", response.get_data(as_text=True))
        self.smtp.send_message.assert_not_called()

    def test_authentication_error_returns_sanitized_json(self):
        os.environ.update(SMTP_USERNAME="user", SMTP_PASSWORD="smtp-secret-password")
        self.smtp.login.side_effect = smtplib.SMTPAuthenticationError(535, b"smtp-secret-password")
        response = self.post()
        self.assert_error(response, 502)
        self.assertNotIn("smtp-secret-password", response.get_data(as_text=True))
        self.smtp.send_message.assert_not_called()

    def test_starttls_failure_never_authenticates_or_sends(self):
        os.environ.update(SMTP_USERNAME="user", SMTP_PASSWORD="smtp-test-password")
        self.smtp.starttls.side_effect = smtplib.SMTPNotSupportedError("STARTTLS unavailable")
        self.assert_error(self.post(), 502)
        self.smtp.login.assert_not_called()
        self.smtp.send_message.assert_not_called()

    def test_connection_timeout_is_reported_without_success(self):
        self.smtp_constructor.side_effect = TimeoutError("simulated timeout")
        self.assert_error(self.post(), 502)
        self.smtp.send_message.assert_not_called()

    def test_ssl_certificate_failure_never_sends(self):
        os.environ["SMTP_SECURITY"] = "ssl"
        self.ssl_constructor.side_effect = ssl.SSLCertVerificationError("simulated certificate failure")
        self.assert_error(self.post(), 502)
        self.smtp.send_message.assert_not_called()

    def test_errors_do_not_log_credentials_or_form_contents(self):
        marker = "synthetic-sensitive-value"
        os.environ.update(SMTP_USERNAME="user", SMTP_PASSWORD=marker)
        self.smtp.login.side_effect = smtplib.SMTPAuthenticationError(535, marker.encode())
        with self.assertLogs(server.app.logger, level="ERROR") as logs:
            response = self.post({**self.payload, "mensaje": marker})
        self.assert_error(response, 502)
        self.assertNotIn(marker, response.get_data(as_text=True))
        self.assertNotIn(marker, "\n".join(logs.output))

    def test_smtp_rejection_and_data_error_do_not_report_success(self):
        self.smtp.send_message.return_value = {"info@tandemtech.com.ar": (550, b"rejected")}
        self.assert_error(self.post(), 502)
        self.smtp.send_message.side_effect = smtplib.SMTPDataError(550, b"smtp-secret-password")
        response = self.post()
        self.assert_error(response, 502)
        self.assertNotIn("smtp-secret-password", response.get_data(as_text=True))

    def test_cleanup_failure_does_not_undo_accepted_message(self):
        self.smtp.quit.side_effect = OSError("quit failed after accepted")
        self.smtp.close.side_effect = OSError("connection already closed")
        self.smtp.__exit__.side_effect = OSError("context cleanup failed after accepted")
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertIs(response.get_json()["ok"], True)
        self.assert_message(response.get_json())
        cleanup_calls = self.smtp.quit.call_count + self.smtp.close.call_count + self.smtp.__exit__.call_count
        self.assertGreater(cleanup_calls, 0, "La prueba debe ejercitar el cierre de la conexión")

    def test_form_targets_the_canonical_backend_contact_route(self):
        parser = FormParser()
        parser.feed((PROJECT_ROOT / "index.html").read_text())
        self.assertIsNotNone(parser.form)
        self.assertEqual(parser.form.get("action"), "/api/contact")
        self.assertEqual(parser.form.get("method", "get").lower(), "post")
        registered = server.app.url_map.bind("localhost").match("/api/contact", method="POST")
        self.assertIn(registered[0], server.app.view_functions)
        self.assertEqual(parser.fields["email"]["type"], "email")
        for field in ("nombre", "empresa", "email"):
            with self.subTest(field=field):
                self.assertIn("required", parser.fields[field])

    def test_html_maxlengths_match_backend_validation(self):
        parser = FormParser()
        parser.feed((PROJECT_ROOT / "index.html").read_text())
        for field in ("nombre", "empresa", "email", "telefono", "mensaje"):
            with self.subTest(field=field):
                self.assertEqual(int(parser.fields[field]["maxlength"]), server.FIELD_LIMITS[field])

    def test_backend_is_loaded_from_the_production_source(self):
        self.assertEqual(API_PATH, API_PATH.resolve())
        self.assertEqual(str(API_PATH), server.__file__)

    def test_api_does_not_expose_source_or_configuration(self):
        for path in (
            "/app.py", "/.env", "/requirements.txt", "/.git/config",
            "/mail-api/app.py", "/docker-compose.yml", "/tests/test_contact.py",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)
        self.assert_no_smtp()


if __name__ == "__main__":
    unittest.main()
