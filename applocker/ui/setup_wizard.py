"""First-run setup wizard (onboarding).

Flow:
1. Welcome
2. Create master password
3. Recovery configuration (key revealed + confirm-stored)
4. Startup behavior
5. Add first protected application
6. Security complete

On completion the wizard returns the generated recovery key and whether the
user chose to enable startup, plus the first added application.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from applocker.core.app import AppController
from applocker.core.discovery import DiscoveredApp
from applocker.ui import dialogs
from applocker.ui.theme import Palette
from applocker.util.winutil import set_startup_enabled


class SetupWizard:
    STEPS = ["Welcome", "Master Password", "Recovery", "Startup", "First Application", "Done"]

    def __init__(self, root: tk.Misc, controller: AppController, pal: Palette):
        self.controller = controller
        self.pal = pal
        self.step = 0
        self.recovery_key: Optional[str] = None
        self.startup_enabled = False
        self.first_app = None
        # Values persist across steps so Back/Next never loses typed input.
        self.master_pw_var = tk.StringVar()
        self.master_pw2_var = tk.StringVar()
        self.recovery_var = tk.BooleanVar(value=False)
        self.startup_var = tk.BooleanVar(value=True)

        self.win = tk.Toplevel(root)
        self.win.title("Welcome to AppLocker")
        self.win.configure(bg=pal.bg)
        from applocker.ui.dialogs import center_window
        center_window(self.win, 560, 520)
        if root.winfo_viewable():
            try:
                self.win.transient(root)
            except tk.TclError:
                pass
        self.win.grab_set()
        self.win.resizable(False, False)
        self.win.protocol("WM_DELETE_WINDOW", self._cancel)

        self._build_chrome()
        self._render()

    def _build_chrome(self) -> None:
        pal = self.pal
        header = tk.Frame(self.win, bg=pal.surface_alt)
        header.pack(fill="x")
        ttk.Label(header, text="AppLocker", style="TLabel",
                  font=("Segoe UI Semibold", 15), background=pal.surface_alt).pack(
            anchor="w", padx=24, pady=14)
        self.progress = ttk.Progressbar(self.win, maximum=len(self.STEPS) - 1, value=0)
        self.progress.pack(fill="x")
        self.body = tk.Frame(self.win, bg=pal.bg)
        self.body.pack(fill="both", expand=True, padx=28, pady=18)
        footer = ttk.Frame(self.win, style="TFrame")
        footer.pack(fill="x", padx=24, pady=12)
        self.prev_btn = ttk.Button(footer, text="Back", style="Secondary.TButton",
                                   command=self._back)
        self.prev_btn.pack(side="left")
        self.next_btn = ttk.Button(footer, text="Next →", style="TButton", command=self._next)
        self.next_btn.pack(side="right")
        self._step_label = ttk.Label(footer, text="", style="Faint.TLabel")
        self._step_label.pack(side="right", padx=(0, 12))

    def _render(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()
        pal = self.pal
        step = self.STEPS[self.step]
        self.progress.configure(value=self.step)
        self._step_label.configure(text=f"Step {self.step + 1} of {len(self.STEPS)}")
        self.prev_btn.state(["!disabled"] if self.step > 0 else ["disabled"])
        if self.step == len(self.STEPS) - 1:
            self.next_btn.configure(text="Finish")

        if self.step == 0:
            self._render_welcome()
        elif self.step == 1:
            self._render_master()
        elif self.step == 2:
            self._render_recovery()
        elif self.step == 3:
            self._render_startup()
        elif self.step == 4:
            self._render_first_app()
        elif self.step == 5:
            self._render_done()

    def _render_welcome(self) -> None:
        pal = self.pal
        ttk.Label(self.body, text="Welcome to AppLocker", style="PageTitle.TLabel").pack(
            anchor="w", pady=(6, 6))
        ttk.Label(self.body, text=(
            "AppLocker password-protects the applications you choose.\n\n"
            "• Lock apps behind a master password (or per-app passwords)\n"
            "• Block apps on a schedule — like a time window for Games\n"
            "• Unlock a single app for 15 minutes without disabling protection\n"
            "• Runs quietly in the system tray\n\n"
            "This short wizard takes under a minute."), style="TLabel",
            justify="left").pack(anchor="w")

    def _render_master(self) -> None:
        pal = self.pal
        ttk.Label(self.body, text="Create your master password", style="PageTitle.TLabel").pack(
            anchor="w", pady=(6, 4))
        ttk.Label(self.body, text=(
            "The master password unlocks the AppLocker dashboard and can unlock\n"
            "protected apps. It is hashed with a memory-hard KDF and never stored\n"
            "in plain text. Forget it? The recovery key on the next step saves you."),
            style="Faint.TLabel", justify="left").pack(anchor="w", pady=(0, 14))
        self.master_pw = self._field("Master password", self.master_pw_var)
        self.master_pw2 = self._field("Confirm master password", self.master_pw2_var)
        self.wizard_error = ttk.Label(self.body, text="", style="Danger.TLabel")
        self.wizard_error.pack(anchor="w", pady=(6, 0))

    def _field(self, label: str, variable: tk.StringVar) -> tk.Entry:
        pal = self.pal
        ttk.Label(self.body, text=label, style="TLabel").pack(anchor="w", pady=(6, 2))
        ent = tk.Entry(self.body, textvariable=variable, show="●", font=("Segoe UI", 11),
                       bg=pal.input_bg, fg=pal.text,
                       insertbackground=pal.text, relief="solid", bd=1, highlightthickness=1,
                       highlightbackground=pal.border, highlightcolor=pal.accent)
        ent.pack(fill="x", ipady=5)
        ent.focus_set()
        return ent

    def _render_recovery(self) -> None:
        pal = self.pal
        ttk.Label(self.body, text="Recovery key", style="PageTitle.TLabel").pack(
            anchor="w", pady=(6, 4))
        ttk.Label(self.body, text=(
            "This key can reset a forgotten master password. Write it down or\n"
            "save it to a safe place — AppLocker never stores it in plain text."),
            style="Faint.TLabel", justify="left").pack(anchor="w", pady=(0, 12))
        from applocker.core.security import generate_recovery_key
        if self.recovery_key is None:
            self.recovery_key = generate_recovery_key()
        box = tk.Label(self.body, text=self.recovery_key, font=("Cascadia Mono", 13, "bold"),
                       bg=pal.accent_soft, fg=pal.accent, padx=18, pady=12)
        box.pack(fill="x", pady=(2, 6))
        save_btn = tk.Button(self.body, text="Save recovery key to file…", command=self._save_recovery_key,
                             bg=pal.surface_alt, fg=pal.text,
                             activebackground=pal.border, activeforeground=pal.text,
                             relief="flat", font=("Segoe UI", 9), padx=12, pady=4, bd=0,
                             cursor="hand2")
        save_btn.pack(anchor="w", pady=(0, 8))
        self.recovery_saved = tk.Label(self.body, text="", bg=pal.bg, fg=pal.success,
                                       font=("Segoe UI", 9), justify="left", anchor="w",
                                       wraplength=460)
        self.recovery_saved.pack(anchor="w", pady=(0, 2))
        from applocker.ui.widgets import CheckButton
        CheckButton(self.body, "I have stored this recovery key in a safe place",
                    pal, variable=self.recovery_var).pack(anchor="w", pady=(4, 0))

    def _save_recovery_key(self) -> None:
        from datetime import date
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            parent=self.win, title="Save recovery key",
            initialfile="AppLocker Recovery Key.txt", defaultextension=".txt",
            filetypes=[("Text file", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        body = (
            "======================================================================\n"
            "  AppLocker — Master Password Recovery Key\n"
            f"  Generated: {date.today().isoformat()}\n"
            "======================================================================\n"
            "\n"
            "  This key is the only way to reset your AppLocker master password\n"
            "  if you ever forget it. Keep it private — anyone with this key can\n"
            "  reset your master password without needing the password itself.\n"
            "\n"
            f"  Recovery key: {self.recovery_key}\n"
            "\n"
            "  Do NOT share this file. Store it in a secure, private location.\n"
            "  Delete it once you have committed the key to memory.\n"
        )
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(body)
        except OSError as exc:  # noqa: BLE001
            messagebox.showerror("Could not save",
                                 f"The recovery key could not be saved:\n{exc}",
                                 parent=self.win)
            return
        self.recovery_saved.configure(text=f"Saved to {path}")

    def _render_startup(self) -> None:
        pal = self.pal
        ttk.Label(self.body, text="Start with Windows", style="PageTitle.TLabel").pack(
            anchor="w", pady=(6, 4))
        ttk.Label(self.body, text=(
            "Run AppLocker in the background when Windows starts so protected apps\n"
            "stay protected after a reboot.\n\n"
            "This is a user-level startup entry — no administrator privileges are\n"
            "requested and nothing is installed silently."),
            style="Faint.TLabel", justify="left").pack(anchor="w", pady=(0, 14))
        from applocker.ui.widgets import CheckButton
        CheckButton(self.body, "Launch AppLocker when Windows starts",
                    pal, variable=self.startup_var).pack(anchor="w", pady=(6, 0))

    def _render_first_app(self) -> None:
        pal = self.pal
        ttk.Label(self.body, text="Protect your first app", style="PageTitle.TLabel").pack(
            anchor="w", pady=(6, 4))
        ttk.Label(self.body, text=(
            "Add an application to protect right now, or skip and do it later\n"
            "from the Applications page."), style="Faint.TLabel", justify="left").pack(
            anchor="w", pady=(0, 14))
        self.first_app = None
        row = ttk.Frame(self.body, style="TFrame")
        row.pack(fill="x", pady=(4, 0))
        ttk.Button(row, text="+ Browse / Discover Apps…", style="TButton",
                   command=self._pick_app).pack(side="left")
        self._picked_label = ttk.Label(self.body, text="", style="Success.TLabel")
        self._picked_label.pack(anchor="w", pady=(8, 0))

    def _pick_app(self) -> None:
        from applocker.ui.icons import IconCache
        dlg = dialogs.AddAppDialog(self.win, self.controller, self.pal, IconCache(self.win))
        found = dlg.show()
        if found:
            self.first_app = found
            self._picked_label.configure(text=f"Will protect: {found.name}")

    def _render_done(self) -> None:
        pal = self.pal
        ttk.Label(self.body, text="You're all set", style="PageTitle.TLabel").pack(
            anchor="w", pady=(6, 6))
        ttk.Label(self.body, text=(
            "AppLocker is configured and running in the background.\n"
            "Keep an eye on the system tray for quick controls."), style="TLabel",
            justify="left").pack(anchor="w", pady=(0, 8))
        ttk.Label(self.body, text=(
            "Security reminder: AppLocker is a user-space protection utility.\n"
            "It is designed for privacy and light parental control, and is not a\n"
            "substitute for account isolation or OS-level security."),
            style="Faint.TLabel", justify="left").pack(anchor="w")

    # ------------------------------------------------------------------ #
    # Navigation
    # ------------------------------------------------------------------ #
    def _next(self) -> None:
        if self.step == 1:
            pw, pw2 = self.master_pw_var.get(), self.master_pw2_var.get()
            if len(pw) < 4:
                self.wizard_error.configure(text="Password must be at least 4 characters.")
                return
            if pw != pw2:
                self.wizard_error.configure(text="Passwords do not match.")
                return
            rec_key = self.controller.setup_master(pw)
            self.recovery_key = rec_key
        if self.step == 2:
            if not self.recovery_var.get():
                messagebox.showwarning("Recovery Key",
                                       "Please confirm you have stored the recovery key.",
                                       parent=self.win)
                return
        if self.step == 3:
            self.startup_enabled = self.startup_var.get()
        if self.step == 4 and self.first_app:
            icon_path = ""
            try:
                from applocker.util.paths import get_icon_cache_dir
                from applocker.util.winutil import IconExtractor
                icon_path = IconExtractor(get_icon_cache_dir()).get(self.first_app.path) or ""
            except Exception:  # noqa: BLE001
                icon_path = ""
            self.controller.add_app(self.first_app.name, self.first_app.path,
                                    self.first_app.publisher, self.first_app.version,
                                    policy="always", icon_cache=icon_path)
        self.step += 1
        if self.step >= len(self.STEPS):
            self._finish()
            return
        self._render()

    def _back(self) -> None:
        if self.step > 0:
            self.step -= 1
            self._render()

    def _finish(self) -> None:
        if self.startup_enabled:
            try:
                set_startup_enabled(True)
            except Exception:  # noqa: BLE001
                pass
        self.win.destroy()

    def _cancel(self) -> None:
        self.win.destroy()

    def show(self) -> None:
        self.win.wait_window()
        return None