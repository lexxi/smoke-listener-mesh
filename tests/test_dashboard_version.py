"""Dashboard badge must use one centrally declared version."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))
from dashboard_version import DASHBOARD_VERSION


class DashboardVersionTests(unittest.TestCase):
    def test_version_is_040(self):
        self.assertEqual(DASHBOARD_VERSION, "0.4.0")

    def test_monitor_template_uses_central_version(self):
        template = (ROOT / "web" / "templates" / "index.html").read_text(encoding="utf-8")
        app = (ROOT / "web" / "app.py").read_text(encoding="utf-8")
        self.assertIn("Dashboard v{{ dashboard_version }}", template)
        self.assertNotIn("Dashboard v0.4.0", template)
        self.assertIn('render_template("index.html", dashboard_version=DASHBOARD_VERSION)', app)


if __name__ == "__main__":
    unittest.main()
