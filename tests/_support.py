"""Rutas explícitas: nunca importar el backend del checkout anterior."""
import importlib.util
from pathlib import Path
import sys
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_PATH = PROJECT_ROOT / "mail-api" / "app.py"


def load_mail_api():
    if not API_PATH.is_file():
        raise FileNotFoundError(f"Falta el backend de producción esperado: {API_PATH}")
    name = "_webttsa_production_mail_api"
    spec = importlib.util.spec_from_file_location(name, API_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    bytecode_setting = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        # Proteger también la importación, antes de instalar los mocks por test.
        with patch("socket.create_connection", side_effect=AssertionError("Conexiones reales prohibidas en las pruebas")):
            spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    finally:
        sys.dont_write_bytecode = bytecode_setting
    return module
