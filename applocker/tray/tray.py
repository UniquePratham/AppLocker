"""System tray integration via pystray.

The tray is a first-class surface:

* Open Aegis             → show dashboard (requires master if locked)
* Protected Apps          → opens the Applications page
* Pause Protection        → submenu of durations (auth-gated)
* Quick Lock              → reassert all policies immediately
* Security Status         → read-only label of current status
* Settings                → opens the Settings page
* Exit                    → full shutdown (auth-gated, warns protection stops)

Closing the window alone never stops background protection: that only happens
on an explicit, confirmed Exit.
"""

from __future__ import annotations

import os
import threading
from typing import Callable, Optional

import pystray
from PIL import Image

from applocker.core.app import AppController
from applocker.util.logging import get_logger
from applocker.version import APP_DISPLAY_NAME

log = get_logger()


class TrayController:
    def __init__(self, controller: AppController, icon_path: Optional[str] = None,
                 callbacks: Optional[dict] = None):
        self.controller = controller
        self.callbacks = callbacks or {}
        self.icon = None
        self.icon_path = icon_path
        self._menu = None

    def _on_open(self, icon, item) -> None:
        cb = self.callbacks.get("open")
        if cb:
            cb()

    def _on_protected_apps(self, icon, item) -> None:
        cb = self.callbacks.get("applications")
        if cb:
            cb()

    def _on_settings(self, icon, item) -> None:
        cb = self.callbacks.get("settings")
        if cb:
            cb()

    def _on_quick_lock(self, icon, item) -> None:
        self.controller.lock_all()
        cb = self.callbacks.get("toast")
        if cb:
            cb("Quick Lock: all policies reasserted", "success")

    def _on_pause(self, minutes) -> None:
        def _pause(icon, item):
            # Prefer an auth-gated UI callback if the host supplied one.
            ui_pause = self.callbacks.get("pause")
            if ui_pause:
                ui_pause(minutes)
                return
            self.controller.pause_protection(minutes)
            cb = self.callbacks.get("toast")
            if cb:
                cb(f"Protection paused for {minutes} min", "info")
        return _pause

    def _on_pause_manual(self, icon, item) -> None:
        ui_pause = self.callbacks.get("pause_manual")
        if ui_pause:
            ui_pause()
            return
        self.controller.pause_protection_until_resumed()
        cb = self.callbacks.get("toast")
        if cb:
            cb("Protection paused until resumed", "info")

    def _on_resume(self, icon, item) -> None:
        ui_resume = self.callbacks.get("resume")
        if ui_resume:
            ui_resume()
            return
        self.controller.resume_protection()
        cb = self.callbacks.get("toast")
        if cb:
            cb("Protection resumed", "success")

    def _on_exit(self, icon, item) -> None:
        ui_exit = self.callbacks.get("exit_confirm")
        if ui_exit:
            ui_exit()
            return
        cb = self.callbacks.get("exit")
        if cb:
            cb()

    def pause_submenu(self) -> pystray.Menu:
        items = []
        for label, minutes in [("5 minutes", 5), ("15 minutes", 15),
                               ("30 minutes", 30), ("1 hour", 60)]:
            items.append(pystray.MenuItem(label, self._on_pause(minutes)))
        items.append(pystray.MenuItem("Until manually resumed", self._on_pause_manual))
        return pystray.Menu(*items)

    def build_menu(self) -> pystray.Menu:
        status = self.controller.protection_status()
        status_item = []
        if status == "active":
            status_item = [
                pystray.MenuItem("● Protection Active", None, enabled=False),
                pystray.MenuItem("Pause protection…", self.pause_submenu()),
            ]
        else:
            status_item = [
                pystray.MenuItem("● Protection Paused", None, enabled=False),
                pystray.MenuItem("Resume protection", self._on_resume),
            ]
        items = [
            pystray.MenuItem("Open Aegis", self._on_open, default=True),
            pystray.MenuItem("Protected Apps", self._on_protected_apps),
            pystray.MenuItem("Settings", self._on_settings),
            pystray.MenuItem("Quick Lock", self._on_quick_lock),
            pystray.Menu.SEPARATOR,
            *status_item,
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit Aegis", self._on_exit),
        ]
        return pystray.Menu(*items)

    def update(self) -> None:
        """Rebuild the menu to reflect current status."""
        if not self.icon:
            return
        self.icon.menu = self.build_menu()
        self.icon.update_menu()

    def run(self) -> None:
        image = Image.open(self.icon_path).convert("RGBA") if self.icon_path and os.path.exists(self.icon_path) \
            else self._default_icon()
        self.icon = pystray.Icon("Aegis", image, APP_DISPLAY_NAME, self.build_menu())
        self.icon.run()

    @staticmethod
    def _default_icon() -> Image.Image:
        from applocker.util.brand import render_icon
        return render_icon(64)

    def stop(self) -> None:
        if self.icon:
            try:
                self.icon.stop()
            except Exception:  # noqa: BLE001
                pass
