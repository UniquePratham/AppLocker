"""Lock screen — the authentication surface shown when a protected
application is launched.

Designed as a first-class product surface: app icon, app name, the reason the
app is locked, a revealable password field, quick temporary unlock, and
brute-force feedback. Stays on top and modal while the app is blocked.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional

from applocker.core.app import AppController
from applocker.core.policy import PolicyEvaluator
from applocker.ui.theme import Palette
from applocker.ui.widgets import Badge, Card


class LockScreen:
    """Modal lock/intercept screen for a protected application."""

    def __init__(self, root: tk.Misc, controller: AppController, pal: Palette,
                 app: dict, icon_photo=None):
        self.controller = controller
        self.pal = pal
        self.app = app
        self.icon_photo = icon_photo
        self.result: Optional[str] = None  # "unlock" | "temp" | "denied"
        self.win = tk.Toplevel(root)
        self.win.title(f"{app['name']} is protected")
        self.win.configure(bg=pal.bg)
        self.win.overrideredirect(False)
        self.win.attributes("-topmost", True)
        # Center on screen.
        w, h = 440, 460
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        self.win.geometry(f"{w}x{h}+{max(0, (sw-w)//2)}+{max(0, (sh-h)//3)}")
        self.win.grab_set()
        self.win.protocol("WM_DELETE_WINDOW", self._deny)

        self._build()
        self.error = tk.Label(self.win, text="", bg=pal.bg, fg=pal.danger,
                              font=("Segoe UI", 9))
        self.error.pack(pady=(2, 0))

        foot = ttk.Frame(self.win, style="TFrame")
        foot.pack(side="bottom", fill="x", pady=(4, 14))
        ttk.Label(foot, text="AppLocker — application access control",
                  style="Faint.TLabel").pack()
        self.password_entry.focus_set()

    def _build(self) -> None:
        pal = self.pal
        outer = ttk.Frame(self.win, style="TFrame")
        outer.pack(fill="both", expand=True, padx=26, pady=26)

        card = Card(outer, pal, radius=16, height=340)
        card.pack(fill="both", expand=True)
        inner = card.body()

        icon_holder = tk.Label(inner, bg=pal.surface)
        icon_holder.pack(pady=(8, 0))
        if self.icon_photo:
            icon_holder.configure(image=self.icon_photo)
            icon_holder.image = self.icon_photo

        ttk.Label(inner, text=self.app.get("name", "Application"), style="TLabel",
                  font=("Segoe UI Semibold", 16)).pack(pady=(8, 2))
        ttk.Label(inner, text="is protected", style="Faint.TLabel").pack()
        reason = self._reason_text()
        ttk.Label(inner, text=reason, style="Muted.TLabel", wraplength=330,
                  justify="center").pack(pady=(8, 0))
        hint = ("Unlocks with a custom password for this app"
                if self.controller.secrets.app_verifier(self.app["id"])
                else "Unlocks with your master password")
        ttk.Label(inner, text=hint, style="Info.TLabel").pack(pady=(4, 0))

        # Password area
        row = ttk.Frame(inner, style="Card.TFrame")
        row.pack(fill="x", padx=18, pady=(14, 0))
        self.password_entry = tk.Entry(row, show="●", font=("Segoe UI", 12),
                                       bg=pal.input_bg, fg=pal.text,
                                       insertbackground=pal.text, relief="solid", bd=1,
                                       highlightthickness=1, highlightbackground=pal.border,
                                       highlightcolor=pal.accent)
        self.password_entry.pack(side="left", fill="x", expand=True, ipady=6)
        self._show = False
        reveal = tk.Button(row, text="👁", command=self._toggle_reveal, bg=pal.surface_alt,
                           fg=pal.text, activebackground=pal.border, relief="flat",
                           font=("Segoe UI", 11), padx=10, cursor="hand2")
        reveal.pack(side="right", padx=(4, 0), ipady=3)
        self.password_entry.bind("<Return>", lambda _e: self._submit_password())

        # Actions
        btns = ttk.Frame(inner, style="Card.TFrame")
        btns.pack(fill="x", padx=18, pady=(12, 0))
        ttk.Button(btns, text="Unlock", style="TButton",
                   command=self._submit_password).pack(fill="x", ipady=2)

        temp_row = ttk.Frame(inner, style="Card.TFrame")
        temp_row.pack(fill="x", padx=18, pady=(10, 0))
        default_temp = self.controller.get_setting("temp_unlock_default", 15)
        ttk.Button(temp_row, text=f"Temporarily unlock for {default_temp} minutes",
                   style="Ghost.TButton", command=self._submit_temp).pack(fill="x")

        deny = ttk.Button(inner, text="Keep locked", style="Ghost.TButton",
                          command=self._deny)
        deny.pack(pady=(8, 0))

        # Remaining-time notice for temp unlocks already granted
        t = self.app.get("temp_unlock") or 0
        self._temp_notice = ttk.Label(inner, text="", style="Info.TLabel")
        if t and t > self._now():
            from datetime import datetime
            mins = int((t - self._now()) / 60)
            self._temp_notice.configure(text=f"Temporary unlock active · {mins} min remaining")
        self._temp_notice.pack(pady=(6, 0))

    @staticmethod
    def _now() -> float:
        import time
        return time.time()

    def _reason_text(self) -> str:
        kind = self.app.get("policy", "none")
        if kind == "always":
            return "This application requires authentication every time it is launched."
        if kind == "time" or kind == "schedule":
            return "This application is locked because it is outside its allowed time window."
        return "This application requires authentication."

    def _toggle_reveal(self) -> None:
        self._show = not self._show
        self.password_entry.configure(show="" if self._show else "●")

    def _submit_password(self) -> None:
        app_id = self.app["id"]
        remaining = self.controller.lock_guard.remaining_lockout()
        if remaining > 0:
            self.error.configure(text=f"Too many attempts. Try again in {int(remaining)}s.")
            return
        pw = self.password_entry.get()
        if self.controller.verify_app_password(app_id, pw):
            self.controller.session.login()
            self.result = "unlock"
            self.controller.grant_launch(self.app)
            self.win.destroy()
        else:
            remaining = self.controller.lock_guard.remaining_lockout()
            if remaining > 0:
                self.error.configure(text=f"Incorrect. Locked for {int(remaining)}s.")
            else:
                self.error.configure(text="Incorrect password. Access denied.")
            self.password_entry.delete(0, "end")

    def _submit_temp(self) -> None:
        """Grant a temporary unlock after verifying the app's password (or master)."""
        app_id = self.app["id"]
        remaining = self.controller.lock_guard.remaining_lockout()
        if remaining > 0:
            self.error.configure(text=f"Too many attempts. Try again in {int(remaining)}s.")
            return
        if not self.controller.verify_app_password(app_id, self.password_entry.get()):
            remaining = self.controller.lock_guard.remaining_lockout()
            if remaining > 0:
                self.error.configure(text=f"Incorrect. Locked for {int(remaining)}s.")
            else:
                self.error.configure(text="Incorrect password.")
            self.password_entry.delete(0, "end")
            return
        default_temp = self.controller.get_setting("temp_unlock_default", 15)
        self.controller.set_temp_unlock(self.app["id"], default_temp)
        self.controller.session.login()
        self.result = "temp"
        self.controller.grant_launch(self.app)
        self.win.destroy()

    def _deny(self) -> None:
        self.result = "denied"
        self.win.destroy()

    def show(self) -> Optional[str]:
        self.win.wait_window()
        return self.result