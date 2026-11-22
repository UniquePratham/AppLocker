"""First-run setup wizard (CustomTkinter).

Six steps: welcome, master password, recovery key, startup preference,
first application, done. The user cannot continue past the password step
without a valid, confirmed password.
"""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from applocker.core.app import AppController
from applocker.ui.components import PrimaryButton, SecondaryButton
from applocker.ui.tokens import RADIUS, SPACE, TYPE


class SetupWizard:
    STEPS = ["Welcome", "Password", "Recovery", "Startup", "First app", "Done"]

    def __init__(self, root: ctk.CTk, controller: AppController, pal: dict):
        self.root = root
        self.controller = controller
        self.pal = pal
        self.step = 0
        self.password = ""
        self.recovery = ""

        self.win = ctk.CTkToplevel(root)
        self.win.title("Welcome to Aegis")
        # Position explicitly: the host root is parked off-screen, and a
        # Toplevel with no position inherits that offset.
        self.win.update_idletasks()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        w, h = 720, 620
        self.win.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
        self.win.configure(fg_color=pal["bg"])
        self.win.resizable(False, False)
        self.win.protocol("WM_DELETE_WINDOW", self._cancel)
        self.win.grab_set()

        self._build()
        self._render()

        from applocker.util.brand import set_window_icon

        set_window_icon(self.win)

        # The host root is withdrawn, so the wizard must raise itself once the
        # event loop is running. Doing it inline is too early: the window
        # exists but Windows has not mapped it yet.
        def _raise(attempt: int = 0) -> None:
            try:
                self.win.deiconify()
                self.win.attributes("-alpha", 1.0)
                self.win.lift()
                self.win.attributes("-topmost", True)
                self.win.focus_force()
                self.win.update_idletasks()
                if self.win.winfo_viewable():
                    self.win.after(250, lambda: self.win.attributes("-topmost", False))
                    return
            except Exception:  # noqa: BLE001
                pass
            # Frozen builds can map the window a beat later; retry briefly.
            if attempt < 20:
                self.win.after(50, lambda: _raise(attempt + 1))

        # Call directly: a deferred callback never runs before wait_window()
        # blocks in a frozen build.
        _raise()

    # ------------------------------------------------------------------ #
    def _build(self) -> None:
        pal = self.pal

        self._progress = ctk.CTkFrame(self.win, fg_color="transparent")
        self._progress.pack(fill="x", padx=SPACE["2xl"], pady=(SPACE["xl"], SPACE["md"]))

        self._body = ctk.CTkFrame(self.win, fg_color="transparent")
        self._body.pack(fill="both", expand=True, padx=SPACE["2xl"])

        self._footer = ctk.CTkFrame(self.win, fg_color="transparent")
        self._footer.pack(fill="x", padx=SPACE["2xl"], pady=SPACE["xl"])

        self._back = SecondaryButton(self._footer, pal, "Back", command=self._prev, width=100)
        self._back.pack(side="left")

        self._next = PrimaryButton(self._footer, pal, "Continue", command=self._next, width=140)
        self._next.pack(side="right")

    def _render_progress(self) -> None:
        for child in self._progress.winfo_children():
            child.destroy()
        pal = self.pal
        for i, name in enumerate(self.STEPS):
            active = i <= self.step
            ctk.CTkLabel(
                self._progress,
                text=f"{i + 1}",
                width=24, height=24,
                corner_radius=12,
                fg_color=pal["accent"] if active else pal["surface"],
                text_color=pal["accent_text"] if active else pal["text_faint"],
                font=TYPE["caption"],
            ).pack(side="left", padx=(0, SPACE["xs"]))
            if i < len(self.STEPS) - 1:
                ctk.CTkFrame(
                    self._progress, width=28, height=2,
                    fg_color=pal["accent"] if i < self.step else pal["border"],
                ).pack(side="left", padx=(0, SPACE["xs"]))

    def _render(self) -> None:
        self._render_progress()
        for child in self._body.winfo_children():
            child.destroy()
        pal = self.pal

        self._back.configure(state="normal" if self.step > 0 else "disabled")

        if self.step == 0:
            self._step_welcome(pal)
        elif self.step == 1:
            self._step_password(pal)
        elif self.step == 2:
            self._step_recovery(pal)
        elif self.step == 3:
            self._step_startup(pal)
        elif self.step == 4:
            self._step_first_app(pal)
        else:
            self._step_done(pal)

    # ------------------------------------------------------------------ #
    def _title(self, pal, text: str, sub: str = "") -> None:
        ctk.CTkLabel(
            self._body, text=text, font=TYPE["display"], text_color=pal["text"], anchor="w"
        ).pack(fill="x", pady=(SPACE["lg"], SPACE["xs"]))
        if sub:
            ctk.CTkLabel(
                self._body, text=sub, font=TYPE["body"], text_color=pal["text_muted"],
                anchor="w", wraplength=560, justify="left"
            ).pack(fill="x", pady=(0, SPACE["lg"]))

    def _step_welcome(self, pal) -> None:
        self._title(
            pal, "Welcome to Aegis",
            "Aegis password-protects the applications you choose. When a "
            "locked app launches, it is closed and a lock screen appears — the "
            "app runs again only after you enter the correct password.",
        )
        for line in [
            "Your master password is never stored in plain text.",
            "A recovery key lets you reset a forgotten password.",
            "Protection keeps running when the window is closed.",
        ]:
            ctk.CTkLabel(
                self._body, text=f"•   {line}", font=TYPE["body"],
                text_color=pal["text_muted"], anchor="w"
            ).pack(fill="x", pady=2)

    def _step_password(self, pal) -> None:
        self._title(pal, "Create your master password",
                    "Use at least 8 characters. This password unlocks Aegis "
                    "and authorises every protected action.")
        self._pw1 = ctk.CTkEntry(
            self._body, placeholder_text="Master password", show="●",
            font=TYPE["body"], fg_color=pal["bg_alt"], border_color=pal["border"],
            text_color=pal["text"], height=40,
        )
        self._pw1.pack(fill="x", pady=(0, SPACE["sm"]))
        self._pw2 = ctk.CTkEntry(
            self._body, placeholder_text="Confirm password", show="●",
            font=TYPE["body"], fg_color=pal["bg_alt"], border_color=pal["border"],
            text_color=pal["text"], height=40,
        )
        self._pw2.pack(fill="x")
        self._pw1.focus_set()

    def _step_recovery(self, pal) -> None:
        self._title(pal, "Save your recovery key",
                    "This key resets a forgotten master password. Store it "
                    "somewhere safe — it will not be shown again.")
        box = ctk.CTkEntry(
            self._body, font=TYPE["mono"], fg_color=pal["bg_alt"],
            border_color=pal["border"], text_color=pal["text"], height=44,
            justify="center",
        )
        box.pack(fill="x", pady=(0, SPACE["md"]))
        box.insert(0, self.recovery)
        box.configure(state="readonly")

        def copy() -> None:
            self.win.clipboard_clear()
            self.win.clipboard_append(self.recovery)

        def save_file() -> None:
            from tkinter import filedialog

            path = filedialog.asksaveasfilename(
                parent=self.win,
                title="Save recovery key",
                defaultextension=".txt",
                initialfile="aegis-recovery-key.txt",
                filetypes=[("Text file", "*.txt"), ("All files", "*.*")],
            )
            if not path:
                return
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write("Aegis recovery key\\n")
                    fh.write("=" * 40 + "\\n\\n")
                    fh.write(self.recovery + "\\n\\n")
                    fh.write(
                        "Keep this file somewhere safe. It resets a forgotten\\n"
                        "master password. Anyone with this key can reset your\\n"
                        "password, so do not store it on this computer.\\n"
                    )
                self._saved_label.configure(
                    text=f"Saved to {path}", text_color=self.pal["success"]
                )
            except Exception as exc:  # noqa: BLE001
                self._saved_label.configure(
                    text=f"Could not save: {exc}", text_color=self.pal["danger"]
                )

        buttons = ctk.CTkFrame(self._body, fg_color="transparent")
        buttons.pack(fill="x")
        PrimaryButton(buttons, pal, "Save as .txt file", command=save_file).pack(
            side="left", padx=(0, SPACE["sm"])
        )
        SecondaryButton(buttons, pal, "Copy to clipboard", command=copy).pack(side="left")

        self._saved_label = ctk.CTkLabel(
            self._body, text="", font=TYPE["caption"], text_color=pal["text_faint"],
            anchor="w", wraplength=560, justify="left"
        )
        self._saved_label.pack(fill="x", pady=(SPACE["md"], 0))

    def _step_startup(self, pal) -> None:
        self._title(pal, "Startup preferences",
                    "Aegis can start with Windows so protection is never off.")
        self._startup_var = tk.BooleanVar(
            value=bool(self.controller.get_setting("run_at_login", True))
        )
        ctk.CTkCheckBox(
            self._body, text="Start Aegis when I sign in",
            variable=self._startup_var, font=TYPE["body"],
            text_color=pal["text"], fg_color=pal["accent"],
            hover_color=pal["accent_hover"], border_color=pal["border"],
        ).pack(anchor="w", pady=SPACE["sm"])

    def _step_first_app(self, pal) -> None:
        self._title(pal, "Protect your first application",
                    "Optional — you can add applications later from the dashboard.")
        self._first_path = tk.StringVar(value="")
        row = ctk.CTkFrame(self._body, fg_color="transparent")
        row.pack(fill="x")
        ctk.CTkEntry(
            row, textvariable=self._first_path, font=TYPE["small"],
            fg_color=pal["bg_alt"], border_color=pal["border"],
            text_color=pal["text"], height=38,
        ).pack(side="left", fill="x", expand=True, padx=(0, SPACE["sm"]))

        def browse() -> None:
            from tkinter import filedialog

            path = filedialog.askopenfilename(
                title="Select an application",
                filetypes=[("Executables", "*.exe"), ("All files", "*.*")],
            )
            if path:
                self._first_path.set(path)

        SecondaryButton(row, pal, "Browse…", command=browse, width=90).pack(side="right")

    def _step_done(self, pal) -> None:
        self._title(pal, "You're protected",
                    "Aegis is running. Close this window and it will keep "
                    "protecting your applications from the system tray.")
        self._next.configure(text="Finish")

    # ------------------------------------------------------------------ #
    def _next(self) -> None:
        pal = self.pal

        if self.step == 1:
            pw1, pw2 = self._pw1.get(), self._pw2.get()
            if len(pw1) < 8:
                self._error("Use at least 8 characters.")
                return
            if pw1 != pw2:
                self._error("Passwords do not match.")
                return
            self.password = pw1
            self.recovery = self.controller.setup_master(pw1)

        elif self.step == 3:
            self.controller.set_setting("run_at_login", bool(self._startup_var.get()))

        elif self.step == 4:
            path = self._first_path.get().strip()
            if path:
                import os

                if os.path.isfile(path):
                    name = os.path.splitext(os.path.basename(path))[0]
                    self.controller.add_app(name=name, path=path, policy="always")

        if self.step >= len(self.STEPS) - 1:
            self.win.destroy()
            return

        self.step += 1
        self._render()

    def _prev(self) -> None:
        if self.step > 0:
            self.step -= 1
            self._render()

    def _error(self, message: str) -> None:
        ctk.CTkLabel(
            self._body, text=message, font=TYPE["caption"], text_color=self.pal["danger"]
        ).pack(fill="x", pady=(SPACE["sm"], 0))

    def _cancel(self) -> None:
        self.win.destroy()

    def show(self) -> None:
        # Pump the event loop once so the deferred raise actually runs before
        # wait_window() blocks. Without this the window stays unmapped in a
        # frozen (console=False) build.
        self.win.update()
        try:
            self.win.wait_visibility(self.win)
        except Exception:  # noqa: BLE001
            pass
        try:
            self.win.wait_window()
        except Exception:  # noqa: BLE001
            # The window can be destroyed before the wait begins.
            pass
