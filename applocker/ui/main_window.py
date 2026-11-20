"""Main application window: sidebar navigation + page host.

Layout
------
+-----------------------------------------------------------+
|  AppLocker        |  [toast layer]                         |
|  ----             |                                        |
|  [branded header] |   Page content (single child frame)    |
|  Home             |                                        |
|  Applications     |                                        |
|  Groups           |                                        |
|  Activity         |                                        |
|  Settings         |                                        |
|  ----             |                                        |
|  Status: Active   |                                        |
|  About            |                                        |
+-----------------------------------------------------------+

The page area shows one page at a time; switching nav re-renders the page.
All interaction goes through ``controller`` — the window never mutates state
directly.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from applocker.core.app import AppController
from applocker.ui import icons, pages
from applocker.ui.theme import Palette, apply_theme
from applocker.ui.widgets import PageHeader, Toast
from applocker.version import APP_DISPLAY_NAME, APP_VERSION


class MainWindow:
    """Top-level application window.

    Not a Tk subclass — we take ownership of root so tests can create one
    headless-free. The UI thread drives ``controller.tick()`` on a timer.
    """

    NAV = [
        ("home", "Home"),
        ("applications", "Applications"),
        ("groups", "Groups"),
        ("activity", "Activity"),
        ("settings", "Settings"),
    ]

    def __init__(self, root: tk.Tk, controller: AppController,
                 tray_actions: dict | None = None, on_quit: Optional[Callable] = None):
        self.root = root
        self.controller = controller
        self.on_quit = on_quit
        self.tray_actions = tray_actions or {}
        self.pal: Palette | None = None
        self._current_page = "home"
        self._pages: dict[str, tk.Widget] = {}
        self._nav_var = tk.StringVar(value="Home")
        self._status_label: Optional[ttk.Label] = None
        self.icon_cache = icons.IconCache(root)

        root.title(APP_DISPLAY_NAME)
        root.minsize(1040, 640)
        self._center_window(root, 1180, 720)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._apply_theme()
        self._build_layout()
        self._restyle_sidebar()
        self.show_page("home")
        self.refresh_status()
        # Monitor timer: drive the process monitor from the UI loop.
        self._tick_after()

    # ------------------------------------------------------------------ #
    # Window placement
    # ------------------------------------------------------------------ #
    @staticmethod
    def _center_window(window, width: int, height: int) -> None:
        """Size and center a window on the primary display work area."""
        window.update_idletasks()
        sw = window.winfo_screenwidth()
        sh = window.winfo_screenheight()
        x = max(0, (sw - width) // 2)
        y = max(0, (sh - height) // 2)
        window.geometry(f"{width}x{height}+{x}+{y}")

    # ------------------------------------------------------------------ #
    # Layout
    # ------------------------------------------------------------------ #
    def _build_layout(self) -> None:
        self._container = tk.Frame(self.root, bg=self.root.cget("bg"))
        self._container.pack(fill="both", expand=True)

        self._sidebar = tk.Frame(self._container, width=210)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)

        content_host = tk.Frame(self._container, bg=self.root.cget("bg"))
        content_host.pack(side="left", fill="both", expand=True)
        self._content = tk.Frame(content_host, bg=self.root.cget("bg"))
        self._content.pack(fill="both", expand=True, padx=28, pady=22)

        self._toast_host = tk.Frame(content_host, bg=self.root.cget("bg"))
        self._toast_host.place(relx=0, rely=0, relwidth=1, relheight=1)

        self._build_sidebar()

    def _build_sidebar(self) -> None:
        brand = tk.Frame(self._sidebar, bg=self.root.cget("bg"))
        brand.pack(fill="x", pady=(24, 18))
        brand_ttl = tk.Label(brand, text="AppLocker", bg=self.root.cget("bg"),
                             font=("Segoe UI Semibold", 15), fg=self._fg())
        brand_ttl.pack(anchor="w", padx=20)
        brand_sub = tk.Label(brand, text=f"Version {APP_VERSION}", bg=self.root.cget("bg"),
                             font=("Segoe UI", 9), fg=self._muted())
        brand_sub.pack(anchor="w", padx=20, pady=(1, 0))

        for key, label in self.NAV:
            btn = tk.Label(self._sidebar, text=label, anchor="w", padx=20, pady=9,
                           bg=self.root.cget("bg"), fg=self._fg(),
                           font=("Segoe UI", 10), cursor="hand2")
            btn.pack(fill="x")
            btn.bind("<Button-1>", lambda _e, k=key: self.show_page(k))
            btn.bind("<Enter>", lambda _e, b=btn: b.configure(bg=self._hover()))
            btn.bind("<Leave>", lambda _e, b=btn, k=key: b.configure(
                bg=self._selected_bg() if self._current_page == k else self.root.cget("bg")))
            setattr(self, f"_nav_{key}", btn)

        ttk.Separator(self._sidebar).pack(fill="x", padx=14, pady=12)

        # Status line
        status_row = tk.Frame(self._sidebar, bg=self.root.cget("bg"))
        status_row.pack(fill="x", side="bottom", padx=14, pady=(0, 10))
        self._status_label = tk.Label(status_row, text="—", anchor="w",
                                      font=("Segoe UI", 9), bg=self.root.cget("bg"))
        self._status_label.pack(fill="x")

        about_btn = tk.Label(self._sidebar, text="About", anchor="w", padx=20, pady=8,
                             bg=self.root.cget("bg"), fg=self._muted(),
                             font=("Segoe UI", 9), cursor="hand2")
        about_btn.pack(side="bottom", fill="x")
        about_btn.bind("<Button-1>", lambda _e: self.show_page("about"))

    def _selected_bg(self) -> str:
        return self.pal.selection if self.pal else "#c9e3f9"

    def _fg(self) -> str:
        return self.pal.text if self.pal else "#0d1117"

    def _hover(self) -> str:
        return self.pal.hover_row if self.pal else "#eef4fb"

    def _muted(self) -> str:
        return self.pal.text_muted if self.pal else "#4e5868"

    def _apply_theme(self) -> None:
        theme = self.controller.get_setting("theme", "system")
        accent = self.controller.get_setting("accent_color", "system")
        self.pal = apply_theme(self.root, theme, {}, accent)
        self._restyle_sidebar()

    def _restyle_sidebar(self) -> None:
        if not hasattr(self, "_sidebar"):
            return
        pal = self.pal
        bg = pal.bg
        self._sidebar.configure(bg=bg)
        self._container.configure(bg=bg)
        self._content.configure(bg=bg)
        self._toast_host.configure(bg=bg)
        for child in self._sidebar.winfo_children():
            self._apply_bg(child, bg)

    def _apply_bg(self, widget, bg: str) -> None:
        try:
            widget.configure(bg=bg)
        except tk.TclError:
            pass
        try:
            for fg in ("fg",):
                pass
        except Exception:  # noqa: BLE001
            pass
        for child in getattr(widget, "winfo_children", lambda: [])():
            self._apply_bg(child, bg)

    # ------------------------------------------------------------------ #
    # Page management
    # ------------------------------------------------------------------ #
    def show_page(self, key: str) -> None:
        self._current_page = key
        for nav_key, label in self.NAV:
            btn = getattr(self, f"_nav_{nav_key}")
            bg = self._selected_bg() if nav_key == key else (self.pal.bg if self.pal else self.root.cget("bg"))
            btn.configure(bg=bg)

        # Destroy previous page widget (simple, avoids stale state).
        for child in self._content.winfo_children():
            child.destroy()

        page = self._make_page(key)
        page.pack(fill="both", expand=True)
        self._pages[key] = page

    def _make_page(self, key: str) -> tk.Widget:
        if key == "home":
            return pages.build_dashboard(self._content, self.controller, self)
        if key == "applications":
            return pages.build_applications(self._content, self.controller, self)
        if key == "groups":
            return pages.build_groups(self._content, self.controller, self)
        if key == "activity":
            return pages.build_activity(self._content, self.controller, self)
        if key == "settings":
            return pages.build_settings(self._content, self.controller, self)
        if key == "about":
            return pages.build_about(self._content, self.controller, self)
        return pages.build_empty(self._content, f"Unknown page: {key}", "")

    # ------------------------------------------------------------------ #
    # Status + monitor
    # ------------------------------------------------------------------ #
    def refresh_status(self) -> None:
        if not self._status_label:
            return
        status = self.controller.protection_status()
        text = {"active": "● Protection Active", "paused": "● Protection Paused"}.get(status, "● Unknown")
        color = self.pal.success if status == "active" else (self.pal.warning if status == "paused" else self.pal.danger)
        self._status_label.configure(text=text, fg=color if self.pal else "#0d1117")
        # Refresh the visible page too.
        for child in self._content.winfo_children():
            callback = getattr(child, "on_status_changed", None)
            if callback:
                callback()

    def _tick_after(self) -> None:
        try:
            self.controller.tick()
        except Exception:  # noqa: BLE001
            pass
        self.root.after(1100, self._tick_after)

    # ------------------------------------------------------------------ #
    # UX helpers
    # ------------------------------------------------------------------ #
    def toast(self, message: str, kind: str = "info") -> None:
        Toast(self._toast_host, message, kind, pal=self.pal).show()

    def refresh_pages(self) -> None:
        """Rebuild the active page (after a settings/theme/app change)."""
        self._apply_theme()
        key = self._current_page
        self.show_page(key)

    def _on_close(self) -> None:
        """System close button: hide to tray instead of quitting (unless
        protection is explicitly disabled / app closing from menu)."""
        self.root.withdraw()
        if self.on_quit:
            self.on_quit("hide")

    def quit_app(self) -> None:
        if self.on_quit:
            self.on_quit("quit")