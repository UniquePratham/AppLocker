"""Lock screen and master authentication (CustomTkinter).

The lock screen is the moment the product is judged: it must be calm, clear
and impossible to mistake for a generic password popup.
"""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from applocker.core.app import AppController
from applocker.ui.components import PrimaryButton, SecondaryButton
from applocker.ui.tokens import RADIUS, SPACE, TYPE


class MasterAuthDialog:
    """Gate for opening the dashboard. Includes recovery and lockout feedback."""

    def __init__(self, root: ctk.CTk, controller: AppController, pal: dict,
                 title: str = "Unlock Aegis",
                 prompt: str = "Enter your master password to continue."):
        self.root = root
        self.controller = controller
        self.pal = pal
        self.result = False

        self.win = ctk.CTkToplevel(root)
        self.win.title(title)
        self.win.update_idletasks()
        _sw, _sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        self.win.geometry(f"420x330+{(_sw - 420) // 2}+{(_sh - 330) // 2}")
        self.win.configure(fg_color=pal["bg"])
        self.win.resizable(False, False)
        self.win.transient(root)
        self.win.grab_set()

        ctk.CTkLabel(
            self.win, text="Aegis", font=TYPE["title"], text_color=pal["accent"]
        ).pack(pady=(SPACE["2xl"], SPACE["xs"]))
        ctk.CTkLabel(
            self.win, text=prompt, font=TYPE["small"], text_color=pal["text_muted"],
            wraplength=340, justify="center"
        ).pack(pady=(0, SPACE["lg"]))

        self.entry = ctk.CTkEntry(
            self.win, show="●", font=TYPE["body"], fg_color=pal["bg_alt"],
            border_color=pal["border"], text_color=pal["text"], height=40,
        )
        self.entry.pack(fill="x", padx=SPACE["2xl"])
        self.entry.focus_set()
        self.entry.bind("<Return>", lambda _e: self._submit())

        self.error = ctk.CTkLabel(
            self.win, text="", font=TYPE["caption"], text_color=pal["danger"]
        )
        self.error.pack(pady=(SPACE["sm"], 0))

        PrimaryButton(self.win, pal, "Unlock", command=self._submit).pack(
            fill="x", padx=SPACE["2xl"], pady=(SPACE["sm"], SPACE["sm"])
        )
        SecondaryButton(
            self.win, pal, "Forgot password? Use recovery key",
            command=self._recovery,
        ).pack(fill="x", padx=SPACE["2xl"])

        self.win.deiconify()
        self.win.attributes("-alpha", 1.0)
        self.win.lift()
        self.win.attributes("-topmost", True)
        self.win.after(200, lambda: self.win.attributes("-topmost", False))
        self.win.focus_force()
        from applocker.util.brand import set_window_icon
        set_window_icon(self.win)

    def _submit(self) -> None:
        if self.controller.try_master(self.entry.get()):
            self.result = True
            self.win.destroy()
        else:
            self.error.configure(text="Incorrect password")
            self.entry.delete(0, "end")

    def _recovery(self) -> None:
        self.win.destroy()
        RecoveryDialog(self.root, self.controller, self.pal, self)

    def show(self) -> bool:
        self.win.wait_window()
        return self.result


class RecoveryDialog:
    """Reset the master password with the recovery key."""

    def __init__(self, root, controller: AppController, pal: dict, parent=None):
        self.controller = controller
        self.pal = pal
        self.parent = parent
        self.result = False

        self.win = ctk.CTkToplevel(root)
        self.win.title("Recover Access")
        self.win.update_idletasks()
        _sw, _sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        self.win.geometry(f"460x420+{(_sw - 460) // 2}+{(_sh - 420) // 2}")
        self.win.configure(fg_color=pal["bg"])
        self.win.transient(root)
        self.win.grab_set()

        ctk.CTkLabel(
            self.win, text="Recover Access", font=TYPE["title"], text_color=pal["text"]
        ).pack(pady=(SPACE["2xl"], SPACE["xs"]))
        ctk.CTkLabel(
            self.win, text="Enter your recovery key and choose a new master password.",
            font=TYPE["small"], text_color=pal["text_muted"], wraplength=380,
            justify="center"
        ).pack(pady=(0, SPACE["lg"]))

        self.key = ctk.CTkEntry(
            self.win, placeholder_text="Recovery key", font=TYPE["mono"],
            fg_color=pal["bg_alt"], border_color=pal["border"],
            text_color=pal["text"], height=40,
        )
        self.key.pack(fill="x", padx=SPACE["2xl"], pady=(0, SPACE["sm"]))

        self.new = ctk.CTkEntry(
            self.win, placeholder_text="New master password", show="●",
            font=TYPE["body"], fg_color=pal["bg_alt"], border_color=pal["border"],
            text_color=pal["text"], height=40,
        )
        self.new.pack(fill="x", padx=SPACE["2xl"], pady=(0, SPACE["sm"]))

        self.confirm = ctk.CTkEntry(
            self.win, placeholder_text="Confirm new password", show="●",
            font=TYPE["body"], fg_color=pal["bg_alt"], border_color=pal["border"],
            text_color=pal["text"], height=40,
        )
        self.confirm.pack(fill="x", padx=SPACE["2xl"])
        self.key.focus_set()

        self.error = ctk.CTkLabel(
            self.win, text="", font=TYPE["caption"], text_color=pal["danger"]
        )
        self.error.pack(pady=(SPACE["sm"], 0))

        PrimaryButton(self.win, pal, "Reset password", command=self._submit).pack(
            fill="x", padx=SPACE["2xl"], pady=SPACE["md"]
        )

        self.win.deiconify()
        self.win.attributes("-alpha", 1.0)
        self.win.lift()
        self.win.attributes("-topmost", True)
        self.win.after(200, lambda: self.win.attributes("-topmost", False))
        self.win.focus_force()
        from applocker.util.brand import set_window_icon
        set_window_icon(self.win)

    def _submit(self) -> None:
        if self.new.get() != self.confirm.get():
            self.error.configure(text="New passwords do not match")
            return
        if len(self.new.get()) < 8:
            self.error.configure(text="Use at least 8 characters")
            return
        if self.controller.reset_master_with_recovery(self.key.get(), self.new.get()):
            self.result = True
            self.win.destroy()
        else:
            self.error.configure(text="That recovery key is not valid")


class LockScreen:
    """Shown when a protected application is launched."""

    def __init__(self, root: ctk.CTk, controller: AppController, pal: dict,
                 app: dict, icon=None):
        self.root = root
        self.controller = controller
        self.pal = pal
        self.app = app
        self.icon = icon
        self.attempts = 0

        self.win = ctk.CTkToplevel(root)
        self.win.title("Protected application")
        self.win.update_idletasks()
        _sw, _sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        self.win.geometry(f"460x560+{(_sw - 460) // 2}+{(_sh - 560) // 2}")
        self.win.configure(fg_color=pal["bg"])
        self.win.resizable(False, False)
        self.win.attributes("-topmost", True)
        self.win.protocol("WM_DELETE_WINDOW", self._deny)

        self._build()

        self.win.deiconify()
        self.win.attributes("-alpha", 1.0)
        self.win.lift()
        self.win.focus_force()
        from applocker.util.brand import set_window_icon
        set_window_icon(self.win)

    def _build(self) -> None:
        pal = self.pal

        ctk.CTkLabel(self.win, text="", height=SPACE["xl"]).pack()

        if self.icon is not None:
            ctk.CTkLabel(self.win, text="", image=self.icon).pack(pady=(0, SPACE["md"]))
        else:
            ctk.CTkLabel(
                self.win, text="▣", font=(TYPE["body"][0], 44), text_color=pal["text_faint"]
            ).pack(pady=(0, SPACE["md"]))

        ctk.CTkLabel(
            self.win, text=self.app.get("name", "Application"), font=TYPE["title"],
            text_color=pal["text"]
        ).pack()
        ctk.CTkLabel(
            self.win, text="This application is protected.", font=TYPE["body"],
            text_color=pal["text_muted"]
        ).pack(pady=(SPACE["xs"], SPACE["xl"]))

        self.entry = ctk.CTkEntry(
            self.win, placeholder_text="Password", show="●", font=TYPE["body"],
            fg_color=pal["bg_alt"], border_color=pal["border"],
            text_color=pal["text"], height=44,
        )
        self.entry.pack(fill="x", padx=SPACE["2xl"])
        self.entry.focus_set()
        self.entry.bind("<Return>", lambda _e: self._unlock())

        self.error = ctk.CTkLabel(
            self.win, text="", font=TYPE["caption"], text_color=pal["danger"]
        )
        self.error.pack(pady=(SPACE["sm"], 0))

        PrimaryButton(self.win, pal, "Unlock", command=self._unlock).pack(
            fill="x", padx=SPACE["2xl"], pady=(SPACE["sm"], SPACE["md"])
        )

        ctk.CTkLabel(
            self.win, text="Unlock temporarily", font=TYPE["small"],
            text_color=pal["text_muted"]
        ).pack(pady=(SPACE["sm"], SPACE["xs"]))

        temp = ctk.CTkFrame(self.win, fg_color="transparent")
        temp.pack()
        for label, minutes in [("5 min", 5), ("15 min", 15), ("30 min", 30)]:
            SecondaryButton(
                temp, pal, label, width=90,
                command=lambda m=minutes: self._temp_unlock(m),
            ).pack(side="left", padx=SPACE["xs"])

        self.attempts_label = ctk.CTkLabel(
            self.win, text="", font=TYPE["caption"], text_color=pal["text_faint"]
        )
        self.attempts_label.pack(pady=(SPACE["lg"], 0))

    def _unlock(self) -> None:
        password = self.entry.get()
        if self.controller.verify_master_for_lockscreen(password):
            self.controller.grant_launch(self.app)
            self.win.destroy()
            return

        self.attempts += 1
        remaining = max(0, 5 - self.attempts)
        self.error.configure(text="Incorrect password")
        self.entry.delete(0, "end")
        if remaining:
            self.attempts_label.configure(text=f"{remaining} attempts remaining")
        else:
            self.attempts_label.configure(text="Too many attempts — try again later")

    def _temp_unlock(self, minutes: int) -> None:
        self.controller.set_temp_unlock(self.app["id"], minutes)
        self.controller.grant_launch(self.app)
        self.win.destroy()

    def _deny(self) -> None:
        self.win.destroy()

    def show(self) -> None:
        self.win.wait_window()
