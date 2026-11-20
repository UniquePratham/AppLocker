"""Unit tests for the SQLite data layer."""

import os
import tempfile
import unittest

from applocker.data.database import AppDatabase, SCHEMA_VERSION


class AppDatabaseTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.db = AppDatabase(os.path.join(self.dir, "test.db"))

    def add_sample_app(self):
        self.db.add_app("app1", "Chrome", r"C:\Program Files\Google\Chrome\chrome.exe",
                        "Google", "120.0")
        self.db.add_app("app2", "Steam", r"C:\Program Files (x86)\Steam\steam.exe",
                        "Valve")

    def test_add_list_get_delete(self):
        self.add_sample_app()
        apps = self.db.list_apps()
        self.assertEqual(len(apps), 2)
        app = self.db.get_app("app1")
        self.assertEqual(app["name"], "Chrome")
        self.assertEqual(app["path"], r"C:\Program Files\Google\Chrome\chrome.exe")
        self.db.delete_app("app1")
        self.assertIsNone(self.db.get_app("app1"))
        self.assertEqual(len(self.db.list_apps()), 1)

    def test_update_app(self):
        self.add_sample_app()
        self.db.update_app("app1", favorite=True, policy="time")
        app = self.db.get_app("app1")
        self.assertTrue(app["favorite"])
        self.assertEqual(app["policy"], "time")

    def test_temp_unlock(self):
        self.add_sample_app()
        self.db.set_temp_unlock("app1", 1234567890)
        app = self.db.get_app("app1")
        self.assertEqual(app["temp_unlock"], 1234567890)
        self.db.set_temp_unlock("app1", 0)
        self.assertEqual(self.db.get_app("app1")["temp_unlock"], 0)

    def test_groups(self):
        self.add_sample_app()
        self.db.add_group("g1", "Browsers", "#4c6ef5", "always")
        self.db.add_app_to_group("g1", "app1")
        members = self.db.group_apps("g1")
        self.assertEqual(len(members), 1)
        self.assertEqual(members[0]["name"], "Chrome")
        groups = self.db.groups_for_app("app1")
        self.assertEqual(len(groups), 1)
        self.db.remove_app_from_group("g1", "app1")
        self.assertEqual(len(self.db.group_apps("g1")), 0)

    def test_events(self):
        self.db.add_event("blocked", "Chrome blocked", "app1")
        self.db.add_event("auth", "Master auth succeeded")
        events = self.db.list_events()
        self.assertEqual(len(events), 2)
        filtered = self.db.list_events(event_type="blocked")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(self.db.event_count(), 2)
        self.db.clear_events()
        self.assertEqual(self.db.event_count(), 0)

    def test_settings(self):
        self.db.set_setting("theme", "dark")
        self.db.set_setting("poll_interval_ms", 1200)
        self.assertEqual(self.db.get_setting("theme"), "dark")
        self.assertEqual(self.db.get_setting("poll_interval_ms"), 1200)
        self.assertIsNone(self.db.get_setting("missing"))
        self.assertEqual(self.db.get_setting("missing", "x"), "x")

    def test_integrity(self):
        self.assertTrue(self.db.integrity_check())

    def test_export_import_roundtrip(self):
        self.add_sample_app()
        self.db.add_group("g1", "Games", "#d6336c", "always")
        self.db.add_app_to_group("g1", "app2")
        self.db.set_setting("theme", "dark")
        data = self.db.export()
        self.assertEqual(len(data["apps"]), 2)
        self.assertEqual(len(data["groups"]), 1)

        db2 = AppDatabase(os.path.join(self.dir, "test2.db"))
        db2.import_(data)
        self.assertEqual(len(db2.list_apps()), 2)
        self.assertEqual(len(db2.list_groups()), 1)
        self.assertEqual(len(db2.group_apps("g1")), 1)


if __name__ == "__main__":
    unittest.main()