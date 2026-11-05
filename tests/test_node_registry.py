"""Node enrollment regression: input validation and authorized mutations."""
import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))
registry = importlib.import_module("node_registry")
roles = importlib.import_module("node_role_policy")


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.old_nodes = registry.NODES_FILE
        self.old_targets = roles.TARGETS_FILE
        self.old_registry_targets = registry.TARGETS_FILE
        self.base = Path(self.tmp.name)
        registry.NODES_FILE = self.base / "nodes.csv"
        roles.TARGETS_FILE = self.base / "node_targets.json"
        registry.TARGETS_FILE = roles.TARGETS_FILE
        # load_targets defaults are bound at function definition, so registry
        # endpoint instead uses a patched function for test isolation.
        self.old_loader = registry.load_targets
        registry.load_targets = lambda: roles.load_targets(roles.TARGETS_FILE)
        self.addCleanup(self.restore)
        from flask import Flask
        app = Flask(__name__)
        app.register_blueprint(registry.bp)
        app.testing = True
        self.client = app.test_client()
        self.headers = {"X-Registry-CSRF": registry.csrf}

    def restore(self):
        registry.NODES_FILE = self.old_nodes
        roles.TARGETS_FILE = self.old_targets
        registry.TARGETS_FILE = self.old_registry_targets
        registry.load_targets = self.old_loader

    def test_auth_and_save(self):
        node = "0000123456789ABC"
        data = {"node_id": node, "name": "TestC3", "location": "Werkbank", "ota": True}
        self.assertEqual(self.client.post("/api/nodes/registry", json=data).status_code, 403)
        result = self.client.post("/api/nodes/registry", json=data, headers=self.headers)
        self.assertEqual(result.status_code, 200, result.get_json())
        self.assertEqual(roles.load_targets(roles.TARGETS_FILE), {node})
        self.assertIn("TestC3", registry.NODES_FILE.read_text(encoding="utf-8"))
        self.assertEqual(len(self.client.get("/api/nodes/registry").get_json()["entries"]), 1)

    def test_unknown_gateway_cannot_be_ota_target(self):
        gateway_id = registry.TRUSTED_GATEWAYS[registry.LOGGER_PORT][1]
        data = {"node_id": gateway_id, "name": "Gateway", "location": "PC", "ota": True}
        response = self.client.post("/api/nodes/registry", json=data, headers=self.headers)
        self.assertEqual(response.status_code, 400)

    def test_existing_kitchen_garage_receivers_remain_eligible_for_ota_and_location(self):
        for node in ("000094457F6E27AC", "000058FE7D6E27AC"):
            data = {"node_id": node, "name": "Test", "location": "Alt", "ota": True}
            first = self.client.post("/api/nodes/registry", json=data, headers=self.headers)
            self.assertEqual(first.status_code, 200, first.get_json())
            data["location"] = "Neuer Standort"
            result = self.client.post("/api/nodes/registry", json=data, headers=self.headers)
            self.assertEqual(result.status_code, 200, result.get_json())
            self.assertIn(node, roles.load_targets(roles.TARGETS_FILE))
        self.assertEqual(len(self.client.get("/api/nodes/registry").get_json()["entries"]), 2)
        self.assertEqual(self.client.get("/api/nodes/registry").get_json()["gateway_nodes"],
                         [registry.TRUSTED_GATEWAYS[registry.LOGGER_PORT][1]])

    def test_fifth_allowed_and_sixth_rejected(self):
        for i in range(1, 7):
            node = "0000" + f"{i:012X}"
            data = {"node_id": node, "name": "Test", "location": "", "ota": True}
            response = self.client.post("/api/nodes/registry", json=data, headers=self.headers)
            self.assertEqual(response.status_code, 200 if i <= 5 else 409)
        self.assertEqual(len(roles.load_targets(roles.TARGETS_FILE)), 5)

    def test_invalid_inputs_are_not_written(self):
        data = {"node_id": "0000000000000001", "name": "bad,name", "location": "Lab", "ota": True}
        response = self.client.post("/api/nodes/registry", json=data, headers=self.headers)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(registry.NODES_FILE.exists())


if __name__ == "__main__":
    unittest.main()
