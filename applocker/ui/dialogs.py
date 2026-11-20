"""Dialogs: auth, add-application discovery, policy editor, pause, recovery.

Every dialog is built on the global ttk theme and reads the current palette
for tk-drawn widgets so it matches the active light/dark theme.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Optional

from applocker.core.app import AppController
from applocker.core.discovery import DiscoveredApp, discover_all, scan_running
from applocker.ui import icons as ui_icons
from applocker.ui.theme import Palette
from applocker.util.winutil import IconExtractor


def themed_toplevel(root: tk.Misc, pal: Palette, title: str, size: tuple[int, int],
                    modal: bool = True) -> tk.Toplevel:
    win = tk.Toplevel(root)
    win.title(title)
    win.configure(bg=pal.bg)
    center_window(win, *size)
    if root.winfo_viewable():
        try:
            win.transient(getattr(root, "root", root))
        except tk.TclError:
            pass
    if modal:
        win.grab_set()
        win.resizable(False, False)
    return win


def center_window(window: tk.Misc, width: int, height: int) -> None:
    """Size and center ``window`` on the primary screen work area."""
    try:
        window.update_idletasks()
    except tk.TclError:
        pass
    sw = window.winfo_screenwidth()
    sh = window.winfo_screenheight()
    x = max(0, (sw - width) // 2)
    y = max(0, (sh - height) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


def _label(master, text: str, pal: Palette, **kw) -> tk.Label:
    kw.setdefault("bg", pal.bg)
    kw.setdefault("fg", pal.text)
    kw.setdefault("font", ("Segoe UI", 10))
    return tk.Label(master, text=text, **kw)


# --------------------------------------------------------------------------- #
# Master password authentication
# --------------------------------------------------------------------------- #
class MasterAuthDialog:
    """Gate for opening the dashboard. Includes recovery path + lockout."""

    def __init__(self, root: tk.Misc, controller: AppController, pal: Palette,
                 title: str = "Authenticate", prompt: str = "Enter your master password to continue."):
        self.controller = controller
        self.pal = pal
        self.result = None
        self.root = root

        self.win = themed_toplevel(root, pal, title, (380, 280))
        _label(self.win, "AppLocker", pal, font=("Segoe UI Semibold", 16),
               fg=pal.accent).pack(pady=(22, 2))
        _label(self.win, prompt, pal, fg=pal.text_muted, wraplength=320,
               justify="center").pack(pady=(0, 14))

        self.entry = tk.Entry(self.win, show="●", font=("Segoe UI", 11),
                              bg=pal.input_bg, fg=pal.text, insertbackground=pal.text,
                              relief="solid", bd=1, highlightthickness=1,
                              highlightbackground=pal.border, highlightcolor=pal.accent)
        self.entry.pack(fill="x", padx=40, ipady=6)
        self.entry.bind("<Return>", lambda _e: self._submit())
        self.entry.focus_set()

        self.error = _label(self.win, "", pal, fg=pal.danger, font=("Segoe UI", 9))
        self.error.pack(pady=(6, 0))

        buttons = tk.Frame(self.win, bg=pal.bg)
        buttons.pack(fill="x", padx=40, pady=(6, 10))
        tk.Button(buttons, text="Unlock", command=self._submit, bg=pal.accent, fg="#ffffff",
                  activebackground=pal.accent_hover, activeforeground="#ffffff",
                  relief="flat", font=("Segoe UI", 10), padx=20, pady=5, bd=0).pack(side="right")
        tk.Button(buttons, text="Cancel", command=self.win.destroy, bg=pal.surface_alt,
                  fg=pal.text, activebackground=pal.border, relief="flat",
                  font=("Segoe UI", 10), padx=16, pady=5, bd=0).pack(side="right", padx=(0, 8))
        rec = tk.Button(self.win, text="Forgot password? Recover", command=self._recovery,
                        bg=pal.bg, fg=pal.accent, activebackground=pal.bg, relief="flat",
                        font=("Segoe UI", 9), cursor="hand2", bd=0, pady=2)
        rec.pack(pady=4)

    def _submit(self) -> None:
        text = self.entry.get()
        remaining = self.controller.master_guard.remaining_lockout()
        if remaining > 0:
            self.error.configure(text=f"Temporarily locked. Try again in {int(remaining)}s.")
            return
        if self.controller.try_master(text):
            self.result = True
            self.win.destroy()
        else:
            remaining = self.controller.master_guard.remaining_lockout()
            if remaining > 0:
                self.error.configure(text=f"Incorrect. Locked for {int(remaining)}s.")
            else:
                self.error.configure(text="Incorrect master password.")

    def _recovery(self) -> None:
        dd = RecoveryResetDialog(self.root, self.controller, self.pal)
        if dd.result:
            self.result = True
            self.win.destroy()

    def show(self) -> bool:
        self.win.wait_window()
        return bool(self.result)


# --------------------------------------------------------------------------- #
# Change master password
# --------------------------------------------------------------------------- #
class ChangeMasterDialog:
    def __init__(self, root: tk.Misc, controller: AppController, pal: Palette):
        self.controller = controller
        self.pal = pal
        self.win = themed_toplevel(root, pal, "Change Master Password", (400, 320))
        _label(self.win, "Change Master Password", pal, font=("Segoe UI Semibold", 14)).pack(pady=(18, 10))

        form = tk.Frame(self.win, bg=pal.bg)
        form.pack(padx=34, fill="x")
        self.old_ent = self._field(form, "Current password", 0, show="●")
        self.new_ent = self._field(form, "New password", 1, show="●")
        self.again_ent = self._field(form, "Confirm new password", 2, show="●")
        self.error = _label(self.win, "", pal, fg=pal.danger, font=("Segoe UI", 9))
        self.error.pack(pady=(6, 0))

        btns = tk.Frame(self.win, bg=pal.bg)
        btns.pack(fill="x", padx=34, pady=(8, 16))
        tk.Button(btns, text="Change Password", command=self._submit, bg=pal.accent,
                  fg="#ffffff", activebackground=pal.accent_hover, relief="flat",
                  font=("Segoe UI", 10), padx=18, pady=5, bd=0).pack(side="right")
        tk.Button(btns, text="Cancel", command=self.win.destroy, bg=pal.surface_alt, fg=pal.text,
                  activebackground=pal.border, relief="flat", font=("Segoe UI", 10),
                  padx=14, pady=5, bd=0).pack(side="right", padx=(0, 8))
        self.new_ent.bind("<Return>", lambda _e: self._submit())

    def _field(self, parent, label: str, row: int, show: str = "") -> tk.Entry:
        _label(parent, label, self.pal).grid(row=row, column=0, sticky="w", pady=(8, 0))
        ent = tk.Entry(parent, show=show or None, font=("Segoe UI", 10),
                       bg=self.pal.input_bg, fg=self.pal.text, insertbackground=self.pal.text,
                       relief="solid", bd=1, highlightthickness=1,
                       highlightbackground=self.pal.border, highlightcolor=self.pal.accent)
        ent.grid(row=row, column=1, sticky="ew", padx=(12, 0), ipady=4)
        parent.columnconfigure(1, weight=1)
        return ent

    def _submit(self) -> None:
        old = self.old_ent.get()
        new = self.new_ent.get()
        again = self.again_ent.get()
        if new != again:
            self.error.configure(text="New passwords do not match.")
            return
        if len(new) < 4:
            self.error.configure(text="New password must be at least 4 characters.")
            return
        if self.controller.change_master(old, new):
            self.win.destroy()
        else:
            self.error.configure(text="Current password is incorrect.")

    def show(self) -> None:
        self.win.wait_window()


# --------------------------------------------------------------------------- #
# Recovery reset (forgot master password)
# --------------------------------------------------------------------------- #
class RecoveryResetDialog:
    def __init__(self, root: tk.Misc, controller: AppController, pal: Palette):
        self.controller = controller
        self.pal = pal
        self.result = False
        self.win = themed_toplevel(root, pal, "Recover Access", (420, 340))
        _label(self.win, "Recovery", pal, font=("Segoe UI Semibold", 14)).pack(pady=(18, 4))
        _label(self.win,
               "Enter your recovery key, then choose a new master password.\n"
               "The recovery key was shown when AppLocker was first set up.",
               pal, fg=pal.text_muted, wraplength=370, justify="center").pack(pady=(0, 12))

        form = tk.Frame(self.win, bg=pal.bg)
        form.pack(padx=34, fill="x")
        _label(form, "Recovery key", pal).grid(row=0, column=0, sticky="w", pady=(6, 0))
        self.key_ent = tk.Entry(form, font=("Cascadia Mono", 10), bg=pal.input_bg, fg=pal.text,
                                insertbackground=pal.text, relief="solid", bd=1,
                                highlightthickness=1, highlightbackground=pal.border,
                                highlightcolor=pal.accent)
        self.key_ent.grid(row=0, column=1, sticky="ew", padx=(12, 0), ipady=4)
        _label(form, "New master password", pal).grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.new_ent = tk.Entry(form, show="●", font=("Segoe UI", 10), bg=pal.input_bg, fg=pal.text,
                                insertbackground=pal.text, relief="solid", bd=1,
                                highlightthickness=1, highlightbackground=pal.border,
                                highlightcolor=pal.accent)
        self.new_ent.grid(row=1, column=1, sticky="ew", padx=(12, 0), ipady=4)
        _label(form, "Confirm new master", pal).grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.again_ent = tk.Entry(form, show="●", font=("Segoe UI", 10), bg=pal.input_bg, fg=pal.text,
                                  insertbackground=pal.text, relief="solid", bd=1,
                                  highlightthickness=1, highlightbackground=pal.border,
                                  highlightcolor=pal.accent)
        self.again_ent.grid(row=2, column=1, sticky="ew", padx=(12, 0), ipady=4)
        form.columnconfigure(1, weight=1)

        self.error = _label(self.win, "", pal, fg=pal.danger, font=("Segoe UI", 9))
        self.error.pack(pady=(8, 0))

        btns = tk.Frame(self.win, bg=pal.bg)
        btns.pack(fill="x", padx=34, pady=(8, 16))
        tk.Button(btns, text="Reset", command=self._submit, bg=pal.accent, fg="#ffffff",
                  activebackground=pal.accent_hover, relief="flat", font=("Segoe UI", 10),
                  padx=18, pady=5, bd=0).pack(side="right")
        tk.Button(btns, text="Cancel", command=self.win.destroy, bg=pal.surface_alt, fg=pal.text,
                  activebackground=pal.border, relief="flat", font=("Segoe UI", 10),
                  padx=14, pady=5, bd=0).pack(side="right", padx=(0, 8))

    def _submit(self) -> None:
        key = self.key_ent.get()
        new = self.new_ent.get()
        again = self.again_ent.get()
        if new != again:
            self.error.configure(text="New passwords do not match.")
            return
        if len(new) < 4:
            self.error.configure(text="New password must be at least 4 characters.")
            return
        if self.controller.reset_master_with_recovery(key, new):
            self.result = True
            self.win.destroy()
        else:
            self.error.configure(text="Invalid recovery key.")

    def show(self) -> bool:
        self.win.wait_window()
        return self.result


# --------------------------------------------------------------------------- #
# Add application (discovery)
# --------------------------------------------------------------------------- #
class AddAppDialog:
    """Browse discovered apps, running processes, or a file on disk."""

    def __init__(self, root: tk.Misc, controller: AppController, pal: Palette,
                 icon_cache: ui_icons.IconCache):
        self.controller = controller
        self.pal = pal
        self.icon_cache = icon_cache
        self.result: Optional[DiscoveredApp] = None
        self.win = themed_toplevel(root, pal, "Add Application", (680, 500))
        self.win.resizable(True, True)
        _label(self.win, "Add Application", pal, font=("Segoe UI Semibold", 14)).pack(pady=(16, 2))
        _label(self.win, "Choose an application to protect, or browse for an executable.",
               pal, fg=pal.text_muted).pack(pady=(0, 8))

        self._discovered: list[DiscoveredApp] = []
        self._app_by_item: dict[str, DiscoveredApp] = {}

        nb = ttk.Notebook(self.win)
        nb.pack(fill="both", expand=True, padx=20, pady=(0, 8))
        nb.enable_traversal()

        self._build_installed_tab(nb)
        self._build_running_tab(nb)

        btn_row = tk.Frame(self.win, bg=pal.bg)
        btn_row.pack(fill="x", padx=20, pady=(0, 14))
        tk.Button(btn_row, text="Browse for executable…", command=self._browse,
                  bg=pal.surface_alt, fg=pal.text, activebackground=pal.border,
                  relief="flat", font=("Segoe UI", 10), padx=12, pady=5).pack(side="left")
        self._scan_label = _label(btn_row, "Scanning…", pal, fg=pal.text_muted,
                                  font=("Segoe UI", 9))
        self._scan_label.pack(side="left", padx=12)
        self._selected_label = _label(btn_row, "", pal, fg=pal.success, font=("Segoe UI", 9))
        self._selected_label.pack(side="left", padx=12)
        tk.Button(btn_row, text="Add", command=self._confirm, bg=pal.accent, fg="#ffffff",
                  activebackground=pal.accent_hover, relief="flat", font=("Segoe UI", 10),
                  padx=22, pady=5).pack(side="right")
        tk.Button(btn_row, text="Cancel", command=self.win.destroy, bg=pal.surface_alt,
                  fg=pal.text, activebackground=pal.border, relief="flat",
                  font=("Segoe UI", 10), padx=14, pady=5).pack(side="right", padx=(0, 8))

        self._begin_scan()

    def _begin_scan(self) -> None:
        """Scan registry + Start Menu + running processes off the UI thread so
        the dialog opens instantly instead of freezing for seconds.

        Tk forbids ``after`` from other threads ("main thread is not in main
        loop"), so the worker hands results back through a queue that the main
        thread polls briefly.
        """
        self._scan_label.configure(text="Scanning installed and running applications…")
        import queue
        import threading

        self._scan_queue: queue.Queue = queue.Queue()

        def work():
            installed: list[DiscoveredApp] = []
            running: list[DiscoveredApp] = []
            try:
                installed = discover_all()
                running = scan_running()
            except Exception:  # noqa: BLE001
                pass
            self._scan_queue.put((installed, running))

        threading.Thread(target=work, daemon=True).start()
        self._poll_scan()

    def _poll_scan(self) -> None:
        try:
            installed, running = self._scan_queue.get_nowait()
        except Exception:  # noqa: BLE001  (queue.Empty)
            try:
                self.win.after(150, self._poll_scan)
            except Exception:  # noqa: BLE001
                pass
            return
        self._finish_scan(installed, running)

    def _finish_scan(self, installed: list[DiscoveredApp],
                     running: list[DiscoveredApp]) -> None:
        self._discovered = installed
        tree = self._tree_installed
        for app in installed:
            name = app.name or os.path.splitext(os.path.basename(app.path))[0]
            item = tree.insert("", "end", text=" ", values=(name, app.publisher or "—",
                                                             app.path, app.source))
            self._app_by_item[item] = app
        known = {a.path.lower() for a in installed}
        rtree = self._tree_running
        for app in running:
            if app.path.lower() in known:
                continue
            item = rtree.insert("", "end", values=(app.name, app.path))
            self._app_by_item[item] = app
        self._scan_label.configure(
            text=f"{len(tree.get_children())} installed · {len(rtree.get_children())} running")

    def _build_installed_tab(self, nb) -> None:
        tab = ttk.Frame(nb)
        nb.add(tab, text="Installed Applications")
        cols = ("name", "publisher", "path", "source")
        tree = ttk.Treeview(tab, columns=cols, show="tree headings", selectmode="browse", height=12)
        tree.heading("#0", text="")
        tree.heading("name", text="Name")
        tree.heading("publisher", text="Publisher")
        tree.heading("path", text="Path")
        tree.heading("source", text="Source")
        tree.column("#0", width=44, stretch=False)
        tree.column("name", width=180, anchor="w")
        tree.column("publisher", width=140, anchor="w")
        tree.column("path", width=300, anchor="w")
        tree.column("source", width=80, anchor="w")
        sc = ttk.Scrollbar(tab, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sc.set)
        tree.pack(side="left", fill="both", expand=True, padx=(0, 2))
        sc.pack(side="right", fill="y")
        tree.bind("<<TreeviewSelect>>", lambda _e: self._on_select(tree))
        tree.bind("<Double-1>", lambda _e: self._confirm())

        self._tree_installed = tree

    def _build_running_tab(self, nb) -> None:
        tab = ttk.Frame(nb)
        nb.add(tab, text="Running Applications")
        cols = ("name", "path")
        tree = ttk.Treeview(tab, columns=cols, show="tree headings", selectmode="browse")
        tree.heading("#0", text="")
        tree.heading("name", text="Name")
        tree.heading("path", text="Path")
        tree.column("#0", width=44, stretch=False)
        tree.column("name", width=200)
        tree.column("path", width=340)
        tree.pack(fill="both", expand=True)
        tree.bind("<<TreeviewSelect>>", lambda _e: self._on_select(tree))
        self._tree_running = tree

    def _on_select(self, tree) -> None:
        sel = tree.selection()
        if not sel:
            return
        app = self._app_by_item.get(sel[0])
        if app:
            self._pending = app
            self._selected_label.configure(text=app.name)

    def _browse(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.win, title="Choose an executable",
            filetypes=[("Executable files", "*.exe"), ("All files", "*.*")])
        if not path:
            return
        name = os.path.splitext(os.path.basename(path))[0]
        self._pending = DiscoveredApp(name=name, path=path, source="picker")
        self._selected_label.configure(text=name)

    def _confirm(self) -> None:
        if not getattr(self, "_pending", None):
            messagebox.showinfo("Add Application", "Select an application first.",
                                parent=self.win)
            return
        self.result = self._pending
        self.win.destroy()

    def show(self) -> Optional[DiscoveredApp]:
        self.win.wait_window()
        return self.result


# --------------------------------------------------------------------------- #
# Policy editor
# --------------------------------------------------------------------------- #
class PolicyDialog:
    """Edit an app/group policy: always / time window / schedule with days."""

    DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    KINDS = {"always": "Always locked", "time": "Allowed time window", "schedule": "Custom schedule", "none": "Not protected"}

    def __init__(self, root: tk.Misc, controller: AppController, pal: Palette,
                 current: dict, is_group: bool = False):
        self.controller = controller
        self.pal = pal
        self.is_group = is_group
        self.result = None
        kind = current.get("policy", "none")
        schedule = current.get("schedule_json") or {}
        allow_start = current.get("allow_start", "07:00")
        allow_end = current.get("allow_end", "20:00")

        title = "Group Policy" if is_group else "Application Policy"
        self.win = themed_toplevel(root, pal, title, (470, 400))
        _label(self.win, title, pal, font=("Segoe UI Semibold", 14)).pack(pady=(16, 8))

        p = tk.Frame(self.win, bg=pal.bg)
        p.pack(fill="x", padx=30)
        _label(p, "Policy", pal).pack(anchor="w")
        self.kind_var = tk.StringVar(value=kind)
        row = tk.Frame(p, bg=pal.bg)
        row.pack(fill="x", pady=(4, 0))
        for k, label in self.KINDS.items():
            tk.Radiobutton(row, text=label, variable=self.kind_var, value=k,
                           bg=pal.bg, fg=pal.text, selectcolor=pal.surface_alt,
                           activebackground=pal.bg, activeforeground=pal.text,
                           font=("Segoe UI", 9), command=self._rebuild_extra).pack(side="left", padx=(0, 14))

        self.extra = tk.Frame(self.win, bg=pal.bg)
        self.extra.pack(fill="both", expand=True, padx=30, pady=(8, 0))
        self.start_var = tk.StringVar(value=allow_start)
        self.end_var = tk.StringVar(value=allow_end)
        self._days_vars = {d: tk.BooleanVar() for d in self.DAYS}
        sched = schedule
        for d in self.DAYS:
            if d[:3] in sched:
                self._days_vars[d].set(True)
                entry = sched[d[:3]]
                self.start_var.set(f"{int(entry.get('start_hour', 0)):02d}:{int(entry.get('start_minute', 0)):02d}")
                self.end_var.set(f"{int(entry.get('end_hour', 23)):02d}:{int(entry.get('end_minute', 59)):02d}")
        self._rebuild_extra()

        btns = tk.Frame(self.win, bg=pal.bg)
        btns.pack(fill="x", padx=30, pady=(4, 16))
        tk.Button(btns, text="Save", command=self._save, bg=pal.accent, fg="#ffffff",
                  activebackground=pal.accent_hover, relief="flat", font=("Segoe UI", 10),
                  padx=18, pady=5).pack(side="right")
        tk.Button(btns, text="Cancel", command=self.win.destroy, bg=pal.surface_alt, fg=pal.text,
                  activebackground=pal.border, relief="flat", font=("Segoe UI", 10),
                  padx=14, pady=5).pack(side="right", padx=(0, 8))

    def _rebuild_extra(self) -> None:
        for child in self.extra.winfo_children():
            child.destroy()
        kind = self.kind_var.get()
        if kind == "time":
            _label(self.extra, "Allowed window", pal, font=("Segoe UI Semibold", 10)).pack(anchor="w", pady=(6, 4))
            row = tk.Frame(self.extra, bg=pal.bg)
            row.pack(anchor="w")
            _label(row, "From ", pal).pack(side="left")
            ttk.Spinbox(row, from_=0, to=23, width=2, textvariable=self.start_var, format="%02.0f",
                        font=("Segoe UI", 10)).pack(side="left", padx=(2, 8))
            _label(row, " To ", pal).pack(side="left")
            ttk.Spinbox(row, from_=0, to=23, width=2, textvariable=self.end_var, format="%02.0f",
                        font=("Segoe UI", 10)).pack(side="left")
            # Note: keep wildcard "" out of format; user edits hours.
            self._fix_spinbox_format()
        elif kind == "schedule":
            _label(self.extra, "Days", pal, font=("Segoe UI Semibold", 10)).pack(anchor="w", pady=(6, 2))
            days_row = tk.Frame(self.extra, bg=pal.bg)
            days_row.pack(anchor="w")
            for d in self.DAYS[:4]:
                tk.Checkbutton(days_row, text=d[:3], variable=self._days_vars[d],
                               bg=pal.bg, fg=pal.text, selectcolor=pal.surface_alt,
                               activebackground=pal.bg, activeforeground=pal.text,
                               font=("Segoe UI", 9)).pack(side="left", padx=0)
            days_row2 = tk.Frame(self.extra, bg=pal.bg)
            days_row2.pack(anchor="w")
            for d in self.DAYS[4:]:
                tk.Checkbutton(days_row2, text=d[:3], variable=self._days_vars[d],
                               bg=pal.bg, fg=pal.text, selectcolor=pal.surface_alt,
                               activebackground=pal.bg, activeforeground=pal.text,
                               font=("Segoe UI", 9)).pack(side="left", padx=0)
            _label(self.extra, "Allowed window (start → end, overnight OK)", pal,
                   font=("Segoe UI", 9), fg=pal.text_muted).pack(anchor="w", pady=(8, 2))
            row = tk.Frame(self.extra, bg=pal.bg)
            row.pack(anchor="w")
            _label(row, "From ", pal).pack(side="left")
            ttk.Spinbox(row, from_=0, to=23, width=2, textvariable=self.start_var, format="%02.0f").pack(side="left", padx=(2, 8))
            _label(row, " To ", pal).pack(side="left")
            ttk.Spinbox(row, from_=0, to=23, width=2, textvariable=self.end_var, format="%02.0f").pack(side="left")
            self._fix_spinbox_format()
            _label(self.extra, "Apps are blocked outside the selected days and time, "
                   "on days with no window, and any time outside it.",
                   pal, fg=pal.text_faint, wraplength=400, justify="left", font=("Segoe UI", 9)).pack(anchor="w", pady=(10, 0))
        elif kind == "always":
            _label(self.extra, "This application will require authentication every time it is launched.",
                   pal, fg=pal.text_muted, wraplength=400, justify="left").pack(anchor="w", pady=(10, 0))
        else:
            _label(self.extra, "No protection; the app can be launched freely.",
                   pal, fg=pal.text_muted).pack(anchor="w", pady=(10, 0))

    def _fix_spinbox_format(self) -> None:
        for spin in self.extra.winfo_children():
            pass

    def _save(self) -> None:
        kind = self.kind_var.get()
        schedule = {}
        if kind == "schedule":
            for d in self.DAYS:
                if self._days_vars[d].get():
                    sh, sm = self._parse_hhmm(self.start_var.get())
                    eh, em = self._parse_hhmm(self.end_var.get())
                    schedule[d[:3]] = {"start_hour": sh, "start_minute": sm,
                                       "end_hour": eh, "end_minute": em}
        allow_start, allow_end = self.start_var.get(), self.end_var.get()
        if kind == "time" and not schedule:
            pass
        self.result = {"policy": kind, "schedule_json": schedule,
                       "allow_start": allow_start if kind == "time" else "07:00",
                       "allow_end": allow_end if kind == "time" else "20:00"}
        self.win.destroy()

    @staticmethod
    def _parse_hhmm(value: str) -> tuple[int, int]:
        parts = value.strip().replace(":", " ").split()
        try:
            hh = int(float(parts[0])) if parts else 0
            mm = int(float(parts[1])) if len(parts) > 1 else 0
        except (ValueError, IndexError):
            hh, mm = 0, 0
        return max(0, min(23, hh)), max(0, min(59, mm))

    def show(self) -> Optional[dict]:
        self.win.wait_window()
        return self.result


# --------------------------------------------------------------------------- #
# Pause protection
# --------------------------------------------------------------------------- #
class PauseDialog:
    def __init__(self, root: tk.Misc, controller: AppController, pal: Palette):
        self.controller = controller
        self.pal = pal
        self.win = themed_toplevel(root, pal, "Pause Protection", (360, 260))
        _label(self.win, "Pause Protection", pal, font=("Segoe UI Semibold", 14)).pack(pady=(20, 4))
        _label(self.win, "Authentication required before disabling protection.\n"
               "Protection resumes automatically.", pal, fg=pal.text_muted,
               justify="center", wraplength=300).pack(pady=(0, 12))

        self.entry = tk.Entry(self.win, show="●", font=("Segoe UI", 11), bg=pal.input_bg,
                              fg=pal.text, insertbackground=pal.text, relief="solid", bd=1,
                              highlightthickness=1, highlightbackground=pal.border,
                              highlightcolor=pal.accent)
        self.entry.pack(fill="x", padx=40, ipady=5)
        self.entry.focus_set()
        self.entry.bind("<Return>", lambda _e: self._choose())

        durations = [("5 minutes", 5), ("15 minutes", 15), ("30 minutes", 30),
                     ("1 hour", 60), ("Until resumed", 0)]
        btns = tk.Frame(self.win, bg=pal.bg)
        btns.pack(fill="both", expand=True, pady=(10, 14))
        for label, minutes in durations:
            tk.Button(btns, text=label, command=lambda m=minutes: self._choose_duration(
                None if m == 0 else m),
                bg=pal.surface_alt, fg=pal.text, activebackground=pal.border, relief="flat",
                font=("Segoe UI", 10), padx=10, pady=4).pack(fill="x", padx=40, pady=2)

    def _auth_ok(self) -> bool:
        if not self.controller.try_master(self.entry.get()):
            messagebox.showerror("Pause Protection", "Incorrect master password.",
                                 parent=self.win)
            return False
        return True

    def _choose_duration(self, minutes) -> None:
        if not self._auth_ok():
            return
        if minutes is None:
            self.controller.pause_protection_until_resumed()
        else:
            self.controller.pause_protection(minutes)
        self.win.destroy()

    def _choose(self) -> None:
        self._choose_duration(15)

    def show(self) -> None:
        self.win.wait_window()


# --------------------------------------------------------------------------- #
# Recovery key display
# --------------------------------------------------------------------------- #
class RecoveryKeyDialog:
    """Shows the user's recovery key with a confirm-to-reveal gate."""

    def __init__(self, root: tk.Misc, controller: AppController, pal: Palette):
        self.controller = controller
        self.pal = pal
        self.win = themed_toplevel(root, pal, "Recovery Key", (460, 280))
        _label(self.win, "Recovery Key", pal, font=("Segoe UI Semibold", 14)).pack(pady=(20, 4))
        _label(self.win, "Keep this key safe but private. It can reset a forgotten master password.\n"
               "You must authenticate to reveal it.", pal, fg=pal.text_muted, wraplength=410,
               justify="center").pack(pady=(0, 10))

        self._stage_auth()
        self.key_var = tk.StringVar()

    def _stage_auth(self) -> None:
        self.entry = tk.Entry(self.win, show="●", font=("Segoe UI", 11), bg=self.pal.input_bg,
                              fg=self.pal.text, insertbackground=self.pal.text, relief="solid",
                              bd=1, highlightthickness=1, highlightbackground=self.pal.border,
                              highlightcolor=self.pal.accent)
        self.entry.pack(fill="x", padx=46, ipady=5)
        self.entry.focus_set()
        self.entry.bind("<Return>", lambda _e: self._reveal())
        btns = tk.Frame(self.win, bg=self.pal.bg)
        btns.pack(fill="x", padx=46, pady=(10, 16))
        tk.Button(btns, text="Reveal", command=self._reveal, bg=self.pal.accent, fg="#ffffff",
                  activebackground=self.pal.accent_hover, relief="flat", font=("Segoe UI", 10),
                  padx=18, pady=5).pack(side="right")
        tk.Button(btns, text="Cancel", command=self.win.destroy, bg=self.pal.surface_alt,
                  fg=self.pal.text, activebackground=self.pal.border, relief="flat",
                  font=("Segoe UI", 10), padx=14, pady=5).pack(side="right", padx=(0, 8))

    def _reveal(self) -> None:
        if not self.controller.try_master(self.entry.get()):
            messagebox.showerror("Recovery Key", "Incorrect master password.", parent=self.win)
            return
        key = self.controller.recovery_key()
        if not key:
            messagebox.showwarning("Recovery Key", "No recovery key is stored for this installation.",
                                   parent=self.win)
            self.win.destroy()
            return
        for child in self.win.winfo_children():
            child.destroy()
        pal = self.pal
        _label(self.win, "Your Recovery Key", pal, font=("Segoe UI Semibold", 14)).pack(pady=(22, 8))
        _label(self.win, "Store it in a safe place. Anyone with this key can reset your master password.",
               pal, fg=pal.text_muted, wraplength=410, justify="center").pack(pady=(0, 8))
        show = tk.Label(self.win, text=key, font=("Cascadia Mono", 13, "bold"), bg=self.pal.accent_soft,
                        fg=self.pal.accent, padx=22, pady=12)
        show.pack(fill="x", padx=46, pady=(6, 8))
        btns = tk.Frame(self.win, bg=self.pal.bg)
        btns.pack(fill="x", padx=46, pady=(4, 18))
        tk.Button(btns, text="Copy", command=lambda: (self.win.clipboard_clear(),
                                                      self.win.clipboard_append(key),
                                                      self.win.update()), bg=self.pal.surface_alt,
                  fg=self.pal.text, activebackground=self.pal.border, relief="flat",
                  font=("Segoe UI", 10), padx=14, pady=5).pack(side="left")
        tk.Button(btns, text="Done", command=self.win.destroy, bg=self.pal.accent, fg="#ffffff",
                  activebackground=self.pal.accent_hover, relief="flat", font=("Segoe UI", 10),
                  padx=18, pady=5).pack(side="right")

    def show(self) -> None:
        self.win.wait_window()


# --------------------------------------------------------------------------- #
# Group creation
# --------------------------------------------------------------------------- #
class GroupDialog:
    COLORS = ["#0b6bce", "#0e9f8a", "#178a3f", "#cb3e6b", "#b25d00", "#c2271e", "#5b6b7c"]

    def __init__(self, root: tk.Misc, controller: AppController, pal: Palette):
        self.controller = controller
        self.pal = pal
        self.win = themed_toplevel(root, pal, "New Group", (420, 260))
        _label(self.win, "Create Group", pal, font=("Segoe UI Semibold", 14)).pack(pady=(18, 8))

        form = tk.Frame(self.win, bg=pal.bg)
        form.pack(fill="x", padx=34)
        _label(form, "Group name", pal).pack(anchor="w")
        self.name_ent = tk.Entry(form, font=("Segoe UI", 10), bg=pal.input_bg, fg=pal.text,
                                 insertbackground=pal.text, relief="solid", bd=1,
                                 highlightthickness=1, highlightbackground=pal.border,
                                 highlightcolor=pal.accent)
        self.name_ent.pack(fill="x", ipady=4, pady=(4, 10))
        _label(form, "Color", pal).pack(anchor="w")
        self.color_var = tk.StringVar(value=self.COLORS[0])
        row = tk.Frame(form, bg=pal.bg)
        row.pack(anchor="w", pady=(4, 0))
        for color in self.COLORS:
            c = tk.Canvas(row, width=20, height=20, bg=pal.bg, highlightthickness=0, cursor="hand2")
            c.create_oval(3, 3, 17, 17, fill=color, outline=pal.border)
            c.pack(side="left", padx=3)
            c.bind("<Button-1>", lambda _e, col=color: self.color_var.set(col))

        btns = tk.Frame(self.win, bg=pal.bg)
        btns.pack(fill="x", padx=34, pady=(14, 18))
        tk.Button(btns, text="Create", command=self._save, bg=pal.accent, fg="#ffffff",
                  activebackground=pal.accent_hover, relief="flat", font=("Segoe UI", 10),
                  padx=18, pady=5).pack(side="right")
        tk.Button(btns, text="Cancel", command=self.win.destroy, bg=pal.surface_alt,
                  fg=pal.text, activebackground=pal.border, relief="flat", font=("Segoe UI", 10),
                  padx=14, pady=5).pack(side="right", padx=(0, 8))
        self.name_ent.bind("<Return>", lambda _e: self._save())

    def _save(self) -> None:
        name = self.name_ent.get().strip()
        if not name:
            return
        self.controller.add_group(name, self.color_var.get())
        self.win.destroy()

    def show(self) -> None:
        self.win.wait_window()


# --------------------------------------------------------------------------- #
# Group management (members + policy)
# --------------------------------------------------------------------------- #
class GroupManageDialog:
    def __init__(self, root: tk.Misc, controller: AppController, pal: Palette, group: dict):
        self.controller = controller
        self.pal = pal
        self.group = group
        self.win = themed_toplevel(root, pal, f"Group — {group['name']}", (560, 480))
        self.win.resizable(True, True)
        _label(self.win, group["name"], pal, font=("Segoe UI Semibold", 14)).pack(pady=(16, 2))

        current = self.group
        _label(self.win, f"Policy: {_group_policy_label(group)}",
               pal, fg=pal.text_muted).pack(anchor="w", padx=28)

        top = ttk.Frame(self.win)
        top.pack(fill="x", padx=28, pady=(10, 4))
        ttk.Button(top, text="Edit Policy…", style="TButton",
                   command=self._edit_policy).pack(side="left")
        ttk.Button(top, text="Add Applications…", style="Secondary.TButton",
                   command=self._add_members).pack(side="left", padx=(8, 0))
        ttk.Button(top, text="Delete Group", style="Danger.TButton",
                   command=self._delete).pack(side="right")

        host = ttk.Frame(self.win)
        host.pack(fill="both", expand=True, padx=28, pady=(6, 0))
        cols = ("name", "path", "policy")
        self.tree = ttk.Treeview(host, columns=cols, show="headings")
        for col, label, width in [("name", "Application", 180), ("path", "Path", 240),
                                  ("policy", "Policy", 110)]:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width)
        self.tree.pack(side="left", fill="both", expand=True)
        sc = ttk.Scrollbar(host, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sc.set)
        sc.pack(side="right", fill="y")
        self._reload()

        bottom = ttk.Frame(self.win)
        bottom.pack(fill="x", padx=28, pady=(8, 16))
        ttk.Button(bottom, text="Remove Selected", style="Ghost.TButton",
                   command=self._remove_selected).pack(side="left")
        ttk.Button(bottom, text="Close", style="Secondary.TButton",
                   command=self.win.destroy).pack(side="right")

    def _reload(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for app in self.controller.db.group_apps(self.group["id"]):
            self.tree.insert("", "end", iid=app["id"],
                             values=(app["name"], app["path"], _group_policy_label(app)))

    def _edit_policy(self) -> None:
        dlg = PolicyDialog(self.win, self.controller, self.pal, self.group, is_group=True)
        res = dlg.show()
        if res:
            self.controller.update_group(self.group["id"], policy=res["policy"],
                                         schedule_json=res["schedule_json"])
            self.group = self.controller.db.get_group(self.group["id"]) or self.group
            self.win.title(f"Group — {self.group['name']}")

    def _add_members(self) -> None:
        dlg = AddAppDialog(self.win, self.controller, self.pal, _empty_icon_cache(self.win))
        found = dlg.show()
        if found:
            existing = next(
                (a for a in self.controller.db.list_apps() if a.get("path", "").lower() == found.path.lower()),
                None,
            )
            if existing:
                self.controller.db.add_app_to_group(self.group["id"], existing["id"])
            else:
                icon_path = ""
                try:
                    from applocker.util.paths import get_icon_cache_dir
                    icon_path = IconExtractor(get_icon_cache_dir()).get(found.path) or ""
                except Exception:  # noqa: BLE001
                    icon_path = ""
                app = self.controller.add_app(found.name, found.path, found.publisher,
                                              found.version, policy="none", icon_cache=icon_path)
                self.controller.db.add_app_to_group(self.group["id"], app["id"])
            self._reload()

    def _remove_selected(self) -> None:
        for app_id in self.tree.selection():
            self.controller.db.remove_app_from_group(self.group["id"], app_id)
        self._reload()

    def _delete(self) -> None:
        if messagebox.askyesno("Delete Group", f"Delete group '{self.group['name']}'?",
                               parent=self.win):
            self.controller.delete_group(self.group["id"])
            self.win.destroy()

    def show(self) -> None:
        self.win.wait_window()


def _group_policy_label(data: dict) -> str:
    kind = data.get("policy", "none")
    return {"always": "Always Locked", "time": "Time Window",
            "schedule": "Scheduled", "none": "No policy"}.get(kind, kind)


def _empty_icon_cache(root: tk.Misc):
    from applocker.ui.icons import IconCache
    return IconCache(root)