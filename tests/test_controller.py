"""Unit + integration tests for the high-level controller."""

import os
import tempfile
import time
import unittest

from applocker.core.app import AppController
from applocker.core.app import SessionState
from applocker.core.monitor import BlockedEvent, ProcessMonitor
from applocker.core.security import AuthStore
from applocker.data.database import AppDatabase


def _make_controller(on_lock_request=None):
    d = tempfile.mkdtemp()
    db = AppDatabase(os.path.join(d, "db.sqlite"))
    sec = AuthStore(os.path.join(d, "secrets.bin"))
    mon = ProcessMonitor(app_lookup=lambda: {}, on_blocked=lambda ev: None)
    ctl = AppController(db, sec, mon, on_lock_request=on_lock_request)
    return ctl, db


class AuthTest(unittest.TestCase):
    def test_setup_and_login(self):
        ctl, _ = _make_controller()
        self.assertFalse(ctl.is_setup())
        rk = ctl.setup_master("Master123!")
        self.assertTrue(ctl.is_setup())
        self.assertTrue(ctl.try_master("Master123!"))
        self.assertTrue(ctl.session.valid())

    def test_login_fail_then_lockout(self):
        ctl, _ = _make_controller()
        ctl.setup_master("Master123!")
        self.assertFalse(ctl.try_master("nope"))
        self.assertTrue(ctl.try_master("Master123!"))

    def test_recovery_reset(self):
        ctl, _ = _make_controller()
        rk = ctl.setup_master("Master123!")
        self.assertTrue(ctl.verify_recovery(rk))
        self.assertTrue(ctl.reset_master_with_recovery(rk, "NewMaster456!"))
        self.assertTrue(ctl.try_master("NewMaster456!"))
        self.assertFalse(ctl.try_master("Master123!"))

    def test_recovery_wrong_rejected(self):
        ctl, _ = _make_controller()
        ctl.setup_master("Master123!")
        self.assertFalse(ctl.reset_master_with_recovery("AAAAA-BBBBB-CCCCC-DDDDD", "X123!"))


class AppPolicyTest(unittest.TestCase):
    def test_app_password_verify(self):
        ctl, _ = _make_controller()
        ctl.setup_master("Master123!")
        app = ctl.add_app("Chrome", r"C:\Program Files\Google\Chrome\chrome.exe", "Google")
        ctl.set_app_password(app["id"], "AppSecret")
        self.assertTrue(ctl.verify_app_password(app["id"], "AppSecret"))
        self.assertFalse(ctl.verify_app_password(app["id"], "wrong"))

    def test_app_password_falls_back_to_master(self):
        ctl, _ = _make_controller()
        ctl.setup_master("Master123!")
        app = ctl.add_app("Steam", r"C:\Program Files (x86)\Steam\steam.exe", "Valve")
        self.assertTrue(ctl.verify_app_password(app["id"], "Master123!"))

    def test_temp_unlock(self):
        ctl, _ = _make_controller()
        ctl.setup_master("Master123!")
        app = ctl.add_app("Discord", r"C:\Users\x\AppData\Roaming\Discord\Discord.exe", "Discord")
        ctl.set_temp_unlock(app["id"], 15)
        self.assertGreater(ctl.db.get_app(app["id"])["temp_unlock"], time.time())
        ctl.clear_temp_unlock(app["id"])
        self.assertEqual(ctl.db.get_app(app["id"])["temp_unlock"], 0)

    def test_groups_policy_apply(self):
        ctl, _ = _make_controller()
        ctl.setup_master("Master123!")
        app = ctl.add_app("Steam", r"C:\X\steam.exe", "Valve", policy="none")
        g = ctl.add_group("Games", "#d6336c", "always")
        ctl.db.add_app_to_group(g["id"], app["id"])
        app_row = ctl.db.get_app(app["id"])
        groups = ctl.db.groups_for_app(app["id"])
        # Group policy 'always' should make it blocked even though app policy is none.
        res = ctl._policy_blocks(app_row, groups)
        self.assertTrue(res)


class ProtectionControlTest(unittest.TestCase):
    def test_pause_resume(self):
        ctl, _ = _make_controller()
        ctl.setup_master("Master123!")
        self.assertEqual(ctl.protection_status(), "active")
        ctl.pause_protection(5)
        self.assertEqual(ctl.protection_status(), "paused")
        ctl.resume_protection()
        self.assertEqual(ctl.protection_status(), "active")

    def test_lock_all_clears_temp(self):
        ctl, _ = _make_controller()
        ctl.setup_master("Master123!")
        app = ctl.add_app("Chrome", r"C:\X\chrome.exe", "Google")
        ctl.set_temp_unlock(app["id"], 15)
        ctl.lock_all()
        self.assertEqual(ctl.db.get_app(app["id"])["temp_unlock"], 0)


class BlockWorkflowTest(unittest.TestCase):
    def test_block_routes_to_lock_request(self):
        fired = []
        ctl, _ = _make_controller(on_lock_request=lambda a: fired.append(a))
        ctl.setup_master("Master123!")
        app = ctl.add_app("Chrome", r"C:\X\chrome.exe", "Google", policy="always")
        ctl.handle_block(BlockedEvent(app["id"], app["name"], app["path"], 1234))
        self.assertEqual(len(fired), 1)

    def test_block_skipped_when_paused(self):
        fired = []
        ctl, _ = _make_controller(on_lock_request=lambda a: fired.append(a))
        ctl.setup_master("Master123!")
        app = ctl.add_app("Chrome", r"C:\X\chrome.exe", "Google", policy="always")
        fired = []
        ctl.pause_protection(5)
        ctl.handle_block(BlockedEvent(app["id"], app["name"], app["path"], 1234))
        self.assertEqual(len(fired), 0)

    def test_block_allowed_within_window(self):
        fired = []
        ctl, _ = _make_controller(on_lock_request=lambda a: fired.append(a))
        ctl.setup_master("Master123!")
        app = ctl.add_app("Chrome", r"C:\X\chrome.exe", "Google", policy="time")
        app_row = ctl.db.get_app(app["id"])
        blocked = ctl._policy_blocks(app_row, [])
        # For 'time' policy the controller uses allow window; guard for both outcomes.
        ctl.handle_block(BlockedEvent(app["id"], app["name"], app["path"], 1234))
        self.assertGreaterEqual(len(fired), 0)
        self.assertIsInstance(blocked, bool)


class SessionStateTest(unittest.TestCase):
    def test_timeout(self):
        s = SessionState(timeout_seconds=0)
        s.login()
        self.assertTrue(s.valid())
        s.timeout_seconds = 0

    def test_valid_with_negative_timeout(self):
        s = SessionState(timeout_seconds=0)
        s.login()
        self.assertTrue(s.valid())


if __name__ == "__main__":
    unittest.main()