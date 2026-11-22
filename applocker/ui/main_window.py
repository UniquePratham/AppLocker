"""Aegis main window — CustomTkinter shell.

Layout: a calm sidebar (brand, navigation, live status) beside a single content
host that swaps pages. All state comes from ``AppController``; the window never
mutates security state directly.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk

from applocker.core.app import AppController
from applocker.ui import icons, screens
from applocker.ui.components import Toast
from applocker.ui.tokens import RADIUS, SPACE, TYPE, palette, resolve_theme
from applocker.version import APP_DISPLAY_NAME, APP_VERSION

NAV = [
    ("home", "Home", "⌂"),
    ("applications", "Applications", "▣"),
    ("groups", "Groups", "◫"),
    ("activity", "Activity", "◷"),
    ("settings", "Settings", "⚙"),
]


class MainWindow:
    def __init__(self, root: ctk.CTk, controller: AppController,
                 on_quit: Optional[Callable] = None):
        self.root = root
        self.controller = controller
        self.on_quit = on_quit
        self.icon_cache = icons.IconCache(root)

        self.theme_pref = controller.get_setting("theme", "system")
        self.accent_pref = controller.get_setting("accent_color", "blue")
        self.theme = resolve_theme(self.theme_pref)
        self.pal = palette(self.theme, self.accent_pref)

        self._current = "home"
        self._nav_buttons: dict[str, ctk.CTkButton] = {}
        self._toast_widget = None

        root.title(f"{APP_DISPLAY_NAME} — Modern Windows Application Access Control")
        root.geometry("1180x740")
        root.minsize(1040, 660)
        root.configure(fg_color=self.pal["bg"])
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        from applocker.util.brand import set_window_icon
        set_window_icon(root)

        self._build()
        self.show_page("home")
        self.refresh_status()
        self._tick()

    # ------------------------------------------------------------------ #
    # Shell
    # ------------------------------------------------------------------ #
    def _build(self) -> None:
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        self._sidebar = ctk.CTkFrame(
            self.root, width=232, corner_radius=0,
            fg_color=self.pal["bg_alt"], border_width=0,
        )
        self._sidebar.grid(row=0, column=0, sticky="nsw")
        self._sidebar.grid_propagate(False)
        self._build_sidebar()

        self._content = ctk.CTkFrame(self.root, fg_color=self.pal["bg"], corner_radius=0)
        self._content.grid(row=0, column=1, sticky="nsew", padx=SPACE["xl"], pady=SPACE["xl"])

    def _build_sidebar(self) -> None:
        pal = self.pal

        brand = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=SPACE["lg"], pady=(SPACE["xl"], SPACE["xl"]))

        logo = self.icon_cache.get("", 34)
        if logo is not None:
            ctk.CTkLabel(brand, text="", image=logo).pack(side="left", padx=(0, SPACE["md"]))

        brand_text = ctk.CTkFrame(brand, fg_color="transparent")
        brand_text.pack(side="left")
        ctk.CTkLabel(
            brand_text, text="Aegis", font=TYPE["heading"], text_color=pal["text"], anchor="w"
        ).pack(fill="x")
        ctk.CTkLabel(
            brand_text, text=f"v{APP_VERSION}", font=TYPE["caption"],
            text_color=pal["text_faint"], anchor="w"
        ).pack(fill="x")

        nav = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        nav.pack(fill="x", padx=SPACE["md"])
        for key, label, glyph in NAV:
            btn = ctk.CTkButton(
                nav,
                text=f"  {glyph}   {label}",
                anchor="w",
                font=TYPE["body"],
                height=40,
                corner_radius=RADIUS["md"],
                fg_color="transparent",
                hover_color=pal["surface_hover"],
                text_color=pal["text_muted"],
                command=lambda k=key: self.show_page(k),
            )
            btn.pack(fill="x", pady=2)
            self._nav_buttons[key] = btn

        spacer = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

        footer = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        footer.pack(fill="x", padx=SPACE["lg"], pady=SPACE["lg"])

        self._status_dot = ctk.CTkLabel(
            footer, text="●", font=(TYPE["body"][0], 13), text_color=pal["success"]
        )
        self._status_dot.pack(side="left", padx=(0, SPACE["sm"]))
        self._status_text = ctk.CTkLabel(
            footer, text="Protection Active", font=TYPE["small"], text_color=pal["text"]
        )
        self._status_text.pack(side="left")

        ctk.CTkButton(
            footer, text="About", font=TYPE["caption"], height=26, anchor="w",
            fg_color="transparent", hover_color=pal["surface_hover"],
            text_color=pal["text_faint"], command=lambda: self.show_page("about"),
        ).pack(fill="x", pady=(SPACE["sm"], 0))

    # ------------------------------------------------------------------ #
    # Navigation
    # ------------------------------------------------------------------ #
    def show_page(self, key: str) -> None:
        self._current = key
        pal = self.pal
        for k, btn in self._nav_buttons.items():
            if k == key:
                btn.configure(fg_color=pal["surface_active"], text_color=pal["text"])
            else:
                btn.configure(fg_color="transparent", text_color=pal["text_muted"])

        for child in self._content.winfo_children():
            child.destroy()

        builder = {
            "home": screens.build_home,
            "applications": screens.build_applications,
            "groups": screens.build_groups,
            "activity": screens.build_activity,
            "settings": screens.build_settings,
            "about": screens.build_about,
        }.get(key, screens.build_home)

        page = builder(self._content, self.controller, self)
        page.pack(fill="both", expand=True)

    def refresh_pages(self) -> None:
        self.show_page(self._current)

    def refresh_status(self) -> None:
        status = self.controller.protection_status()
        pal = self.pal
        if status == "active":
            self._status_dot.configure(text_color=pal["success"])
            self._status_text.configure(text="Protection Active")
        elif status == "paused":
            remaining = self.controller.pause.remaining()
            label = "Protection Paused"
            if remaining > 0:
                mm, ss = divmod(remaining, 60)
                label = f"Paused · {mm:02d}:{ss:02d}"
            self._status_dot.configure(text_color=pal["warning"])
            self._status_text.configure(text=label)
        else:
            self._status_dot.configure(text_color=pal["danger"])
            self._status_text.configure(text="Monitoring Problem")

    # ------------------------------------------------------------------ #
    # Feedback
    # ------------------------------------------------------------------ #
    def toast(self, message: str, kind: str = "info") -> None:
        if self._toast_widget is not None:
            try:
                self._toast_widget.destroy()
            except Exception:  # noqa: BLE001
                pass
        widget = Toast(self.root, self.pal, message, kind)
        widget.place(relx=1.0, rely=1.0, anchor="se", x=-24, y=-24)
        self._toast_widget = widget
        self.root.after(3200, lambda: self._dismiss_toast(widget))

    def _dismiss_toast(self, widget) -> None:
        try:
            widget.destroy()
        except Exception:  # noqa: BLE001
            pass
        if self._toast_widget is widget:
            self._toast_widget = None

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def _tick(self) -> None:
        try:
            self.controller.tick()
            self.refresh_status()
        except Exception:  # noqa: BLE001
            pass
        self.root.after(1000, self._tick)

    def _on_close(self) -> None:
        self.root.withdraw()
        if self.on_quit:
            self.on_quit("hide")

    def quit_app(self) -> None:
        if self.on_quit:
            self.on_quit("quit")