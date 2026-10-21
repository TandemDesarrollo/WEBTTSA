"""Pruebas de comportamiento del handler real con DOM/fetch simulados, sin red."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest


NODE = shutil.which("node")


@unittest.skipUnless(NODE, "Node.js no disponible: ejecutar tests/test_contact_frontend.js en un runtime JS")
class FrontendTests(unittest.TestCase):
    def test_contact_handler_behavior(self):
        harness = Path(__file__).with_name("test_contact_frontend.js")
        result = subprocess.run(
            [NODE, str(harness)], capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        report = json.loads(result.stdout)
        self.assertEqual(report["passed"], 11)
        self.assertEqual(len(report["cases"]), report["passed"])


if __name__ == "__main__":
    unittest.main()
