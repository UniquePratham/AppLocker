"""Smoke test: build the real CustomTkinter UI and render every screen.

Creates the widgets, pumps the event loop once, swaps through all pages and
destroys. Catches import and layout wiring bugs that unit tests cannot.
"""

import os
import sys
import tempfile

import customtkinter as ctk

from applocker.core.app import AppController
from applocker.core.monitor import ProcessMonitor
from applocker.core.security import AuthStore
from applocker.data.database import AppDatabase
from applocker.ui.main_window import MainWindow
from applocker.ui.tokens import palette


def _make_controller():
    d = tempfile.mkdtemp()
    db = AppDatabase(os.path.join(d, "db.sqlite"))
    sec = AuthStore(os.path.join(d, "secrets.bin"))
    mon = ProcessMonitor(app_lookup=lambda: {}, on_blocked=lambda ev: None)
    ctl = AppController(db, sec, mon)
    ctl.setup_master("MasterSmoke!")
    for i, name in enumerate(["Chrome", "Steam", "Discord"]):
        ctl.add_app(name, rf"C:\Prog\{name}\{name}.exe", "Example",
                    policy="time" if i % 2 else "always")
    grp = ctl.add_group("Games", "#d6336c", "always")
    ctl.db.add_app_to_group(grp["id"], ctl.db.list_apps()[1]["id"])
    ctl.log_event("blocked", "Sample block event", ctl.db.list_apps()[0]["id"])
    return ctl


def main():
    ctl = _make_controller()

    ctk.set_appearance_mode("dark")
    root = ctk.CTk()
    root.geometry("1x1+0+0")
    root.deiconify()
    root.update()

    pal = palette("dark")
    win = MainWindow(root, ctl)
    win.toast("Hello", "info")

    for page in ["home", "applications", "groups", "activity", "settings", "about"]:
        win.show_page(page)
        root.update_idletasks()
        print(f"page ok: {page}")

    from applocker.ui.setup_wizard import SetupWizard

    wizard = SetupWizard(root, ctl, pal)
    root.update_idletasks()
    wizard.win.destroy()
    print("setup wizard ok")

    from applocker.ui.lockscreen import MasterAuthDialog

    auth = MasterAuthDialog(root, ctl, pal)
    root.update_idletasks()
    auth.win.destroy()
    print("auth dialog ok")

    from applocker.ui.lockscreen import LockScreen

    app = ctl.db.list_apps()[0]
    ls = LockScreen(root, ctl, pal, app)
    root.update_idletasks()
    ls.win.destroy()
    print("lock screen ok")

    root.destroy()
    print("SMOKE OK")


if __name__ == "__main__":
    main()