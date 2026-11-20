"""Unit tests for the policy engine (scheduling logic)."""

import time
import unittest
from datetime import datetime

from applocker.core.policy import (
    PolicyEvaluator,
    PolicyRecord,
    ScheduleWindow,
    blocks_app,
    convert_schedule,
)


class ScheduleWindowTest(unittest.TestCase):
    def test_normal_window(self):
        w = ScheduleWindow(7, 0, 20, 0)
        self.assertTrue(w.allows(datetime(2026, 9, 8, 12, 0)))
        self.assertFalse(w.allows(datetime(2026, 9, 8, 22, 0)))
        self.assertFalse(w.allows(datetime(2026, 9, 8, 6, 59)))

    def test_overnight_window(self):
        w = ScheduleWindow(22, 0, 7, 0)
        self.assertFalse(w.allows(datetime(2026, 9, 8, 12, 0)))
        self.assertTrue(w.allows(datetime(2026, 9, 8, 23, 30)))
        self.assertTrue(w.allows(datetime(2026, 9, 8, 2, 0)))


class PolicyEvaluatorTest(unittest.TestCase):
    def setUp(self):
        self.pe = PolicyEvaluator()

    def test_always_blocks(self):
        rec = PolicyRecord(kind="always")
        self.assertTrue(self.pe.blocks(rec, datetime(2026, 9, 8, 10, 0)))

    def test_none_allows(self):
        rec = PolicyRecord(kind="none")
        self.assertFalse(self.pe.blocks(rec, datetime(2026, 9, 8, 10, 0)))

    def test_time_window(self):
        rec = PolicyRecord(kind="time", allow_start="09:00", allow_end="17:00")
        self.assertFalse(self.pe.blocks(rec, datetime(2026, 9, 8, 12, 0)))
        self.assertTrue(self.pe.blocks(rec, datetime(2026, 9, 8, 20, 0)))

    def test_schedule_outside_days_blocks(self):
        sched = convert_schedule(["Monday", "Tuesday"], 10, 0, 20, 0)
        rec = PolicyRecord(kind="schedule", schedule=sched)
        # Wednesday midday (not scheduled) → blocked.
        self.assertTrue(self.pe.blocks(rec, datetime(2026, 9, 9, 12, 0)))
        # Monday 12:00 → allowed.
        self.assertFalse(self.pe.blocks(rec, datetime(2026, 9, 7, 12, 0)))
        # Monday 21:00 (outside window) → blocked.
        self.assertTrue(self.pe.blocks(rec, datetime(2026, 9, 7, 21, 0)))

    def test_temp_unlock_overrides(self):
        rec = PolicyRecord(kind="always")
        rec.temporary_until = time.time() + 600
        self.assertFalse(self.pe.blocks(rec, datetime.now()))

    def test_session_unlock_overrides(self):
        rec = PolicyRecord(kind="always")
        rec.session_unlocked = True
        self.assertFalse(self.pe.blocks(rec, datetime.now()))


class AppBlockTest(unittest.TestCase):
    def test_blocks_app_policy(self):
        app = {"id": "a1", "policy": "always", "schedule_json": {}, "temp_unlock": 0,
               "allow_start": "07:00", "allow_end": "20:00"}
        self.assertTrue(blocks_app(app, PolicyEvaluator()))

    def test_temp_unlock_allows(self):
        app = {"id": "a1", "policy": "always", "schedule_json": {},
               "temp_unlock": int(time.time()) + 300}
        self.assertFalse(blocks_app(app, PolicyEvaluator()))

    def test_no_groups_unprotected(self):
        app = {"id": "a1", "policy": "none", "schedule_json": {}, "temp_unlock": 0}
        self.assertFalse(blocks_app(app, PolicyEvaluator()))


if __name__ == "__main__":
    unittest.main()