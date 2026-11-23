"""Aegis application bootstrap.

Creates the core services (DB, secrets, monitor, controller), shows
the first-run wizard or master-auth gate, then launches the main
window + system tray and drives the monitor on a UI timer.
"""

from __future__ import annotations

import os
import sys
import threading
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

from applocker.core.app import AppController
from applocker.core.monitor import BlockedEvent, ProcessMonitor
from applocker.core.security import AuthStore
from applocker.data.database import AppDatabase
from applocker.tray.tray import TrayController
from applocker.ui.icons import IconCache
from applocker.ui.lockscreen import LockScreen
from applocker.ui.main_window import MainWindow
from applocker.ui.setup_wizard import SetupWizard
from applocker.ui.tokens import palette, resolve_theme
from applocker.util.brand import render_icon, write_runtime_icons
from applocker.util.logging import setup_logging, get_logger
from applocker.util.paths import get_icon_cache_dir, get_platform_data_dir


log = get_logger()
_pal = palette("dark")  # module-level palette, replaced after theme resolution


def _apply_and_store_pal(root, theme, fonts=None, accent=None):
    global _pal
    _pal = palette(resolve_theme(theme), accent or "blue")
    return _pal


def _show_master_auth(root: tk.Tk, controller: AppController) -> bool:
    """Show the master auth dialog; returns True if authenticated."""
    from applocker.ui.lockscreen import MasterAuthDialog
    pal = palette(resolve_theme(controller.get_setting("theme", "system")), controller.get_setting("accent_color", "blue"))
    dlg = MasterAuthDialog(root, controller, pal)
    return dlg.show()


def _lock_request_factory(root: tk.Tk, controller: AppController,
                          icon_cache: IconCache):
    """Return an ``on_lock_request`` callback for ``controller.handle_block``.

    The monitor calls ``controller.handle_block`` (which terminates the PID
    and checks policy). When blocking is required, the controller invokes this
    ``on_lock_request`` to queue a ``LockScreen`` on the UI thread.
    """
    _lock = threading.Lock()
    pending: list[dict] = []

    def _dispatch():
        while True:
            with _lock:
                if not pending:
                    break
                app = pending.pop(0)
            photo = icon_cache.get(app.get("icon_cache") or "", 72)
            def _show(a=app, p=photo):
                try:
                    dlg = LockScreen(root, controller, _pal, a, p)
                    dlg.show()
                except Exception as exc:  # noqa: BLE001
                    log.error("Lock screen error: %s", exc)
            root.after(0, _show)
        root.after(500, _dispatch)

    def on_lock_request(app: dict):
        with _lock:
            pending.append(app)

    root.after(500, _dispatch)
    return on_lock_request


def run():
    setup_logging()
    log.info("Aegis starting")
    try:
        _run()
    except Exception:
        import traceback
        log.error("Fatal: %s", traceback.format_exc())
        raise

def _run():

    # Single-instance guard — prevent two SQLite writers competing.
    try:
        import win32event
        import win32api
        import winerror
        _m = win32event.CreateMutex(None, False, "AegisSingleInstanceMutex-v2")
        if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
            # Use a temporary hidden root for the messagebox.
            _r = ctk.CTk()
            _r.withdraw()
            messagebox.showerror("Aegis", "Aegis is already running.", parent=_r)
            _r.destroy()
            return
    except Exception:  # noqa: BLE001
        pass

    # Any error thrown inside a Tk callback must be logged, never allowed to
    # crash the frozen (no-console) app.  A caller that raises would otherwise
    # unwind through wait_window()/mainloop() and close silently.
    def _callback_error(_self, exc, val, tb):
        log.error("Tk callback error: %s", val)
        try:
            import traceback
            log.error("".join(traceback.format_exception(exc, val, tb)))
        except Exception:  # noqa: BLE001
            pass

    tk.Tk.report_callback_exception = _callback_error
    sys.excepthook = lambda exc, val, tb: _callback_error(None, exc, val, tb)

    # A windowed (console=False) build has no stderr, so an unhandled
    # exception would vanish. Mirror it into the log file.
    def _thread_hook(args):
        _callback_error(None, args.exc_type, args.exc_value, args.exc_traceback)

    threading.excepthook = _thread_hook

    # Ensure brand assets exist.
    from applocker.util import paths as _paths
    asset_dir = _paths.resource_path("assets")
    if not os.path.exists(os.path.join(asset_dir, "png", "aegis_256x256.png")):
        try:
            write_runtime_icons(asset_dir)
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not write brand assets: %s", exc)

    # Build core services.
    db = AppDatabase()
    secrets = AuthStore()

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    # The root must be genuinely mapped for Toplevel children to become
    # visible on Windows. Park it off-screen at a real size, then hide it
    # once the first window is up.
    root.geometry("1x1+0+0")
    root.deiconify()
    root.update()
    icon_cache = IconCache(root)

    def _empty_app_map():
        return {}

    def _noop_block(_ev: BlockedEvent):
        pass

    # Build monitor first with a placeholder; wire to controller after.
    monitor = ProcessMonitor(app_lookup=_empty_app_map, on_blocked=_noop_block)
    controller = AppController(db, secrets, monitor)

    # Wire monitor to controller: monitor detects -> controller.handle_block
    # terminates the PID and decides whether a LockScreen is needed. The
    # lock screen itself is queued via controller.on_lock_request.
    lock_request = _lock_request_factory(root, controller, icon_cache)
    controller.on_lock_request = lock_request
    monitor.app_lookup = controller.monitor_apps_map
    monitor.on_blocked = controller.handle_block

    # Brand icon on window frame (retain reference to avoid GC).
    icon_cache_dir = get_icon_cache_dir()
    root_icon_path = os.path.join(icon_cache_dir, "app_256.png")
    render_icon(256).save(root_icon_path, "PNG")
    # Tray icons render best at 32px; Windows scales down for the notification area.
    tray_icon_path = os.path.join(icon_cache_dir, "app_32.png")
    render_icon(32).save(tray_icon_path, "PNG")
    try:
        _photo = tk.PhotoImage(file=root_icon_path)
        root.tk.call("wm", "iconphoto", root._w, _photo)
        root._icon_photo = _photo  # noqa: SLF001  keep alive
    except Exception:  # noqa: BLE001
        pass

    # Start the tray before any window appears, so the notification-area icon
    # is present from launch (including during first-run setup). Callbacks are
    # lazy: the main window does not exist yet.
    _tray_holder = {}

    def _show_main() -> None:
        root.deiconify()
        root.lift()
        root.focus_force()

    def _tray_goto(page: str) -> None:
        _show_main()
        win = _tray_holder.get("win")
        if win is not None:
            win.show_page(page)

    def _tray_toast(message: str, kind: str) -> None:
        win = _tray_holder.get("win")
        if win is not None:
            win.toast(message, kind)

    def _start_tray() -> None:
        if _tray_holder.get("tray"):
            return
        tray = TrayController(
            controller,
            icon_path=tray_icon_path,
            callbacks={
                "open": lambda: root.after(0, _show_main),
                "applications": lambda: root.after(0, lambda: _tray_goto("applications")),
                "settings": lambda: root.after(0, lambda: _tray_goto("settings")),
                "toast": lambda m, k: root.after(0, lambda: _tray_toast(m, k)),
                "exit": lambda: root.after(0, lambda: _handle_close("quit")),
                "pause": lambda m: root.after(0, lambda: _tray_pause(m)),
                "pause_manual": lambda: root.after(0, _tray_pause_manual),
                "resume": lambda: root.after(0, _tray_resume),
                "exit_confirm": lambda: root.after(0, _tray_exit_confirm),
            },
        )
        _tray_holder["tray"] = tray
        threading.Thread(target=tray.run, daemon=True).start()

    # Defer tray start until the Tk event loop is running; pystray needs a
    # live message pump to register its notification-area icon.
    root.after(300, _start_tray)

    # First-run wizard (if no master password is set). The root stays withdrawn
    # so the wizard is the only visible window.
    if not controller.is_setup():
        _apply_and_store_pal(root, "system")
        log.info("showing setup wizard")
        try:
            SetupWizard(root, controller, _pal).show()
        except Exception:
            import traceback
            log.error("wizard failed: %s", traceback.format_exc())
            raise
        if not controller.is_setup():
            root.destroy()
            return

    # Master authentication.
    if not _show_master_auth(root, controller):
        root.destroy()
        return

    # Main window.
    theme = controller.get_setting("theme", "system")
    accent = controller.get_setting("accent_color", "system")
    _apply_and_store_pal(root, theme, None, accent)

    # Honour --startup / --minimized flag from run-at-login (no UI flash).
    start_minimized = any(a.lower() in ("--startup", "--minimized", "/startup") for a in sys.argv[1:])

    def _handle_close(reason: str) -> None:
        if reason == "quit":
            controller.logout()
            try:
                tray.stop()  # type: ignore[name-defined]
            except Exception:
                pass
            root.after(50, root.destroy)
            return
        root.withdraw()

    win = MainWindow(root, controller, on_quit=lambda reason: _handle_close(reason))
    _tray_holder["win"] = win

    # Auth-gated tray actions — tray menu must not bypass master password.
    def _tray_pause(minutes: int):
        def _ask():
            from applocker.ui.lockscreen import MasterAuthDialog
            dlg = MasterAuthDialog(root, controller, _pal, title="Pause Protection",
                                   prompt=f"Enter master password to pause for {minutes} minute(s).")
            if dlg.show():
                controller.pause_protection(minutes)
                win.toast(f"Protection paused for {minutes} min", "info")
                win.refresh_pages()
                try:
                    tray.update()
                except Exception:
                    pass
        root.after(0, _ask)

    def _tray_pause_manual():
        def _ask():
            from applocker.ui.lockscreen import MasterAuthDialog
            dlg = MasterAuthDialog(root, controller, _pal, title="Pause Protection",
                                   prompt="Enter master password to pause until resumed.")
            if dlg.show():
                controller.pause_protection_until_resumed()
                win.toast("Protection paused until resumed", "info")
                win.refresh_pages()
                try:
                    tray.update()
                except Exception:
                    pass
        root.after(0, _ask)

    def _tray_resume():
        def _ask():
            # Resume is re-enabling protection; still gate with master to avoid
            # accidental or malicious resume via tray spoofing inconsistency.
            from applocker.ui.lockscreen import MasterAuthDialog
            dlg = MasterAuthDialog(root, controller, _pal, title="Resume Protection",
                                   prompt="Enter master password to resume protection.")
            if dlg.show():
                controller.resume_protection()
                win.toast("Protection resumed", "success")
                win.refresh_pages()
                try:
                    tray.update()
                except Exception:
                    pass
        root.after(0, _ask)

    def _tray_exit_confirm():
        def _ask():
            if not messagebox.askyesno("Exit Aegis",
                                       "Protection will stop if Aegis exits.\n\nExit anyway?",
                                       parent=root):
                return
            from applocker.ui.lockscreen import MasterAuthDialog
            dlg = MasterAuthDialog(root, controller, _pal, title="Exit Aegis",
                                   prompt="Enter master password to exit.")
            if dlg.show():
                _handle_close("quit")
        root.after(0, _ask)

    # Tray (runs on a daemon thread).
    def _tray_open():
        root.after(0, lambda: (root.deiconify(), root.lift(), root.focus_force()))

    def _tray_apps():
        root.after(0, lambda: (root.deiconify(), win.show_page("applications")))

    def _tray_settings():
        root.after(0, lambda: (root.deiconify(), win.show_page("settings")))

    def _tray_toast(msg, kind):
        root.after(0, lambda: win.toast(msg, kind))

    if not start_minimized:
        root.deiconify()
    else:
        root.withdraw()
    root.mainloop()
    _tray_holder.get("tray") and _tray_holder["tray"].stop()

if __name__ == "__main__":
    run()
