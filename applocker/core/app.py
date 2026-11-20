"""Application controller.

The controller is the single mutable state owner of the app: it owns the
database, secret store, monitor, and the current security session. The UI
(read-only views) talk *only* to this controller for state transitions, so
business logic stays UI-free and unit-testable.

Threading model: the UI thread drives ``tick()`` (monitor poll) on a timer.
The controller itself does not spawn threads; lock screens are modal dialogs
driven from the UI, invoked via the ``on_block_request`` hook.
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Callable, Optional

from applocker.core.monitor import BlockedEvent, ProcessMonitor
from applocker.core.policy import PolicyEvaluator
from applocker.core.security import (
    AuthStore,
    BruteForceGuard,
    BruteForcePolicy,
    generate_recovery_key,
    normalize_recovery_key,
)
from applocker.data.database import AppDatabase
from applocker.util.logging import get_logger
from applocker.util.winutil import launch_path, terminate_pid

log = get_logger()


# --------------------------------------------------------------------------- #
# Session state (auth)
# --------------------------------------------------------------------------- #
class SessionState:
    """Tracks whether the user is authenticated into the dashboard."""

    def __init__(self, timeout_seconds: int = 300):
        self.timeout_seconds = timeout_seconds
        self.auth_at: float = 0.0
        self.authed = False
        self._lock = threading.Lock()

    def login(self) -> None:
        with self._lock:
            self.authed = True
            self.auth_at = time.monotonic()

    def logout(self) -> None:
        with self._lock:
            self.authed = False

    def valid(self) -> bool:
        with self._lock:
            if not self.authed:
                return False
            if self.timeout_seconds > 0 and time.monotonic() - self.auth_at > self.timeout_seconds:
                self.authed = False
                return False
            return True


# --------------------------------------------------------------------------- #
# Pause protection state
# --------------------------------------------------------------------------- #
@dataclass
class PauseState:
    until: float = 0.0
    reason: str = ""

    def active(self) -> bool:
        return time.time() < self.until

    def remaining(self) -> int:
        if not self.until:
            return 0
        if self.until == float("inf"):
            return -1  # indefinite
        return max(0, int(self.until - time.time()))


# --------------------------------------------------------------------------- #
# The controller
# --------------------------------------------------------------------------- #
class AppController:
    """Central facade used by the GUI and represented in tests."""

    def __init__(self, db: AppDatabase, secrets: AuthStore, monitor: ProcessMonitor,
                 session: Optional[SessionState] = None,
                 on_lock_request: Optional[Callable[[dict], None]] = None,
                 on_status_change: Optional[Callable[[], None]] = None):
        self.db = db
        self.secrets = secrets
        self.monitor = monitor
        self.session = session or SessionState()
        self.on_lock_request = on_lock_request
        self.on_status_change = on_status_change
        self.pause = PauseState()
        self.lock_guard = BruteForceGuard()
        self.master_guard = BruteForceGuard(BruteForcePolicy(max_attempts=5, lockout_seconds=120))
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ #
    # Auth
    # ------------------------------------------------------------------ #
    def is_setup(self) -> bool:
        return self.secrets.is_initialized()

    def setup_master(self, password: str) -> str:
        """First-run: create master password and generate a recovery key."""
        rec_key = generate_recovery_key()
        self.secrets.set_master(password, recovery_key=rec_key)
        self.db.add_event("setup", "AppLocker initialized with master password")
        self._notify()
        return rec_key

    def try_master(self, password: str) -> bool:
        if self.master_guard.is_locked():
            return False
        if self.secrets.verify_master(password):
            self.master_guard.record_success()
            self.session.login()
            self.db.add_event("auth", "Master authentication succeeded")
            self._notify()
            return True
        delay = self.master_guard.record_failure()
        self.db.add_event("auth_failed", "Master authentication failed")
        if delay > 0:
            self.db.add_event("lockout", f"Authentication temporarily locked for {int(delay)}s")
        return False

    def verify_master_for_lockscreen(self, password: str) -> bool:
        """Verify the master password without opening a session (lock screen)."""
        if self.master_guard.is_locked():
            return False
        if self.secrets.verify_master(password):
            self.master_guard.record_success()
            return True
        self.master_guard.record_failure()
        return False

    def change_master(self, old: str, new: str) -> bool:
        ok = self.secrets.change_master(old, new)
        if ok:
            self.db.add_event("settings", "Master password changed")
            self._notify()
        return ok

    def logout(self) -> None:
        self.session.logout()
        self.db.add_event("auth", "Dashboard locked")
        self._notify()

    # ------------------------------------------------------------------ #
    # App management
    # ------------------------------------------------------------------ #
    def add_app(self, name: str, path: str, publisher: str = "", version: str = "",
                policy: str = "always", icon_cache: str = "") -> dict:
        app_id = str(uuid.uuid4())
        self.db.add_app(app_id, name, path, publisher, version, icon_cache,
                        policy=policy, favorite=False)
        if policy != "none":
            self.db.add_event("app_added", f"Added protected application: {name}", app_id)
        else:
            self.db.add_event("app_added", f"Added application: {name}", app_id)
        self._notify()
        return self.db.get_app(app_id) or {}

    def remove_app(self, app_id: str) -> None:
        app = self.db.get_app(app_id)
        name = app["name"] if app else app_id
        self.secrets.remove_app_verifier(app_id)
        self.db.delete_app(app_id)
        self.db.add_event("app_removed", f"Removed application: {name}", app_id)
        self._notify()

    def set_app_policy(self, app_id: str, policy: str, schedule_json: Optional[dict] = None) -> None:
        self.db.update_app(app_id, policy=policy, schedule_json=schedule_json or {})
        self.db.add_event("policy", "Application policy updated", app_id)
        self._notify()

    def set_app_password(self, app_id: str, password: str) -> None:
        self.secrets.set_app_verifier(app_id, password)

    def verify_app_password(self, app_id: str, password: str, guard: Optional[BruteForceGuard] = None) -> bool:
        guard = guard or self.lock_guard
        if guard.is_locked():
            return False
        verifier = self.secrets.app_verifier(app_id)
        if verifier:
            from applocker.core.crypto import PasswordHasher
            ok = PasswordHasher().verify(password, verifier)
        else:
            ok = self.secrets.verify_master(password)
        if ok:
            guard.record_success()
            return True
        guard.record_failure()
        return False

    def set_temp_unlock(self, app_id: str, minutes: int) -> None:
        until = time.time() + minutes * 60
        self.db.set_temp_unlock(app_id, until)
        self.db.add_event("unlock", f"Temporary unlock ({minutes} min)", app_id)
        self._notify()

    def clear_temp_unlock(self, app_id: str) -> None:
        self.db.set_temp_unlock(app_id, 0)
        self.db.add_event("policy", "Temporary unlock cleared", app_id)
        self._notify()

    def set_favorite(self, app_id: str, fav: bool) -> None:
        self.db.update_app(app_id, favorite=fav)
        self._notify()

    # ------------------------------------------------------------------ #
    # Groups
    # ------------------------------------------------------------------ #
    def add_group(self, name: str, color: str = "#0b6bce", policy: str = "none",
                  schedule_json: Optional[dict] = None) -> dict:
        group_id = str(uuid.uuid4())
        self.db.add_group(group_id, name, color, policy, schedule_json or {})
        self.db.add_event("group", f"Created group: {name}")
        self._notify()
        return self.db.get_group(group_id) or {}

    def delete_group(self, group_id: str) -> None:
        g = self.db.get_group(group_id)
        name = g["name"] if g else group_id
        self.db.delete_group(group_id)
        self.db.add_event("group", f"Deleted group: {name}")
        self._notify()

    def update_group(self, group_id: str, **fields) -> None:
        self.db.update_group(group_id, **fields)
        self.db.add_event("group", "Group updated")
        self._notify()

    # ------------------------------------------------------------------ #
    # Protection control
    # ------------------------------------------------------------------ #
    def pause_protection(self, minutes: int) -> None:
        self.pause = PauseState(until=time.time() + minutes * 60, reason=f"{minutes} min")
        self.monitor.set_paused(True)
        self.db.add_event("protection", f"Protection paused for {minutes} minute(s)")
        self._notify()

    def resume_protection(self) -> None:
        self.pause = PauseState()
        self.monitor.set_paused(False)
        self.db.add_event("protection", "Protection resumed")
        self._notify()

    def pause_protection_until_resumed(self) -> None:
        """Pause protection indefinitely (until the user resumes it)."""
        self.pause = PauseState(until=float("inf"), reason="manual")
        self.monitor.set_paused(True)
        self.db.add_event("protection", "Protection paused (manual)")
        self._notify()

    def lock_all(self) -> None:
        """Reassert all policies: clear temp unlocks, resume if paused."""
        for app in self.db.list_apps():
            self.db.set_temp_unlock(app["id"], 0)
        self.pause = PauseState()
        self.monitor.set_paused(False)
        self.db.add_event("protection", "Quick Lock: all policies reasserted")
        self._notify()

    def protection_active(self) -> bool:
        return not self.pause.active() and not self.monitor.paused

    def protection_status(self) -> str:
        if self.pause.active():
            return "paused"
        if self.monitor.paused:
            return "paused"
        return "active"

    # ------------------------------------------------------------------ #
    # Block workflow (called by monitor on detection)
    # ------------------------------------------------------------------ #
    def handle_block(self, event: BlockedEvent) -> None:
        """Called when the monitor detects a protected app was launched.

        Terminates the offending process, then routes to the UI lock screen.
        """
        if self.pause.active() or self.monitor.paused:
            return
        app = self.db.get_app(event.app_id)
        if not app:
            return
        # Verify the policy still blocks (temp unlock may have been granted).
        groups = self.db.groups_for_app(app["id"])
        if not self._policy_blocks(app, groups):
            self.db.add_event("allowed", f"{app['name']} launched within allowed window", app["id"])
            return
        terminate_pid(event.pid)
        self.db.add_event("blocked", f"{app['name']} blocked from launching", app["id"])
        if self.on_lock_request:
            self.on_lock_request(app)

    def _policy_blocks(self, app: dict, groups: list[dict]) -> bool:
        evaluator = PolicyEvaluator()
        from applocker.core.policy import blocks_app
        return blocks_app(app, evaluator, groups)

    # ------------------------------------------------------------------ #
    # Lock screen outcome
    # ------------------------------------------------------------------ #
    def grant_launch(self, app: dict) -> None:
        path = app.get("path", "")
        if path and os.path.isfile(path):
            ok = launch_path(path)
            if ok:
                self.db.add_event("launch", f"{app['name']} launched after unlock", app["id"])
        else:
            self.db.add_event("launch", f"{app['name']} unlocked (path missing)", app["id"])

    # ------------------------------------------------------------------ #
    # Settings + events
    # ------------------------------------------------------------------ #
    def get_setting(self, key: str, default=None):
        return self.db.get_setting(key, default)

    def set_setting(self, key: str, value) -> None:
        self.db.set_setting(key, value)
        self.db.add_event("settings", f"Setting updated: {key}")
        self._notify()

    def log_event(self, event_type: str, message: str, app_id: str = "") -> None:
        self.db.add_event(event_type, message, app_id)

    def _notify(self) -> None:
        if self.on_status_change:
            self.on_status_change()

    # ------------------------------------------------------------------ #
    # Monitoring config
    # ------------------------------------------------------------------ #
    def monitor_apps_map(self) -> dict[str, dict]:
        """Build ``{lowercased_path: app_row}`` for the monitor."""
        out = {}
        for app in self.db.list_apps():
            if app.get("policy", "none") == "none":
                continue
            path = app.get("path", "").lower()
            if path:
                out[path] = app
        return out

    def tick(self) -> None:
        self.monitor.poll()

    # ------------------------------------------------------------------ #
    # Import / export (no secrets)
    # ------------------------------------------------------------------ #
    def export_config(self) -> dict:
        return self.db.export()

    def import_config(self, data: dict, replace: bool = True) -> None:
        self.db.import_(data, replace)
        self.db.add_event("settings", "Configuration imported")
        self._notify()

    # ------------------------------------------------------------------ #
    # Recovery
    # ------------------------------------------------------------------ #
    def recovery_key(self) -> Optional[str]:
        return self.secrets.get_recovery_key()

    def verify_recovery(self, typed: str) -> bool:
        return self.secrets.verify_recovery_key(normalize_recovery_key(typed))

    def reset_master_with_recovery(self, typed: str, new_password: str) -> bool:
        """Emergency path: prove the recovery key, then set a new master."""
        if not self.secrets.verify_recovery_key(normalize_recovery_key(typed)):
            return False
        # Re-key the master verifier; recovery key stays usable.
        stored = self.secrets.get_recovery_key()
        self.secrets.set_master(new_password, recovery_key=stored)
        self.db.add_event("recovery", "Master password reset via recovery key")
        self._notify()
        return True