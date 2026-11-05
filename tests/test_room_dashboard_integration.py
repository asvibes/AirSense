from pathlib import Path
import re
import unittest


class RoomDashboardIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.template = (cls.root / "app" / "templates" / "alerts.html").read_text(
            encoding="utf-8"
        )
        cls.dashboard = (
            cls.root / "app" / "static" / "js" / "dashboard.js"
        ).read_text(encoding="utf-8")

    def test_dashboard_template_loads_the_room_edit_script(self):
        self.assertRegex(
            self.template,
            re.compile(
                r"""url_for\('static',\s*filename='js/dashboard\.js'\)"""
            ),
        )

    def test_owner_room_card_action_calls_scoped_patch_endpoint(self):
        self.assertIn('config.role === "owner"', self.dashboard)
        self.assertIn('data-edit-room="${escapeHtml(room.id)}"', self.dashboard)
        self.assertIn('method: "PATCH"', self.dashboard)
        self.assertIn(
            "/rooms/${encodeURIComponent(roomId)}",
            self.dashboard,
        )

    def test_dashboard_room_form_supports_create_and_edit_modes(self):
        self.assertIn('form.dataset.roomId ? updateRoom(form) : createRoom(form)', self.dashboard)
        self.assertIn('method: "POST"', self.dashboard)
        self.assertIn('method: "PATCH"', self.dashboard)
        self.assertIn("custom_ventilation_source", self.template)
