"""Validación client-only de Compose: sin daemon, builds, imágenes ni .env real."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest

from _support import PROJECT_ROOT


DOCKER = shutil.which("docker")


@unittest.skipUnless(DOCKER, "Docker CLI no disponible para validar Compose")
class DeploymentTests(unittest.TestCase):
    def test_compose_validates_the_production_services(self):
        process = subprocess.run(
            [
                DOCKER, "compose", "--env-file", os.devnull,
                "--file", str(PROJECT_ROOT / "docker-compose.yml"),
                "config", "--no-interpolate", "--no-env-resolution", "--format", "json",
            ],
            cwd=PROJECT_ROOT,
            env={"PATH": os.environ.get("PATH", os.defpath), "HOME": str(Path.home())},
            capture_output=True, text=True, timeout=30,
        )
        # No incluir stdout/stderr: una configuración futura podría tener secretos.
        self.assertEqual(process.returncode, 0, f"Compose no valida (código {process.returncode}); salida omitida")
        config = json.loads(process.stdout)
        services = config["services"]
        self.assertIn("web", services)
        web = services["web"]
        # --no-interpolate preserves short syntax, including ${PORT:-8080}.
        # Other Compose versions may already emit normalized long syntax.
        def targets_web_http(port):
            if isinstance(port, dict):
                return str(port.get("target")) == "8080" and port.get("protocol", "tcp") == "tcp"
            if isinstance(port, str):
                target, _, protocol = port.rsplit(":", 1)[-1].partition("/")
                return target == "8080" and protocol in ("", "tcp")
            return False
        self.assertTrue(any(targets_web_http(port) for port in web.get("ports", [])))
        api_names = []
        for name, service in services.items():
            build = service.get("build", {})
            if isinstance(build, str):
                build = {"context": build}
            context = Path(build.get("context", "."))
            dockerfile = Path(build.get("dockerfile", "Dockerfile"))
            if context.name == "mail-api" or dockerfile.parent.name == "mail-api":
                api_names.append(name)
        self.assertEqual(len(api_names), 1, "Debe existir un único servicio construido desde mail-api/")


if __name__ == "__main__":
    unittest.main()
