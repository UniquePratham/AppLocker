"""Password-related dialogs: per-app password management."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from applocker.core.app import AppController
from applocker.ui.theme import Palette


class AppPasswordDialog:
    """Choose how an application unlocks.

    Two modes, usable simultaneously across all apps:

    * *Master password (shared)* — the app unlocks with the same master
      password used everywhere else. This is the universal lock.
    * *Separate password* — the app gets its own secret, independent of the
      master password. Setting one switches just this app to an individual
      lock; clearing it returns the app to the universal (master) lock.
    """

    def __init__(self, root: tk.Misc, controller: AppController, pal: Palette, app: dict):
        self.controller = controller
        self.pal = pal
        self.app = app
        self.has_custom = controller.secrets.app_verifier(app["id"]) is not None

        self.win = tk.Toplevel(root)
        self.win.title(f"Password — {app['name']}")
        self.win.configure(bg=pal.bg)
        from applocker.ui.dialogs import center_window
        center_window(self.win, 420, 360)
        if root.winfo_viewable():
            try:
                self.win.transient(root)
            except tk.TclError:
                pass
        self.win.grab_set()

        ttk.Label(self.win, text="Unlock password", style="PageTitle.TLabel").pack(
            anchor="w", padx=28, pady=(20, 4))
        ttk.Label(self.win, text=f"{app['name']}",
                  style="TLabel").pack(anchor="w", padx=28)

        ttk.Label(self.win, text=(
            "Apps without a custom password unlock with your master password.\n"
            "Set a separate one to give just this app its own secret."),
            style="Faint.TLabel", wraplength=360, justify="left").pack(anchor="w", padx=28, pady=(8, 6))

        self.mode_var = tk.StringVar(value="custom" if self.has_custom else "master")
        mode_frame = ttk.Frame(self.win, style="TFrame")
        mode_frame.pack(fill="x", padx=28)
        ttk.Radiobutton(mode_frame, text="Master password (shared with all apps)",
                        variable=self.mode_var, value="master", style="TRadiobutton",
                        command=self._sync_mode).pack(anchor="w", pady=2)
        ttk.Radiobutton(mode_frame, text="Separate password for this app",
                        variable=self.mode_var, value="custom", style="TRadiobutton",
                        command=self._sync_mode).pack(anchor="w", pady=2)

        form = ttk.Frame(self.win, style="TFrame")
        form.pack(fill="x", padx=28, pady=(6, 0))
        ttk.Label(form, text="New app password:", style="TLabel").grid(row=0, column=0, sticky="w", pady=(6, 0))
        self.pw = ttk.Entry(form, show="●", style="TEntry")
        self.pw.grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=(6, 0), ipady=3)
        ttk.Label(form, text="Confirm:", style="TLabel").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.pw2 = ttk.Entry(form, show="●", style="TEntry")
        self.pw2.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=(6, 0), ipady=3)
        form.columnconfigure(1, weight=1)

        self.error = tk.Label(self.win, text="", bg=pal.bg, fg=pal.danger, font=("Segoe UI", 9))
        self.error.pack(anchor="w", padx=28, pady=(8, 0))

        btns = ttk.Frame(self.win, style="TFrame")
        btns.pack(fill="x", padx=28, pady=(10, 18))
        ttk.Button(btns, text="Save", style="TButton", command=self._save).pack(side="right")
        ttk.Button(btns, text="Cancel", style="Secondary.TButton",
                   command=self.win.destroy).pack(side="right", padx=(0, 8))

        self._sync_mode()

    def _sync_mode(self) -> None:
        custom = self.mode_var.get() == "custom"
        state = "normal" if custom else "disabled"
        self.pw.configure(state=state)
        self.pw2.configure(state=state)
        if not custom:
            self.error.configure(text="")

    def _save(self) -> None:
        if self.mode_var.get() == "master":
            self.controller.secrets.remove_app_verifier(self.app["id"])
            self.win.destroy()
            return
        pw, pw2 = self.pw.get(), self.pw2.get()
        if len(pw) < 4:
            self.error.configure(text="Password must be at least 4 characters.")
            return
        if pw != pw2:
            self.error.configure(text="Passwords do not match.")
            return
        self.controller.set_app_password(self.app["id"], pw)
        self.win.destroy()

    def show(self) -> None:
        self.win.wait_window()