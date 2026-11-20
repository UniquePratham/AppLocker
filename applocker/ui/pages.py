"""Primary UI pages (Dashboard, Applications, Groups, Activity, Settings,
About). Each ``build_*`` returns a widget placed into the main content area.

Widgets are mostly ttk (global theme) so light/dark switch applies across the
whole tree; the ``Card`` canvas widget gives the rounded-corner surfaces.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from applocker.core.app import AppController
from applocker.core.discovery import DiscoveredApp
from applocker.core.policy import WEEKDAY_NAMES
from applocker.ui import dialogs
from applocker.ui.widgets import Badge, Card, EmptyState, PageHeader
from applocker.util.logging import snapshot as logging_snapshot
from applocker.util.winutil import is_startup_enabled, set_startup_enabled


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
class Page(ttk.Frame):
    """Base page: holds references to the window, controller and palette."""

    def __init__(self, master, controller: AppController, window):
        super().__init__(master, style="TFrame")
        self.controller = controller
        self.window = window
        self.pal = window.pal


def _header(page: Page, title: str, subtitle: str = "") -> None:
    PageHeader(page, page.pal, title, subtitle).pack(fill="x", pady=(0, 16))


def _stat_card(parent, pal, value: str, label: str, accent: str,
               width: int | None = None, height: int = 76) -> tk.Widget:
    card = Card(parent, pal, radius=12, width=width, height=height)
    inner = card.body()
    ttk.Label(inner, text=value, style="TLabel",
              font=("Segoe UI Semibold", 20), foreground=accent).pack(anchor="w")
    ttk.Label(inner, text=label, style="Faint.TLabel").pack(anchor="w")
    return card


def _monthday(ts: str) -> str:
    if not ts:
        return ""
    d = ts.split("T")[0]
    try:
        from datetime import datetime
        return datetime.fromisoformat(ts).strftime("%b %d, %H:%M")
    except Exception:  # noqa: BLE001
        return d


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
def build_dashboard(master, controller: AppController, window) -> tk.Widget:
    page = Page(master, controller, window)
    pal = page.pal
    apps = controller.db.list_apps()
    groups = controller.db.list_groups()
    protected = [a for a in apps if a.get("policy") != "none"]
    status = controller.protection_status()
    today_blocked = controller.db.count_events(event_type="blocked")
    event_count = controller.db.event_count()

    _header(page, "Dashboard",
            "Security overview and quick control for protected applications.")

    # Status hero
    hero = Card(page, pal, radius=14, height=110)
    hero.pack(fill="x", pady=(0, 14))
    inner = hero.body()
    dot_color = pal.success if status == "active" else (pal.warning if status == "paused" else pal.danger)
    status_text = {"active": "Protection Active", "paused": "Protection Paused"}.get(status, "Unknown")
    row = ttk.Frame(inner, style="Card.TFrame")
    row.pack(fill="x")
    dot = tk.Canvas(row, width=14, height=14, bg=pal.surface, highlightthickness=0)
    dot.create_oval(2, 2, 12, 12, fill=dot_color, outline="")
    dot.pack(side="left", pady=(10, 0))
    ttk.Label(row, text=status_text, style="TLabel",
              font=("Segoe UI Semibold", 15)).pack(side="left", padx=(8, 0))

    if status == "paused" and controller.pause.active():
        remaining = controller.pause.remaining()
        if remaining > 0:
            mm, ss = divmod(remaining, 60)
            ttk.Label(row, text=f"· resumes in {mm:02d}:{ss:02d}" if remaining else "· paused until resumed",
                      style="Faint.TLabel").pack(side="left", padx=(12, 0))
        else:
            ttk.Label(row, text="· paused until resumed", style="Faint.TLabel").pack(side="left", padx=(12, 0))
    ttk.Label(row, text=f"{len(protected)} application(s) protected.",
              style="Faint.TLabel").pack(side="right")

    actions = ttk.Frame(inner, style="Card.TFrame")
    actions.pack(anchor="w", pady=(12, 0))
    if status == "active":
        ttk.Button(actions, text="Pause Protection", style="Ghost.TButton",
                   command=lambda: _do_pause(window)).pack(side="left")
    else:
        ttk.Button(actions, text="Resume Protection", style="TButton",
                   command=lambda: _do_resume(window, controller)).pack(side="left")
    ttk.Button(actions, text="Lock All", style="Secondary.TButton",
               command=lambda: _do_lock_all(window, controller)).pack(side="left", padx=(8, 0))
    ttk.Button(actions, text="+ Add Application", style="TButton",
               command=lambda: _do_add_app(window)).pack(side="right")

    if page.pal:
        pass

    # Stat tiles
    tiles = ttk.Frame(page, style="TFrame")
    tiles.pack(fill="x", pady=(0, 14))
    tiles.columnconfigure((0, 1, 2, 3), weight=1, uniform="tile")
    data = [
        (f"{len(protected)}", "Protected Applications", pal.accent),
        (f"{today_blocked}", "Blocked Attempts", pal.danger),
        (f"{len(groups)}", "Smart Groups", pal.info),
        (f"{event_count}", "Log Events", pal.success),
    ]
    for i, (value, label, accent) in enumerate(data):
        tiles.columnconfigure(i, weight=1, uniform="tile")
        tile = Card(tiles, pal, radius=12, height=64, width=180)
        tile.grid(row=0, column=i, sticky="nsew", padx=4)
        inner = tile.body()
        bubble = ttk.Frame(inner, style="Card.TFrame")
        bubble.pack()
        ttk.Label(bubble, text=value, foreground=accent,
                  font=("Segoe UI Semibold", 22)).pack(side="left")
        ttk.Label(inner, text=label, style="Faint.TLabel").pack()

    # Protected applications quick list
    _header2 = ttk.Label(page, text="Protected Applications", style="Section.TLabel")
    _header2.pack(anchor="w", pady=(0, 8))
    if not apps:
        empty = EmptyState(page, "No protected applications yet",
                           "Add an application to start protecting it.\n"
                           "AppLocker will block protected apps until the correct password is entered.",
                           pal, icon_text="🔒", action_text="+ Add Application",
                           action=lambda: _do_add_app(window))
        empty.pack(fill="both", expand=True)
    else:
        list_host = ttk.Frame(page, style="TFrame")
        list_host.pack(fill="both", expand=True)
        _render_app_rows(list_host, page, apps[:8])

    page.on_status_changed = lambda: None
    return page


def _do_pause(window) -> None:
    if not window.pal:
        return
    dlg = dialogs.PauseDialog(window.root, window.controller, window.pal)
    dlg.show()
    window.refresh_pages()


def _do_resume(window, controller) -> None:
    if not window.pal:
        return
    if controller.protection_status() != "active":
        controller.resume_protection()
        window.toast("Protection resumed", "success")
        window.refresh_pages()


def _do_lock_all(window, controller) -> None:
    controller.lock_all()
    window.toast("All policies reasserted", "success")
    window.refresh_pages()


def _do_add_app(window) -> None:
    if not window.pal:
        return
    dlg = dialogs.AddAppDialog(window.root, window.controller, window.pal, window.icon_cache)
    found = dlg.show()
    if found:
        controller = window.controller
        # Normalise the exe path and extract its Windows icon for the list.
        exe_path = os.path.normpath(found.path)
        icon_cache = ""
        try:
            from applocker.util.paths import get_icon_cache_dir
            from applocker.util.winutil import IconExtractor
            icon_cache = IconExtractor(get_icon_cache_dir()).get(exe_path) or ""
        except Exception:  # noqa: BLE001
            icon_cache = ""
        if not os.path.isfile(exe_path):
            window.toast("Executable not found — path will be checked on launch.", "warning")
        controller.add_app(found.name, exe_path, found.publisher, found.version,
                           policy="always", icon_cache=icon_cache)
        window.toast(f"Added {found.name}", "success")
        window.refresh_pages()


def _render_app_rows(parent, page: Page, apps: list[dict], with_controls: bool = True) -> None:
    """Render a vertical list of app cards."""
    for app in apps:
        row = Card(parent, page.pal, radius=10, height=64)
        row.pack(fill="x", pady=3)
        inner = row.body()
        inner.columnconfigure(0, weight=0)
        inner.columnconfigure((1, 2), weight=1)
        inner.columnconfigure(3, weight=0)

        icon_path = app.get("icon_cache") or ""
        photo = page.window.icon_cache.get(icon_path, 40)
        icon = tk.Label(inner, image=photo, bg=page.pal.surface, text="")
        icon.image = photo
        icon.grid(row=0, column=0, rowspan=2, padx=(0, 12), pady=8)

        ttk.Label(inner, text=app["name"], style="TLabel",
                  font=("Segoe UI Semibold", 11)).grid(row=0, column=1, sticky="sw")
        sub = ", ".join(x for x in [app.get("publisher") or "", app["path"]] if x)
        ttk.Label(inner, text=sub[:110], style="Faint.TLabel").grid(row=1, column=1, sticky="nw")

        policy_text = _policy_label(app)
        ttk.Label(inner, text=policy_text, style="Muted.TLabel").grid(row=0, column=2, sticky="e")
        ttk.Label(inner, text=_status_label(app), style="Success.TLabel").grid(row=1, column=2, sticky="e")
        if with_controls:
            ttk.Button(inner, text="Manage", style="Ghost.TButton",
                       command=lambda a=app: _open_app_controls(page, a)).grid(row=0, column=3, rowspan=2,
                                                                              padx=(8, 0), sticky="e")


def _policy_label(app: dict) -> str:
    kind = app.get("policy", "none")
    return {"always": "Always Locked", "time": "Time Window",
            "schedule": "Scheduled", "none": "Unprotected"}.get(kind, kind)


def _status_label(app: dict) -> str:
    if app.get("temp_unlock"):
        return "Temporarily allowed"
    if app.get("policy", "none") != "none":
        return "Protected"
    return "Not protected"


def _open_app_controls(page: Page, app: dict) -> None:
    """Open the app detail/workspace dialog from a card."""
    win = dialogs.themed_toplevel(page.window.root, page.pal, app["name"], (520, 470))
    _label = ttk.Label
    body = ttk.Frame(win, style="TFrame")
    body.pack(fill="both", expand=True, padx=22, pady=18)
    _label(body, text=app["name"], style="PageTitle.TLabel").pack(anchor="w")
    for line in (f"Publisher: {app.get('publisher') or '—'}",
                 f"Path: {app['path']}",
                 f"Version: {app.get('version') or '—'}"):
        ttk.Label(body, text=line, style="Faint.TLabel").pack(anchor="w", pady=1)
    ttk.Separator(body).pack(fill="x", pady=12)
    ttk.Label(body, text="Policy",
              style="Section.TLabel").pack(anchor="w", pady=(0, 6))
    policy = app.get("policy", "none")
    ttk.Label(body, text=_policy_label(app), style="Muted.TLabel").pack(anchor="w")

    ttk.Separator(body).pack(fill="x", pady=12)
    ttk.Label(body, text="Unlock password",
              style="Section.TLabel").pack(anchor="w", pady=(0, 6))
    ttk.Label(body, text=_password_mode(page.controller, app), style="Muted.TLabel").pack(anchor="w")
    ttk.Label(body, text=("Apps without a custom password unlock with your master password. "
                          "Set a custom one to give this app its own secret — both can be used "
                          "at the same time."),
              style="Faint.TLabel", wraplength=460, justify="left").pack(anchor="w", pady=(2, 0))

    btns = ttk.Frame(body, style="TFrame")
    btns.pack(anchor="w", pady=(16, 0))
    ttk.Button(btns, text="Edit Policy…", style="TButton",
               command=lambda: _edit_policy(page, win, app)).pack(side="left")
    ttk.Button(btns, text="Set Password…", style="Secondary.TButton",
               command=lambda: _open_password(page, win, app)).pack(side="left", padx=(8, 0))
    ttk.Button(btns, text="Unlock 15 min", style="Secondary.TButton",
               command=lambda: _temp_unlock(page, win, app, 15)).pack(side="left", padx=(8, 0))
    ttk.Button(btns, text="Unlock 60 min", style="Secondary.TButton",
               command=lambda: _temp_unlock(page, win, app, 60)).pack(side="left", padx=(8, 0))
    ttk.Button(btns, text="Remove App", style="Danger.TButton",
               command=lambda: _remove_app(page, win, app)).pack(side="right")


def _password_mode(controller: AppController, app: dict) -> str:
    if controller.secrets.app_verifier(app["id"]):
        return "Custom password (this app only)"
    return "Master password (shared with all apps)"


def _open_password(page: Page, win, app: dict) -> None:
    from applocker.ui import passwords
    dlg = passwords.AppPasswordDialog(page.window.root, page.controller, page.pal, app)
    dlg.show()
    win.destroy()
    page.window.refresh_pages()


def _edit_policy(page: Page, win, app: dict) -> None:
    dlg = dialogs.PolicyDialog(page.window.root, page.controller, page.pal, app)
    res = dlg.show()
    if res:
        page.controller.set_app_policy(app["id"], res["policy"], res["schedule_json"])
        page.window.toast(f"Policy updated for {app['name']}", "success")
        win.destroy()
        page.window.refresh_pages()


def _temp_unlock(page: Page, win, app: dict, minutes: int) -> None:
    page.controller.set_temp_unlock(app["id"], minutes)
    page.window.toast(f"{app['name']} unlocked for {minutes} min", "info")
    win.destroy()
    page.window.refresh_pages()


def _remove_app(page: Page, win, app: dict) -> None:
    if messagebox.askyesno("Remove Application", f"Remove {app['name']} from AppLocker?",
                           parent=win):
        page.controller.remove_app(app["id"])
        page.window.toast(f"Removed {app['name']}", "info")
        win.destroy()
        page.window.refresh_pages()


# --------------------------------------------------------------------------- #
# Applications
# --------------------------------------------------------------------------- #
def build_applications(master, controller: AppController, window) -> tk.Widget:
    page = Page(master, controller, window)
    pal = page.pal
    apps = controller.db.list_apps()

    _header(page, "Applications", "Discover, protect and manage your applications.")
    top = ttk.Frame(page, style="TFrame")
    top.pack(fill="x", pady=(0, 12))
    search = ttk.Entry(top, style="TEntry")
    search.pack(side="left", fill="x", expand=True, padx=(0, 10), ipady=3)
    ttk.Button(top, text="+ Add Application", style="TButton",
               command=lambda: _do_add_app(window)).pack(side="right")

    filter_var = tk.StringVar(value="all")
    filter_row = ttk.Frame(page, style="TFrame")
    filter_row.pack(fill="x", pady=(0, 8))
    for key, label in [("all", "All"), ("protected", "Protected"),
                       ("unprotected", "Unprotected"), ("favorites", "Favorites")]:
        ttk.Radiobutton(filter_row, text=label, value=key, variable=filter_var,
                        style="TRadiobutton").pack(side="left", padx=(0, 14))

    if not apps:
        EmptyState(page, "No applications yet",
                   "Add an application and it will appear here for management.",
                   pal, icon_text="📦", action_text="+ Add Application",
                   action=lambda: _do_add_app(window)).pack(fill="both", expand=True)
        page.on_status_changed = lambda: None
        return page

    tree_frame = ttk.Frame(page, style="TFrame")
    tree_frame.pack(fill="both", expand=True)
    cols = ("publisher", "path", "policy", "status")
    tree = ttk.Treeview(tree_frame, columns=cols, show="tree headings", selectmode="extended")
    tree.heading("#0", text="Name")
    tree.column("#0", width=230, minwidth=160, anchor="w")
    for col, label, width in [("publisher", "Publisher", 150), ("path", "Path", 260),
                              ("policy", "Policy", 110), ("status", "Status", 140)]:
        tree.heading(col, text=label)
        tree.column(col, width=width, minwidth=90, anchor="w")
    vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")

    filtered = _filter_apps(apps, search.get().lower())
    _populate_app_tree(tree, controller, filtered, pal, window)
    page.apps_tree = tree

    def _apply_filter(_event=None):
        filtered = _filter_apps(apps, search.get().lower(), filter_var.get())
        _populate_app_tree(tree, controller, filtered, pal, window)

    search.bind("<KeyRelease>", _apply_filter)
    filter_var.trace_add("write", lambda *_: _apply_filter())
    tree.bind("<Double-1>", lambda e: _tree_row_action(page, tree))
    tree.bind("<Delete>", lambda e: _tree_delete_selected(page, tree))
    tree.bind("<space>", lambda e: _tree_toggle_fav(page, tree))

    actions = ttk.Frame(page, style="TFrame")
    actions.pack(fill="x", pady=(10, 0))
    ttk.Button(actions, text="Manage Selected / Details", style="Secondary.TButton",
               command=lambda: _tree_row_action(page, tree)).pack(side="left")
    ttk.Button(actions, text="Set Password…", style="Secondary.TButton",
               command=lambda: _set_password(page, tree)).pack(side="left", padx=(8, 0))
    ttk.Button(actions, text="Favorite", style="Ghost.TButton",
               command=lambda: _tree_toggle_fav(page, tree)).pack(side="left", padx=(8, 0))
    ttk.Button(actions, text="Remove", style="Danger.TButton",
               command=lambda: _tree_delete_selected(page, tree)).pack(side="right")

    page.on_status_changed = lambda: None
    return page


def _filter_apps(apps: list[dict], search: str, mode: str = "all") -> list[dict]:
    def match(a: dict) -> bool:
        if mode == "protected" and a.get("policy") == "none":
            return False
        if mode == "unprotected" and a.get("policy") != "none":
            return False
        if mode == "favorites" and not a.get("favorite"):
            return False
        if search:
            hay = f"{a.get('name','')} {a.get('publisher','')} {a['path']}".lower()
            if search not in hay:
                return False
        return True
    return [a for a in apps if match(a)]


def _populate_app_tree(tree, controller, apps: list[dict], pal, window) -> None:
    tree.delete(*tree.get_children())
    for app in apps:
        icon_path = app.get("icon_cache") or ""
        photo = window.icon_cache.get(icon_path, 24)
        fav = "★ " if app.get("favorite") else ""
        policy = _policy_label(app)
        status = _status_label(app)
        tree.insert("", "end", iid=app["id"], text=f"{fav}{app['name']}", image=photo,
                    values=(app.get("publisher") or "—", app["path"], policy, status))


def _tree_row_action(page: Page, tree) -> None:
    sel = tree.selection()
    if not sel:
        page.window.toast("Select an application first", "warning")
        return
    app = page.controller.db.get_app(sel[0])
    if app:
        _open_app_controls(page, app)


def _tree_delete_selected(page: Page, tree) -> None:
    sel = tree.selection()
    for app_id in sel:
        app = page.controller.db.get_app(app_id)
        if app and messagebox.askyesno("Remove Application",
                                       f"Remove {app['name']}?", parent=page.window.root):
            page.controller.remove_app(app_id)
    page.window.refresh_pages()


def _tree_toggle_fav(page: Page, tree) -> None:
    sel = tree.selection()
    for app_id in sel:
        app = page.controller.db.get_app(app_id)
        if app:
            page.controller.set_favorite(app_id, not app.get("favorite"))
    page.window.refresh_pages()


def _set_password(page: Page, tree) -> None:
    from applocker.ui import passwords
    sel = tree.selection()
    if not sel:
        page.window.toast("Select an application first", "warning")
        return
    app = page.controller.db.get_app(sel[0])
    dlg = passwords.AppPasswordDialog(page.window.root, page.controller, page.pal, app)
    dlg.show()
    page.window.refresh_pages()


# --------------------------------------------------------------------------- #
# Groups
# --------------------------------------------------------------------------- #
def build_groups(master, controller: AppController, window) -> tk.Widget:
    page = Page(master, controller, window)
    pal = page.pal
    groups = controller.db.list_groups()

    _header(page, "Groups", "Apply policies to a whole set of applications at once.")
    ttk.Button(page, text="+ New Group", style="TButton",
               command=lambda: _new_group(page)).pack(anchor="w", pady=(0, 12))

    if not groups:
        EmptyState(page, "No groups yet",
                   "Create a group like 'Games' or 'Social Media' and apply a single schedule to all its applications.",
                   pal, icon_text="🗂️", action_text="+ New Group",
                   action=lambda: _new_group(page)).pack(fill="both", expand=True)
    else:
        host = ttk.Frame(page, style="TFrame")
        host.pack(fill="both", expand=True)
        for group in groups:
            row = Card(host, pal, radius=12, height=88)
            row.pack(fill="x", pady=4)
            inner = row.body()
            inner.columnconfigure(1, weight=1)
            tk.Canvas(inner, width=14, height=14, bg=pal.surface, highlightthickness=0
                      ).create_oval(2, 2, 12, 12, fill=group.get("color", pal.accent), outline="")
            swatch = tk.Canvas(inner, width=14, height=14, bg=pal.surface, highlightthickness=0)
            swatch.create_oval(2, 2, 12, 12, fill=group.get("color", pal.accent), outline="")
            swatch.grid(row=0, column=0, rowspan=2, padx=(0, 12), pady=8)
            ttk.Label(inner, text=group["name"], style="TLabel",
                      font=("Segoe UI Semibold", 11)).grid(row=0, column=1, sticky="sw")
            members = controller.db.group_apps(group["id"])
            gpol = _policy_label(group)
            ttk.Label(inner, text=f"{len(members)} app(s) · {gpol}",
                      style="Faint.TLabel").grid(row=1, column=1, sticky="nw")
            ttk.Button(inner, text="Manage", style="Ghost.TButton",
                       command=lambda g=group: _manage_group(page, g)).grid(
                row=0, column=2, rowspan=2, padx=(8, 0), sticky="e")

    page.on_status_changed = lambda: None
    return page


def _new_group(page: Page) -> None:
    from applocker.ui.dialogs import GroupDialog
    dlg = GroupDialog(page.window.root, page.controller, page.pal)
    dlg.show()
    page.window.refresh_pages()


def _manage_group(page: Page, group: dict) -> None:
    from applocker.ui.dialogs import GroupManageDialog
    dlg = GroupManageDialog(page.window.root, page.controller, page.pal, group)
    dlg.show()
    page.window.refresh_pages()


# --------------------------------------------------------------------------- #
# Activity
# --------------------------------------------------------------------------- #
def build_activity(master, controller: AppController, window) -> tk.Widget:
    page = Page(master, controller, window)
    pal = page.pal
    events = controller.db.list_events(limit=1000)

    _header(page, "Activity", "Security and policy events recorded by AppLocker.")

    top = ttk.Frame(page, style="TFrame")
    top.pack(fill="x", pady=(0, 10))
    ttk.Label(top, text="Filter:", style="Muted.TLabel").pack(side="left")
    type_var = tk.StringVar(value="all")
    combo = ttk.Combobox(top, textvariable=type_var, state="readonly", width=18,
                         values=["all"] + sorted({e["type"] for e in events}))
    combo.pack(side="left", padx=(8, 12))
    search = ttk.Entry(top, style="TEntry")
    search.pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=3)
    ttk.Button(top, text="Clear Log", style="Danger.TButton",
               command=lambda: _clear_events(page)).pack(side="right")

    if not events:
        EmptyState(page, "No activity yet",
                   "Events such as blocked launches and policy changes will appear here.",
                   pal, icon_text="📋").pack(fill="both", expand=True)
        page.on_status_changed = lambda: None
        return page

    host = ttk.Frame(page, style="TFrame")
    host.pack(fill="both", expand=True)
    cols = ("ts", "type", "app", "message")
    tree = ttk.Treeview(host, columns=cols, show="headings")
    for col, label, width in [("ts", "Time", 150), ("type", "Type", 130),
                              ("app", "Application", 180), ("message", "Message", 330)]:
        tree.heading(col, text=label)
        tree.column(col, width=width, minwidth=80)
    vsb = ttk.Scrollbar(host, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")

    def _populate(*_a):
        tree.delete(*tree.get_children())
        t = type_var.get()
        s = search.get().lower()
        for ev in events:
            if t != "all" and ev["type"] != t:
                continue
            if s and s not in (ev.get("message", "") + ev.get("app_id", "")).lower():
                continue
            app_name = ev.get("app_id", "")
            app = controller.db.get_app(ev["app_id"]) if ev.get("app_id") else None
            if app:
                app_name = app["name"]
            tree.insert("", "end", values=(_monthday(ev["ts"]), ev["type"],
                                           app_name, ev["message"]))
    _populate()
    type_var.trace_add("write", lambda *_: _populate())
    search.bind("<KeyRelease>", lambda _e: _populate())

    page.on_status_changed = lambda: None
    return page


def _clear_events(page: Page) -> None:
    if messagebox.askyesno("Clear Activity Log",
                           "Delete all recorded activity events?", parent=page.window.root):
        page.controller.db.clear_events()
        page.window.toast("Activity log cleared", "info")
        page.window.refresh_pages()


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #
def build_settings(master, controller: AppController, window) -> tk.Widget:
    page = _SettingsPage(master, controller, window)
    page._build()
    return page


class _SettingsPage(Page):
    def _build(self):
        pal = self.pal
        _header(self, "Settings", "General, security, protection, notifications and advanced options.")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        general = ttk.Frame(nb, style="TFrame")
        nb.add(general, text=" General ")
        security = ttk.Frame(nb, style="TFrame")
        nb.add(security, text=" Security ")
        protection = ttk.Frame(nb, style="TFrame")
        nb.add(protection, text=" Protection ")
        notifications = ttk.Frame(nb, style="TFrame")
        nb.add(notifications, text=" Notifications ")
        appearance = ttk.Frame(nb, style="TFrame")
        nb.add(appearance, text=" Appearance ")
        advanced = ttk.Frame(nb, style="TFrame")
        nb.add(advanced, text=" Advanced ")

        self._build_general(general)
        self._build_security(security)
        self._build_protection(protection)
        self._build_notifications(notifications)
        self._build_appearance(appearance)
        self._build_advanced(advanced)

    def _section(self, parent, title: str):
        ttk.Label(parent, text=title, style="Section.TLabel").pack(anchor="w", pady=(12, 6))

    def _setting_row(self, parent, title: str, subtitle: str = ""):
        row = ttk.Frame(parent, style="TFrame")
        row.pack(fill="x", pady=(6, 0))
        left = ttk.Frame(row, style="TFrame")
        left.pack(side="left", fill="x", expand=True)
        ttk.Label(left, text=title, style="TLabel").pack(anchor="w")
        if subtitle:
            ttk.Label(left, text=subtitle, style="Faint.TLabel", wraplength=520).pack(anchor="w")
        return row

    def _build_general(self, parent):
        self._section(parent, "General")
        row = self._setting_row(parent, "Start with Windows",
                                "Launch AppLocker in the background when Windows starts (user-level, no admin required).")
        startup = self.controller.get_setting("start_with_windows", False)
        from applocker.ui.widgets import Toggle
        Toggle(row, self.pal, bool(startup), lambda v: self._set_startup(v)).pack(side="right")

        row = self._setting_row(parent, "Minimize to tray",
                                "Close the dashboard window to the system tray instead of quitting.")
        min_tray = self.controller.get_setting("minimize_to_tray", True)
        Toggle(row, self.pal, bool(min_tray), lambda v: self.controller.set_setting("minimize_to_tray", v)).pack(side="right")

        row = self._setting_row(parent, "Close to tray",
                                "Keep monitoring in the background when the window is closed.")
        close_tray = self.controller.get_setting("close_to_tray", True)
        Toggle(row, self.pal, bool(close_tray), lambda v: self.controller.set_setting("close_to_tray", v)).pack(side="right")

    def _set_startup(self, enabled: bool) -> None:
        ok = set_startup_enabled(enabled)
        self.controller.set_setting("start_with_windows", bool(enabled))
        self.window.toast("Startup updated" if ok else "Could not update startup", "success" if ok else "warning")

    def _build_security(self, parent):
        self._section(parent, "Authentication")
        row = self._setting_row(parent, "Session timeout",
                                "Re-authenticate after inactivity (0 = never).")
        timeout = self.controller.get_setting("session_timeout", 300)
        spin = ttk.Spinbox(row, from_=0, to=120, width=6,
                           textvariable=tk.StringVar(value=str(timeout)))
        ttk.Label(row, text="minutes", style="Faint.TLabel").pack(side="right", padx=(6, 0))
        spin.pack(side="right")
        spin.bind("<FocusOut>", lambda _e, s=spin: self.controller.set_setting(
            "session_timeout", int(s.get() or 0)))

        row = self._setting_row(parent, "Failed attempt lockout",
                                "Temporarily block authentication after repeated failures.")
        attempts = self.controller.get_setting("max_attempts", 5)
        lockout = self.controller.get_setting("lockout_seconds", 90)
        ttk.Label(row, text=f"after {attempts} attempts · {lockout}s lockout",
                  style="Muted.TLabel").pack(side="right")

        self._section(parent, "App passwords")
        row = self._setting_row(parent, "Password mode",
                                "Each protected app can have its own password, or fall back to the master password.")
        ttk.Label(row, text=self.controller.get_setting("app_password_mode", "per-app"),
                  style="Muted.TLabel").pack(side="right")

        self._section(parent, "Recovery")
        row = self._setting_row(parent, "View recovery key",
                                "Your key can restore access if you forget the master password.")
        ttk.Button(row, text="Show", style="Ghost.TButton",
                   command=self._show_recovery_key).pack(side="right")
        row = self._setting_row(parent, "Change master password", "")
        ttk.Button(row, text="Change…", style="Ghost.TButton",
                   command=self._change_master).pack(side="right")

    def _show_recovery_key(self):
        from applocker.ui.dialogs import RecoveryKeyDialog
        dlg = RecoveryKeyDialog(self.window.root, self.controller, self.pal)
        dlg.show()

    def _change_master(self):
        from applocker.ui.dialogs import ChangeMasterDialog
        dlg = ChangeMasterDialog(self.window.root, self.controller, self.pal)
        dlg.show()

    def _build_protection(self, parent):
        self._section(parent, "Default protection")
        row = self._setting_row(parent, "Default policy for new apps",
                                "When you add an application, apply this policy by default.")
        default_policy = self.controller.get_setting("default_policy", "always")
        combo = ttk.Combobox(row, state="readonly", width=16,
                             values=["always", "time", "schedule", "none"])
        combo.set(default_policy)
        combo.pack(side="right")
        combo.bind("<<ComboboxSelected>>",
                   lambda _e: self.controller.set_setting("default_policy", combo.get()))

        row = self._setting_row(parent, "Temporary unlock default",
                                "Minutes granted when you tap 'Unlock N min' from the lock screen.")
        temp = self.controller.get_setting("temp_unlock_default", 15)
        spin = ttk.Spinbox(row, from_=1, to=480, width=6, textvariable=tk.StringVar(value=str(temp)))
        spin.pack(side="right")
        ttk.Label(row, text="minutes", style="Faint.TLabel").pack(side="right", padx=(6, 0))
        spin.bind("<FocusOut>", lambda _e, s=spin: self.controller.set_setting(
            "temp_unlock_default", int(s.get() or 15)))

        row = self._setting_row(parent, "Polling interval (ms)",
                                "How often the background monitor checks for protected apps. Lower is faster but uses more CPU.")
        poll = self.controller.get_setting("poll_interval_ms", 1200)
        spin = ttk.Spinbox(row, from_=500, to=5000, increment=100, width=6,
                           textvariable=tk.StringVar(value=str(poll)))
        spin.pack(side="right")
        spin.bind("<FocusOut>", lambda _e, s=spin: self.controller.set_setting(
            "poll_interval_ms", int(s.get() or 1200)))

    def _build_notifications(self, parent):
        self._section(parent, "Windows notifications")
        for key, label, sub in [
            ("notify_blocked", "Blocked launch alerts", "Show a notification when a protected app is blocked."),
            ("notify_failed", "Failed attempt alerts", "Notify when repeated unlock failures are detected."),
            ("notify_protection", "Protection events", "Notify on pause, resume, and quick-lock."),
            ("notify_startup", "Startup notifications", "Confirm when AppLocker starts in the background."),
        ]:
            row = self._setting_row(parent, label, sub)
            from applocker.ui.widgets import Toggle
            val = self.controller.get_setting(key, False)
            Toggle(row, self.pal, bool(val), lambda v, k=key: self.controller.set_setting(k, v)).pack(side="right")

    def _build_appearance(self, parent):
        self._section(parent, "Theme")
        theme = self.controller.get_setting("theme", "system")
        var = tk.StringVar(value=theme)
        row = ttk.Frame(parent, style="TFrame")
        row.pack(fill="x", pady=(4, 0))
        for label, value in [("Light", "light"), ("Dark", "dark"), ("System", "system")]:
            tk.Radiobutton(row, text=label, value=value, variable=var, bg=self.pal.bg,
                           fg=self.pal.text, selectcolor=self.pal.surface_alt,
                           activebackground=self.pal.bg, activeforeground=self.pal.text,
                           font=("Segoe UI", 10),
                           command=lambda: (self.controller.set_setting("theme", var.get()),
                                            self.window.refresh_pages())).pack(side="left", padx=(0, 18))

        self._section(parent, "Accent color")
        accent = self.controller.get_setting("accent_color", "system")
        avar = tk.StringVar(value=accent)
        row = ttk.Frame(parent, style="TFrame")
        row.pack(fill="x", pady=(4, 0))
        for label, value in [("System", "system"), ("Azure", "#0b6bce"), ("Teal", "#0e9f8a"),
                             ("Emerald", "#178a3f"), ("Rose", "#cb3e6b"), ("Amber", "#b25d00")]:
            tk.Radiobutton(row, text=label, value=value, variable=avar, bg=self.pal.bg,
                           fg=self.pal.text, selectcolor=self.pal.surface_alt,
                           activebackground=self.pal.bg, activeforeground=self.pal.text,
                           font=("Segoe UI", 9),
                           command=lambda: (self.controller.set_setting("accent_color", avar.get()),
                                            self.window.refresh_pages())).pack(side="left", padx=(0, 12))

    def _build_advanced(self, parent):
        self._section(parent, "Data & diagnostics")
        row = self._setting_row(parent, "Data directory",
                                "All AppLocker data lives here. Secrets are encrypted; never share this folder.")
        ttk.Label(row, text=_data_dir(), style="Muted.TLabel").pack(side="right")

        row = self._setting_row(parent, "Diagnostics", "Logs help diagnose issues. No passwords are ever written to logs.")
        btns = ttk.Frame(row, style="TFrame")
        btns.pack(side="right")
        ttk.Button(btns, text="Export Diagnostics…", style="Ghost.TButton",
                   command=self._export_diagnostics).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text="Run Integrity Check", style="Ghost.TButton",
                   command=self._integrity_check).pack(side="left")

        self._section(parent, "Backup")
        row = self._setting_row(parent, "Configuration backup",
                                "Export or import policies, groups and settings. Never includes passwords.")
        btns = ttk.Frame(row, style="TFrame")
        btns.pack(side="right")
        ttk.Button(btns, text="Export…", style="Ghost.TButton",
                   command=self._export_config).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text="Import…", style="Ghost.TButton",
                   command=self._import_config).pack(side="left")


    def _export_diagnostics(self):
        from datetime import datetime
        default = os.path.join(_data_dir(), f"applocker-diagnostics-{datetime.now():%Y%m%d-%H%M%S}.txt")
        path = filedialog.asksaveasfilename(parent=self.window.root, defaultextension=".txt",
                                            initialfile=os.path.basename(default),
                                            initialdir=_data_dir(), title="Export Diagnostics")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(logging_snapshot())
                self.window.toast("Diagnostics exported", "success")
            except OSError as exc:
                messagebox.showerror("Export Diagnostics", str(exc), parent=self.window.root)

    def _integrity_check(self):
        ok = self.controller.db.integrity_check()
        self.window.toast("Integrity check passed" if ok else "Integrity check FAILED — configuration may be corrupted",
                          "success" if ok else "error")

    def _export_config(self):
        import json
        from datetime import datetime
        path = filedialog.asksaveasfilename(parent=self.window.root, defaultextension=".json",
                                            initialfile=f"applocker-config-{datetime.now():%Y%m%d}.json",
                                            initialdir=_data_dir(), title="Export Configuration")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(self.controller.export_config(), fh, indent=2, default=str)
                self.window.toast("Configuration exported", "success")
            except OSError as exc:
                messagebox.showerror("Export", str(exc), parent=self.window.root)

    def _import_config(self):
        import json
        path = filedialog.askopenfilename(parent=self.window.root, title="Import Configuration",
                                          filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Import", f"Could not read configuration: {exc}", parent=self.window.root)
            return
        if not messagebox.askyesno("Import Configuration",
                                   "Importing will REPLACE current applications, groups and settings.\n"
                                   "Passwords and the recovery key are not imported.\n\nContinue?",
                                   parent=self.window.root):
            return
        self.controller.import_config(data, replace=True)
        self.window.toast("Configuration imported", "success")
        self.window.refresh_pages()


def _data_dir() -> str:
    from applocker.util.paths import get_platform_data_dir
    return get_platform_data_dir()


# --------------------------------------------------------------------------- #
# About
# --------------------------------------------------------------------------- #
def build_about(master, controller: AppController, window) -> tk.Widget:
    page = Page(master, controller, window)
    pal = page.pal
    _header(page, "About", "AppLocker — Modern Windows Application Access Control")

    from applocker.version import APP_AUTHOR, APP_LICENSE, APP_TAGLINE, APP_URL, APP_VERSION

    hero = Card(page, pal, radius=14, height=150)
    hero.pack(fill="x")
    inner = hero.body()
    logo = window.icon_cache.get(_brand_png(), 72)
    if logo:
        tk.Label(inner, image=logo, bg=pal.surface).pack(side="left", padx=(0, 18))
        inner.logo = logo
    text = ttk.Frame(inner, style="Card.TFrame")
    text.pack(side="left", fill="both", expand=True)
    ttk.Label(text, text=APP_TAGLINE, style="TLabel",
              font=("Segoe UI Semibold", 14)).pack(anchor="w")
    ttk.Label(text, text=f"Version {APP_VERSION} · MIT License", style="Faint.TLabel").pack(anchor="w", pady=(2, 0))

    body = ttk.Frame(page, style="TFrame")
    body.pack(fill="both", expand=True, pady=(16, 0))
    ttk.Label(body, text="Security model", style="Section.TLabel").pack(anchor="w", pady=(6, 4))
    ttk.Label(body, text=(
        "AppLocker is a user-space privacy and parental-control utility. It blocks protected\n"
        "applications at launch using salted, memory-hard password verification; all secrets are"
        "\nencrypted at rest with DPAPI-protected keys. It is a convenience layer, not kernel-level"
        "\nsecurity: a user with administrator rights, Safe Mode, or a malicious driver can bypass it."
    ), style="Faint.TLabel", justify="left").pack(anchor="w")

    ttk.Label(body, text="Provenance", style="Section.TLabel").pack(anchor="w", pady=(14, 4))
    ttk.Label(body, text=(
        "Rewritten and modernized from the upstream AppLocker\n"
        f"({APP_URL}) under the MIT license. Original work © 2025 Hachiki."
    ), style="Faint.TLabel", justify="left").pack(anchor="w")

    ttk.Label(body, text="Acknowledgements", style="Section.TLabel").pack(anchor="w", pady=(14, 4))
    ttk.Label(body, text=(
        "Python, Tkinter, Pillow, PyInstaller, cryptography, pystray, pywin32.\n"
        "Icons are generated in-vector by AppLocker itself — no third-party clip art."
    ), style="Faint.TLabel", justify="left").pack(anchor="w")

    page.on_status_changed = lambda: None
    return page


_BRAND_PNG: Optional[str] = None


def _brand_png() -> str:
    global _BRAND_PNG
    if _BRAND_PNG is None:
        from applocker.util import paths
        _BRAND_PNG = paths.resource_path(os.path.join("assets", "png", "applocker_256x256.png"))
    return _BRAND_PNG if os.path.exists(_BRAND_PNG) else ""


def build_empty(master, controller: AppController, window, title: str = "", msg: str = "") -> tk.Widget:
    page = Page(master, controller, window)
    EmptyState(page, title or "Nothing here", msg or "", window.pal).pack(fill="both", expand=True)
    return page