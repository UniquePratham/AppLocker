"""Aegis screens, built with CustomTkinter.

Each ``build_*`` function returns a frame that fills the content host. All data
is read from ``AppController``; all mutations go back through it.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog
from typing import Callable

import customtkinter as ctk

from applocker.core.app import AppController
from applocker.ui.components import (
    AppRow,
    Card,
    DangerButton,
    EmptyState,
    PrimaryButton,
    SearchBox,
    SecondaryButton,
    SectionHeader,
    StatTile,
    StatusPill,
)
from applocker.ui.tokens import RADIUS, SPACE, TYPE

POLICY_LABELS = {
    "always": "Always",
    "time": "Allowed hours",
    "schedule": "Schedule",
    "none": "Not protected",
}


def _scroll(parent, pal: dict) -> ctk.CTkScrollableFrame:
    return ctk.CTkScrollableFrame(
        parent, fg_color="transparent", corner_radius=0,
        scrollbar_button_color=pal["border"],
        scrollbar_button_hover_color=pal["border_strong"],
    )

# --------------------------------------------------------------------------- #
# Home
# --------------------------------------------------------------------------- #
def build_home(master, controller: AppController, window) -> ctk.CTkFrame:
    pal = window.pal
    page = ctk.CTkFrame(master, fg_color="transparent")

    header = ctk.CTkFrame(page, fg_color="transparent")
    header.pack(fill="x", pady=(0, SPACE["xl"]))
    SectionHeader(
        header, pal, "Dashboard",
        "Security overview and quick control for protected applications.",
    ).pack(side="left", fill="x", expand=True)

    apps = controller.db.list_apps()
    protected = [a for a in apps if a.get("policy") != "none"]
    status = controller.protection_status()
    blocked = controller.db.count_events(event_type="blocked")
    total_events = controller.db.event_count()

    hero = Card(page, pal)
    hero.pack(fill="x", pady=(0, SPACE["lg"]))
    body = hero.body()

    top = ctk.CTkFrame(body, fg_color="transparent")
    top.pack(fill="x")

    kind = {"active": "success", "paused": "warning"}.get(status, "danger")
    label = {"active": "Protection Active", "paused": "Protection Paused"}.get(
        status, "Monitoring Problem"
    )
    StatusPill(top, pal, label, kind).pack(side="left")

    if status == "paused":
        remaining = controller.pause.remaining()
        if remaining > 0:
            mm, ss = divmod(remaining, 60)
            ctk.CTkLabel(
                top, text=f"{mm:02d}:{ss:02d} remaining", font=TYPE["small"],
                text_color=pal["warning"]
            ).pack(side="left", padx=SPACE["md"])

    ctk.CTkLabel(
        top, text=f"{len(protected)} protected", font=TYPE["small"],
        text_color=pal["text_muted"]
    ).pack(side="right")

    actions = ctk.CTkFrame(body, fg_color="transparent")
    actions.pack(fill="x", pady=(SPACE["lg"], 0))

    PrimaryButton(
        actions, pal, "+  Add Application",
        command=lambda: _add_app_dialog(window, controller),
    ).pack(side="left", padx=(0, SPACE["sm"]))

    SecondaryButton(
        actions, pal, "Lock All",
        command=lambda: _lock_all(window, controller),
    ).pack(side="left", padx=(0, SPACE["sm"]))

    if status == "active":
        SecondaryButton(
            actions, pal, "Pause Protection",
            command=lambda: _pause_dialog(window, controller),
        ).pack(side="left")
    else:
        SecondaryButton(
            actions, pal, "Resume Protection",
            command=lambda: _resume(window, controller),
        ).pack(side="left")

    stats = ctk.CTkFrame(page, fg_color="transparent")
    stats.pack(fill="x", pady=(0, SPACE["lg"]))
    for i in range(3):
        stats.grid_columnconfigure(i, weight=1)

    StatTile(stats, pal, str(len(protected)), "Protected applications").grid(
        row=0, column=0, sticky="ew", padx=(0, SPACE["md"])
    )
    StatTile(stats, pal, str(blocked), "Blocked attempts", pal["danger"]).grid(
        row=0, column=1, sticky="ew", padx=(0, SPACE["md"])
    )
    StatTile(stats, pal, str(total_events), "Total events").grid(
        row=0, column=2, sticky="ew"
    )

    list_header = ctk.CTkFrame(page, fg_color="transparent")
    list_header.pack(fill="x", pady=(SPACE["sm"], SPACE["sm"]))
    ctk.CTkLabel(
        list_header, text="Protected applications", font=TYPE["heading"],
        text_color=pal["text"], anchor="w"
    ).pack(side="left")
    ctk.CTkButton(
        list_header, text="View all", font=TYPE["small"], height=26, width=80,
        fg_color="transparent", hover_color=pal["surface_hover"],
        text_color=pal["accent"], command=lambda: window.show_page("applications"),
    ).pack(side="right")

    if not protected:
        EmptyState(
            page, pal, "▣", "No protected applications yet",
            "Add an application to start protecting it.",
            action=lambda: _add_app_dialog(window, controller),
            action_text="Add your first application",
        ).pack(fill="both", expand=True)
    else:
        listing = ctk.CTkFrame(page, fg_color="transparent")
        listing.pack(fill="both", expand=True)
        for app in protected[:6]:
            icon = window.icon_cache.get(app.get("icon_cache") or "", 32)
            AppRow(
                listing, pal, app, icon=icon,
                on_click=lambda a: _app_details(window, controller, a),
                on_toggle=lambda a, on: _toggle_app(window, controller, a, on),
            ).pack(fill="x", pady=(0, SPACE["sm"]))

    return page

# --------------------------------------------------------------------------- #
# Applications
# --------------------------------------------------------------------------- #
def build_applications(master, controller: AppController, window) -> ctk.CTkFrame:
    pal = window.pal
    page = ctk.CTkFrame(master, fg_color="transparent")

    header = ctk.CTkFrame(page, fg_color="transparent")
    header.pack(fill="x", pady=(0, SPACE["lg"]))
    SectionHeader(
        header, pal, "Applications", "Manage which applications Aegis protects."
    ).pack(side="left", fill="x", expand=True)
    PrimaryButton(
        header, pal, "+  Add Application",
        command=lambda: _add_app_dialog(window, controller),
    ).pack(side="right")

    toolbar = ctk.CTkFrame(page, fg_color="transparent")
    toolbar.pack(fill="x", pady=(0, SPACE["md"]))

    search = SearchBox(toolbar, pal, "Search applications…")
    search.pack(side="left", fill="x", expand=True, padx=(0, SPACE["md"]))

    filter_var = tk.StringVar(value="All")
    ctk.CTkSegmentedButton(
        toolbar,
        values=["All", "Protected", "Unprotected"],
        variable=filter_var,
        font=TYPE["small"],
        fg_color=pal["bg_alt"],
        selected_color=pal["accent"],
        selected_hover_color=pal["accent_hover"],
        unselected_color=pal["bg_alt"],
        unselected_hover_color=pal["surface_hover"],
        text_color=pal["text"],
        command=lambda _v: render(),
    ).pack(side="right")

    listing = _scroll(page, pal)
    listing.pack(fill="both", expand=True)

    def render(*_args) -> None:
        for child in listing.winfo_children():
            child.destroy()

        apps = controller.db.list_apps()
        query = search.get().strip().lower()
        mode = filter_var.get()

        if query:
            apps = [a for a in apps if query in a.get("name", "").lower()
                    or query in a.get("path", "").lower()]
        if mode == "Protected":
            apps = [a for a in apps if a.get("policy") != "none"]
        elif mode == "Unprotected":
            apps = [a for a in apps if a.get("policy") == "none"]

        if not apps:
            EmptyState(
                listing, pal, "▣", "No applications found",
                "Try a different search, or add an application.",
                action=lambda: _add_app_dialog(window, controller),
                action_text="Add Application",
            ).pack(fill="both", expand=True, pady=SPACE["2xl"])
            return

        for app in apps:
            icon = window.icon_cache.get(app.get("icon_cache") or "", 32)
            AppRow(
                listing, pal, app, icon=icon,
                on_click=lambda a: _app_details(window, controller, a),
                on_toggle=lambda a, on: _toggle_app(window, controller, a, on),
            ).pack(fill="x", pady=(0, SPACE["sm"]))

    search.bind("<KeyRelease>", render)
    render()
    return page


# --------------------------------------------------------------------------- #
# Groups
# --------------------------------------------------------------------------- #
def build_groups(master, controller: AppController, window) -> ctk.CTkFrame:
    pal = window.pal
    page = ctk.CTkFrame(master, fg_color="transparent")

    header = ctk.CTkFrame(page, fg_color="transparent")
    header.pack(fill="x", pady=(0, SPACE["lg"]))
    SectionHeader(
        header, pal, "Groups", "Bundle applications that share one policy."
    ).pack(side="left", fill="x", expand=True)
    PrimaryButton(
        header, pal, "+  New Group",
        command=lambda: _new_group_dialog(window, controller),
    ).pack(side="right")

    groups = controller.db.list_groups()
    if not groups:
        EmptyState(
            page, pal, "◫", "No groups yet",
            "Groups let several applications share one policy — for example "
            "“Games, weekends only”.",
            action=lambda: _new_group_dialog(window, controller),
            action_text="Create a group",
        ).pack(fill="both", expand=True)
        return page

    listing = _scroll(page, pal)
    listing.pack(fill="both", expand=True)

    for group in groups:
        members = controller.db.group_apps(group["id"])
        card = Card(listing, pal)
        card.pack(fill="x", pady=(0, SPACE["md"]))
        body = card.body()

        top = ctk.CTkFrame(body, fg_color="transparent")
        top.pack(fill="x")

        swatch = ctk.CTkFrame(
            top, width=10, height=10, corner_radius=5,
            fg_color=group.get("color") or pal["accent"],
        )
        swatch.pack(side="left", padx=(0, SPACE["sm"]))
        swatch.pack_propagate(False)

        ctk.CTkLabel(
            top, text=group.get("name", "Group"), font=TYPE["heading"],
            text_color=pal["text"], anchor="w"
        ).pack(side="left")

        ctk.CTkLabel(
            top, text=f"{len(members)} application{'s' if len(members) != 1 else ''}",
            font=TYPE["small"], text_color=pal["text_muted"]
        ).pack(side="left", padx=SPACE["md"])

        ctk.CTkLabel(
            top, text=POLICY_LABELS.get(group.get("policy", "none"), "—"),
            font=TYPE["small"], text_color=pal["text_muted"]
        ).pack(side="right")

        if members:
            names = ", ".join(m.get("name", "") for m in members[:4])
            if len(members) > 4:
                names += f" +{len(members) - 4} more"
            ctk.CTkLabel(
                body, text=names, font=TYPE["caption"], text_color=pal["text_faint"],
                anchor="w", wraplength=760, justify="left"
            ).pack(fill="x", pady=(SPACE["sm"], 0))

    return page

# --------------------------------------------------------------------------- #
# Activity
# --------------------------------------------------------------------------- #
def build_activity(master, controller: AppController, window) -> ctk.CTkFrame:
    pal = window.pal
    page = ctk.CTkFrame(master, fg_color="transparent")

    header = ctk.CTkFrame(page, fg_color="transparent")
    header.pack(fill="x", pady=(0, SPACE["lg"]))
    SectionHeader(
        header, pal, "Activity", "Every block, unlock and policy change."
    ).pack(side="left", fill="x", expand=True)

    SecondaryButton(
        header, pal, "Export CSV",
        command=lambda: _export_activity(window, controller),
    ).pack(side="right", padx=(SPACE["sm"], 0))
    DangerButton(
        header, pal, "Clear",
        command=lambda: _clear_activity(window, controller),
    ).pack(side="right")

    events = controller.db.list_events(limit=300)
    if not events:
        EmptyState(
            page, pal, "◷", "No activity yet",
            "Blocked attempts, unlocks and policy changes will appear here.",
        ).pack(fill="both", expand=True)
        return page

    listing = _scroll(page, pal)
    listing.pack(fill="both", expand=True)

    for event in events:
        row = ctk.CTkFrame(
            listing, fg_color=pal["surface"], border_color=pal["border"],
            border_width=1, corner_radius=RADIUS["sm"],
        )
        row.pack(fill="x", pady=(0, 4))

        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(fill="x", padx=SPACE["md"], pady=SPACE["sm"])

        kind = event.get("event_type", "")
        colour = {
            "blocked": pal["danger"],
            "unlocked": pal["success"],
            "policy": pal["info"],
            "app_added": pal["accent"],
        }.get(kind, pal["text_muted"])

        ctk.CTkLabel(
            inner, text=kind.upper(), font=TYPE["caption"], text_color=colour, width=90,
            anchor="w"
        ).pack(side="left")

        ctk.CTkLabel(
            inner, text=event.get("message", ""), font=TYPE["small"],
            text_color=pal["text"], anchor="w"
        ).pack(side="left", fill="x", expand=True)

        ts = (event.get("created_at") or "").replace("T", " ")[:19]
        ctk.CTkLabel(
            inner, text=ts, font=TYPE["caption"], text_color=pal["text_faint"], width=140,
            anchor="e"
        ).pack(side="right")

    return page


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #
def build_settings(master, controller: AppController, window) -> ctk.CTkFrame:
    pal = window.pal
    page = ctk.CTkFrame(master, fg_color="transparent")

    SectionHeader(
        page, pal, "Settings", "Appearance, security and data."
    ).pack(fill="x", pady=(0, SPACE["lg"]))

    listing = _scroll(page, pal)
    listing.pack(fill="both", expand=True)

    appearance = Card(listing, pal)
    appearance.pack(fill="x", pady=(0, SPACE["md"]))
    body = appearance.body()
    ctk.CTkLabel(
        body, text="Appearance", font=TYPE["heading"], text_color=pal["text"], anchor="w"
    ).pack(fill="x", pady=(0, SPACE["md"]))

    theme_row = ctk.CTkFrame(body, fg_color="transparent")
    theme_row.pack(fill="x", pady=(0, SPACE["sm"]))
    ctk.CTkLabel(
        theme_row, text="Theme", font=TYPE["body"], text_color=pal["text"], width=140, anchor="w"
    ).pack(side="left")
    theme_var = tk.StringVar(value=controller.get_setting("theme", "system"))
    ctk.CTkSegmentedButton(
        theme_row, values=["system", "light", "dark"], variable=theme_var,
        font=TYPE["small"], fg_color=pal["bg_alt"], selected_color=pal["accent"],
        selected_hover_color=pal["accent_hover"], unselected_color=pal["bg_alt"],
        unselected_hover_color=pal["surface_hover"], text_color=pal["text"],
        command=lambda v: _set_theme(window, controller, v),
    ).pack(side="left")

    accent_row = ctk.CTkFrame(body, fg_color="transparent")
    accent_row.pack(fill="x")
    ctk.CTkLabel(
        accent_row, text="Accent", font=TYPE["body"], text_color=pal["text"], width=140, anchor="w"
    ).pack(side="left")
    from applocker.ui.tokens import ACCENTS

    for name, colour in ACCENTS.items():
        ctk.CTkButton(
            accent_row, text="", width=26, height=26, corner_radius=13,
            fg_color=colour, hover_color=colour,
            command=lambda n=name: _set_accent(window, controller, n),
        ).pack(side="left", padx=(0, SPACE["sm"]))

    security = Card(listing, pal)
    security.pack(fill="x", pady=(0, SPACE["md"]))
    body = security.body()
    ctk.CTkLabel(
        body, text="Security", font=TYPE["heading"], text_color=pal["text"], anchor="w"
    ).pack(fill="x", pady=(0, SPACE["md"]))

    for label, command in [
        ("Change master password", lambda: _change_password_dialog(window, controller)),
        ("Show recovery key", lambda: _show_recovery(window, controller)),
        ("Run integrity check", lambda: _integrity_check(window, controller)),
    ]:
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=(0, SPACE["sm"]))
        ctk.CTkLabel(
            row, text=label, font=TYPE["body"], text_color=pal["text"], anchor="w"
        ).pack(side="left", fill="x", expand=True)
        SecondaryButton(row, pal, "Open", command=command, width=80).pack(side="right")

    data = Card(listing, pal)
    data.pack(fill="x", pady=(0, SPACE["md"]))
    body = data.body()
    ctk.CTkLabel(
        body, text="Data", font=TYPE["heading"], text_color=pal["text"], anchor="w"
    ).pack(fill="x", pady=(0, SPACE["md"]))

    for label, command in [
        ("Export configuration", lambda: _export_config(window, controller)),
        ("Import configuration", lambda: _import_config(window, controller)),
    ]:
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=(0, SPACE["sm"]))
        ctk.CTkLabel(
            row, text=label, font=TYPE["body"], text_color=pal["text"], anchor="w"
        ).pack(side="left", fill="x", expand=True)
        SecondaryButton(row, pal, "Open", command=command, width=80).pack(side="right")

    return page


# --------------------------------------------------------------------------- #
# About
# --------------------------------------------------------------------------- #
def build_about(master, controller: AppController, window) -> ctk.CTkFrame:
    pal = window.pal
    page = ctk.CTkFrame(master, fg_color="transparent")

    SectionHeader(page, pal, "About Aegis").pack(fill="x", pady=(0, SPACE["lg"]))

    card = Card(page, pal)
    card.pack(fill="x")
    body = card.body()

    logo = window.icon_cache.get("", 64)
    if logo is not None:
        ctk.CTkLabel(body, text="", image=logo).pack(pady=(0, SPACE["md"]))

    from applocker.version import APP_VERSION

    ctk.CTkLabel(
        body, text="Aegis", font=TYPE["title"], text_color=pal["text"]
    ).pack()
    ctk.CTkLabel(
        body, text=f"Version {APP_VERSION}", font=TYPE["small"], text_color=pal["text_muted"]
    ).pack(pady=(0, SPACE["md"]))
    ctk.CTkLabel(
        body,
        text="Password-protects the applications you choose. When a locked app "
             "launches it is closed and a lock screen appears; the app runs again "
             "only after the correct password is entered.",
        font=TYPE["body"], text_color=pal["text_muted"], wraplength=560, justify="center",
    ).pack(pady=(0, SPACE["md"]))
    ctk.CTkLabel(
        body, text="MIT License · Windows 10 / 11", font=TYPE["caption"],
        text_color=pal["text_faint"]
    ).pack()

    return page

# --------------------------------------------------------------------------- #
# Actions
# --------------------------------------------------------------------------- #
def _toggle_app(window, controller: AppController, app: dict, on: bool) -> None:
    policy = "always" if on else "none"
    controller.set_app_policy(app["id"], policy)
    window.toast(
        f"{app.get('name')} {'protected' if on else 'unprotected'}",
        "success" if on else "info",
    )
    window.refresh_pages()


def _lock_all(window, controller: AppController) -> None:
    controller.lock_all()
    window.toast("All policies reasserted", "success")
    window.refresh_pages()


def _pause_dialog(window, controller: AppController) -> None:
    _ask_password(window, controller, "Pause Protection",
                  "Enter your master password to pause protection.",
                  lambda: _pause_choose(window, controller))


def _pause_choose(window, controller: AppController) -> None:
    pal = window.pal
    dlg = ctk.CTkToplevel(window.root)
    dlg.title("Pause Protection")
    dlg.geometry("360x280")
    dlg.configure(fg_color=pal["bg"])
    dlg.transient(window.root)
    dlg.grab_set()

    ctk.CTkLabel(
        dlg, text="Pause for how long?", font=TYPE["heading"], text_color=pal["text"]
    ).pack(pady=(SPACE["xl"], SPACE["lg"]))

    for label, minutes in [("5 minutes", 5), ("15 minutes", 15),
                           ("30 minutes", 30), ("1 hour", 60)]:
        SecondaryButton(
            dlg, pal, label,
            command=lambda m=minutes: (_pause(window, controller, m), dlg.destroy()),
        ).pack(fill="x", padx=SPACE["xl"], pady=3)

    dlg.after(50, lambda: (dlg.lift(), dlg.focus_force()))


def _pause(window, controller: AppController, minutes: int) -> None:
    controller.pause_protection(minutes)
    window.toast(f"Protection paused for {minutes} min", "info")
    window.refresh_pages()


def _resume(window, controller: AppController) -> None:
    controller.resume_protection()
    window.toast("Protection resumed", "success")
    window.refresh_pages()


def _ask_password(window, controller: AppController, title: str, prompt: str,
                  on_success: Callable) -> None:
    pal = window.pal
    dlg = ctk.CTkToplevel(window.root)
    dlg.title(title)
    dlg.geometry("400x270")
    dlg.configure(fg_color=pal["bg"])
    dlg.transient(window.root)
    dlg.grab_set()

    ctk.CTkLabel(
        dlg, text=title, font=TYPE["title"], text_color=pal["text"]
    ).pack(pady=(SPACE["xl"], SPACE["xs"]))
    ctk.CTkLabel(
        dlg, text=prompt, font=TYPE["small"], text_color=pal["text_muted"],
        wraplength=320, justify="center"
    ).pack(pady=(0, SPACE["md"]))

    entry = ctk.CTkEntry(
        dlg, show="●", font=TYPE["body"], fg_color=pal["bg_alt"],
        border_color=pal["border"], text_color=pal["text"], height=38,
    )
    entry.pack(fill="x", padx=SPACE["xl"])
    entry.focus_set()

    error = ctk.CTkLabel(dlg, text="", font=TYPE["caption"], text_color=pal["danger"])
    error.pack(pady=(SPACE["xs"], 0))

    def submit(*_args) -> None:
        if controller.try_master(entry.get()):
            dlg.destroy()
            on_success()
        else:
            error.configure(text="Incorrect password")
            entry.delete(0, "end")

    entry.bind("<Return>", submit)
    PrimaryButton(dlg, pal, "Continue", command=submit).pack(
        fill="x", padx=SPACE["xl"], pady=SPACE["md"]
    )
    dlg.after(50, lambda: (dlg.lift(), dlg.focus_force()))

def _add_app_dialog(window, controller: AppController) -> None:
    pal = window.pal
    dlg = ctk.CTkToplevel(window.root)
    dlg.title("Add Application")
    dlg.geometry("580x460")
    dlg.configure(fg_color=pal["bg"])
    dlg.transient(window.root)
    dlg.grab_set()

    ctk.CTkLabel(
        dlg, text="Add Application", font=TYPE["title"], text_color=pal["text"]
    ).pack(pady=(SPACE["xl"], SPACE["xs"]))
    ctk.CTkLabel(
        dlg, text="Choose an executable to protect.", font=TYPE["small"],
        text_color=pal["text_muted"]
    ).pack(pady=(0, SPACE["lg"]))

    path_var = tk.StringVar(value="")

    row = ctk.CTkFrame(dlg, fg_color="transparent")
    row.pack(fill="x", padx=SPACE["xl"])
    entry = ctk.CTkEntry(
        row, textvariable=path_var, font=TYPE["small"], fg_color=pal["bg_alt"],
        border_color=pal["border"], text_color=pal["text"], height=36,
    )
    entry.pack(side="left", fill="x", expand=True, padx=(0, SPACE["sm"]))

    def browse() -> None:
        path = filedialog.askopenfilename(
            title="Select an application",
            filetypes=[("Executables", "*.exe"), ("All files", "*.*")],
        )
        if path:
            path_var.set(path)

    SecondaryButton(row, pal, "Browse…", command=browse, width=90).pack(side="right")

    ctk.CTkLabel(
        dlg, text="Or pick an installed application", font=TYPE["small"],
        text_color=pal["text_muted"], anchor="w"
    ).pack(fill="x", padx=SPACE["xl"], pady=(SPACE["lg"], SPACE["xs"]))

    discovered = _scroll(dlg, pal)
    discovered.pack(fill="both", expand=True, padx=SPACE["xl"])

    def load_discovered() -> None:
        try:
            from applocker.core.discovery import discover_all

            apps = discover_all()
        except Exception:  # noqa: BLE001
            apps = []
        seen = set()
        for app in apps[:60]:
            if app.path in seen:
                continue
            seen.add(app.path)
            ctk.CTkButton(
                discovered,
                text=f"{app.name}   ·   {os.path.basename(app.path)}",
                anchor="w", font=TYPE["small"], height=32,
                fg_color="transparent", hover_color=pal["surface_hover"],
                text_color=pal["text"],
                command=lambda p=app.path: path_var.set(p),
            ).pack(fill="x", pady=1)
        if not seen:
            ctk.CTkLabel(
                discovered, text="No installed applications found.",
                font=TYPE["caption"], text_color=pal["text_faint"]
            ).pack(pady=SPACE["lg"])

    dlg.after(100, load_discovered)

    def add() -> None:
        path = path_var.get().strip()
        if not path or not os.path.isfile(path):
            window.toast("Choose a valid executable first", "warning")
            return
        name = os.path.splitext(os.path.basename(path))[0]
        controller.add_app(name=name, path=path, policy="always")
        dlg.destroy()
        window.toast(f"{name} is now protected", "success")
        window.refresh_pages()

    PrimaryButton(dlg, pal, "Protect this application", command=add).pack(
        fill="x", padx=SPACE["xl"], pady=SPACE["md"]
    )
    dlg.after(50, lambda: (dlg.lift(), dlg.focus_force()))


def _app_details(window, controller: AppController, app: dict) -> None:
    pal = window.pal
    dlg = ctk.CTkToplevel(window.root)
    dlg.title(app.get("name", "Application"))
    dlg.geometry("540x500")
    dlg.configure(fg_color=pal["bg"])
    dlg.transient(window.root)
    dlg.grab_set()

    ctk.CTkLabel(
        dlg, text=app.get("name", "Application"), font=TYPE["title"], text_color=pal["text"]
    ).pack(pady=(SPACE["xl"], SPACE["xs"]))
    ctk.CTkLabel(
        dlg, text=app.get("path", ""), font=TYPE["caption"], text_color=pal["text_faint"],
        wraplength=460, justify="center"
    ).pack(pady=(0, SPACE["lg"]))

    body = ctk.CTkFrame(dlg, fg_color="transparent")
    body.pack(fill="both", expand=True, padx=SPACE["xl"])

    ctk.CTkLabel(
        body, text="Protection policy", font=TYPE["subheading"], text_color=pal["text"],
        anchor="w"
    ).pack(fill="x", pady=(0, SPACE["sm"]))

    policy_var = tk.StringVar(value=app.get("policy", "always"))
    ctk.CTkSegmentedButton(
        body, values=["always", "none"], variable=policy_var,
        font=TYPE["small"], fg_color=pal["bg_alt"], selected_color=pal["accent"],
        selected_hover_color=pal["accent_hover"], unselected_color=pal["bg_alt"],
        unselected_hover_color=pal["surface_hover"], text_color=pal["text"],
    ).pack(fill="x", pady=(0, SPACE["lg"]))

    ctk.CTkLabel(
        body, text="Temporary access", font=TYPE["subheading"], text_color=pal["text"],
        anchor="w"
    ).pack(fill="x", pady=(0, SPACE["sm"]))

    temp_row = ctk.CTkFrame(body, fg_color="transparent")
    temp_row.pack(fill="x", pady=(0, SPACE["lg"]))
    for label, minutes in [("5m", 5), ("15m", 15), ("30m", 30), ("60m", 60)]:
        SecondaryButton(
            temp_row, pal, label, width=60,
            command=lambda m=minutes: _temp_unlock(window, controller, app, m, dlg),
        ).pack(side="left", padx=(0, SPACE["sm"]))

    def save() -> None:
        controller.set_app_policy(app["id"], policy_var.get())
        dlg.destroy()
        window.toast("Policy updated", "success")
        window.refresh_pages()

    PrimaryButton(body, pal, "Save", command=save).pack(fill="x", pady=(0, SPACE["sm"]))
    DangerButton(
        body, pal, "Remove application",
        command=lambda: _remove_app(window, controller, app, dlg),
    ).pack(fill="x")

    dlg.after(50, lambda: (dlg.lift(), dlg.focus_force()))


def _temp_unlock(window, controller: AppController, app: dict, minutes: int, dlg) -> None:
    controller.set_temp_unlock(app["id"], minutes)
    dlg.destroy()
    window.toast(f"{app.get('name')} unlocked for {minutes} min", "success")
    window.refresh_pages()


def _remove_app(window, controller: AppController, app: dict, dlg) -> None:
    controller.remove_app(app["id"])
    dlg.destroy()
    window.toast(f"{app.get('name')} removed", "info")
    window.refresh_pages()


def _new_group_dialog(window, controller: AppController) -> None:
    pal = window.pal
    dlg = ctk.CTkToplevel(window.root)
    dlg.title("New Group")
    dlg.geometry("420x270")
    dlg.configure(fg_color=pal["bg"])
    dlg.transient(window.root)
    dlg.grab_set()

    ctk.CTkLabel(
        dlg, text="New Group", font=TYPE["title"], text_color=pal["text"]
    ).pack(pady=(SPACE["xl"], SPACE["md"]))

    name_entry = ctk.CTkEntry(
        dlg, placeholder_text="Group name", font=TYPE["body"], fg_color=pal["bg_alt"],
        border_color=pal["border"], text_color=pal["text"], height=38,
    )
    name_entry.pack(fill="x", padx=SPACE["xl"])
    name_entry.focus_set()

    def create() -> None:
        name = name_entry.get().strip()
        if not name:
            window.toast("Enter a group name", "warning")
            return
        controller.add_group(name=name)
        dlg.destroy()
        window.toast(f"Group “{name}” created", "success")
        window.refresh_pages()

    name_entry.bind("<Return>", lambda _e: create())
    PrimaryButton(dlg, pal, "Create", command=create).pack(
        fill="x", padx=SPACE["xl"], pady=SPACE["lg"]
    )
    dlg.after(50, lambda: (dlg.lift(), dlg.focus_force()))

def _set_theme(window, controller: AppController, value: str) -> None:
    from applocker.ui.tokens import palette, resolve_theme

    controller.set_setting("theme", value)
    window.theme_pref = value
    window.theme = resolve_theme(value)
    window.pal = palette(window.theme, window.accent_pref)
    window.root.configure(fg_color=window.pal["bg"])
    window.refresh_pages()
    window.toast(f"Theme set to {value}", "info")


def _set_accent(window, controller: AppController, name: str) -> None:
    from applocker.ui.tokens import palette

    controller.set_setting("accent_color", name)
    window.accent_pref = name
    window.pal = palette(window.theme, name)
    window.refresh_pages()
    window.toast(f"Accent set to {name}", "info")


def _change_password_dialog(window, controller: AppController) -> None:
    pal = window.pal
    dlg = ctk.CTkToplevel(window.root)
    dlg.title("Change Master Password")
    dlg.geometry("420x360")
    dlg.configure(fg_color=pal["bg"])
    dlg.transient(window.root)
    dlg.grab_set()

    ctk.CTkLabel(
        dlg, text="Change Master Password", font=TYPE["title"], text_color=pal["text"]
    ).pack(pady=(SPACE["xl"], SPACE["md"]))

    old = ctk.CTkEntry(dlg, placeholder_text="Current password", show="●",
                       fg_color=pal["bg_alt"], border_color=pal["border"],
                       text_color=pal["text"], height=38)
    old.pack(fill="x", padx=SPACE["xl"], pady=(0, SPACE["sm"]))
    new = ctk.CTkEntry(dlg, placeholder_text="New password", show="●",
                       fg_color=pal["bg_alt"], border_color=pal["border"],
                       text_color=pal["text"], height=38)
    new.pack(fill="x", padx=SPACE["xl"], pady=(0, SPACE["sm"]))
    confirm = ctk.CTkEntry(dlg, placeholder_text="Confirm new password", show="●",
                           fg_color=pal["bg_alt"], border_color=pal["border"],
                           text_color=pal["text"], height=38)
    confirm.pack(fill="x", padx=SPACE["xl"])
    old.focus_set()

    def submit() -> None:
        if new.get() != confirm.get():
            window.toast("New passwords do not match", "warning")
            return
        if len(new.get()) < 8:
            window.toast("Use at least 8 characters", "warning")
            return
        if controller.change_master(old.get(), new.get()):
            dlg.destroy()
            window.toast("Master password changed", "success")
        else:
            window.toast("Current password is incorrect", "danger")

    PrimaryButton(dlg, pal, "Change password", command=submit).pack(
        fill="x", padx=SPACE["xl"], pady=SPACE["lg"]
    )
    dlg.after(50, lambda: (dlg.lift(), dlg.focus_force()))


def _show_recovery(window, controller: AppController) -> None:
    key = controller.recovery_key()
    pal = window.pal
    dlg = ctk.CTkToplevel(window.root)
    dlg.title("Recovery Key")
    dlg.geometry("480x270")
    dlg.configure(fg_color=pal["bg"])
    dlg.transient(window.root)
    dlg.grab_set()

    ctk.CTkLabel(
        dlg, text="Recovery Key", font=TYPE["title"], text_color=pal["text"]
    ).pack(pady=(SPACE["xl"], SPACE["sm"]))
    ctk.CTkLabel(
        dlg, text="Store this somewhere safe. It resets a forgotten master password.",
        font=TYPE["small"], text_color=pal["text_muted"], wraplength=400, justify="center"
    ).pack(pady=(0, SPACE["md"]))

    box = ctk.CTkEntry(
        dlg, font=TYPE["mono"], fg_color=pal["bg_alt"], border_color=pal["border"],
        text_color=pal["text"], height=40, justify="center",
    )
    box.pack(fill="x", padx=SPACE["xl"])
    box.insert(0, key or "No recovery key set")
    box.configure(state="readonly")

    dlg.after(50, lambda: (dlg.lift(), dlg.focus_force()))


def _integrity_check(window, controller: AppController) -> None:
    ok = controller.db.integrity_check()
    window.toast(
        "Database healthy" if ok else "Issues detected — see logs",
        "success" if ok else "danger",
    )


def _export_config(window, controller: AppController) -> None:
    import json

    path = filedialog.asksaveasfilename(
        title="Export configuration", defaultextension=".json",
        filetypes=[("JSON", "*.json")],
    )
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(controller.export_config(), fh, indent=2)
        window.toast("Configuration exported", "success")
    except Exception as exc:  # noqa: BLE001
        window.toast(f"Export failed: {exc}", "danger")


def _import_config(window, controller: AppController) -> None:
    import json

    path = filedialog.askopenfilename(
        title="Import configuration", filetypes=[("JSON", "*.json")]
    )
    if not path:
        return
    try:
        with open(path, encoding="utf-8") as fh:
            controller.import_config(json.load(fh))
        window.toast("Configuration imported", "success")
        window.refresh_pages()
    except Exception as exc:  # noqa: BLE001
        window.toast(f"Import failed: {exc}", "danger")


def _export_activity(window, controller: AppController) -> None:
    import csv

    path = filedialog.asksaveasfilename(
        title="Export activity", defaultextension=".csv",
        filetypes=[("CSV", "*.csv")],
    )
    if not path:
        return
    try:
        events = controller.db.list_events(limit=10000)
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["timestamp", "event", "message", "app_id"])
            for e in events:
                writer.writerow([e.get("created_at", ""), e.get("event_type", ""),
                                 e.get("message", ""), e.get("app_id", "")])
        window.toast(f"Exported {len(events)} events", "success")
    except Exception as exc:  # noqa: BLE001
        window.toast(f"Export failed: {exc}", "danger")


def _clear_activity(window, controller: AppController) -> None:
    controller.db.clear_events()
    window.toast("Activity cleared", "info")
    window.refresh_pages()