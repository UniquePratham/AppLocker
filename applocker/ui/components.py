"""Reusable CustomTkinter components for Aegis.

Every screen is composed from these, so spacing, radius and colour stay
consistent and a theme change propagates everywhere.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk

from applocker.ui.tokens import RADIUS, SPACE, TYPE


class Card(ctk.CTkFrame):
    """A rounded surface panel."""

    def __init__(self, master, pal: dict, padding: int = SPACE["lg"], **kwargs):
        super().__init__(
            master,
            fg_color=pal["surface"],
            border_color=pal["border"],
            border_width=1,
            corner_radius=RADIUS["lg"],
            **kwargs,
        )
        self.pal = pal
        self._pad = padding

    def body(self) -> ctk.CTkFrame:
        """Inner frame with the card's padding applied."""
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=self._pad, pady=self._pad)
        return frame


class SectionHeader(ctk.CTkFrame):
    """Page title plus optional subtitle."""

    def __init__(self, master, pal: dict, title: str, subtitle: str = ""):
        super().__init__(master, fg_color="transparent")
        ctk.CTkLabel(
            self, text=title, font=TYPE["display"], text_color=pal["text"], anchor="w"
        ).pack(fill="x")
        if subtitle:
            ctk.CTkLabel(
                self,
                text=subtitle,
                font=TYPE["body"],
                text_color=pal["text_muted"],
                anchor="w",
                justify="left",
            ).pack(fill="x", pady=(SPACE["xs"], 0))


class StatusPill(ctk.CTkFrame):
    """Coloured dot plus label, used for protection state."""

    def __init__(self, master, pal: dict, text: str, kind: str = "success"):
        super().__init__(master, fg_color="transparent")
        colour = {
            "success": pal["success"],
            "warning": pal["warning"],
            "danger": pal["danger"],
            "info": pal["info"],
        }.get(kind, pal["text_muted"])
        self._dot = ctk.CTkLabel(self, text="●", font=(TYPE["body"][0], 13), text_color=colour)
        self._dot.pack(side="left", padx=(0, SPACE["sm"]))
        self._label = ctk.CTkLabel(
            self, text=text, font=TYPE["body_strong"], text_color=pal["text"]
        )
        self._label.pack(side="left")

    def set(self, text: str, kind: str, pal: dict) -> None:
        colour = {
            "success": pal["success"],
            "warning": pal["warning"],
            "danger": pal["danger"],
            "info": pal["info"],
        }.get(kind, pal["text_muted"])
        self._dot.configure(text_color=colour)
        self._label.configure(text=text)


class StatTile(ctk.CTkFrame):
    """Big number with a caption."""

    def __init__(self, master, pal: dict, value: str, label: str, accent: str | None = None):
        super().__init__(
            master,
            fg_color=pal["surface"],
            border_color=pal["border"],
            border_width=1,
            corner_radius=RADIUS["lg"],
        )
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=SPACE["lg"], pady=SPACE["md"])
        self._value = ctk.CTkLabel(
            inner,
            text=value,
            font=(TYPE["display"][0], 24, "bold"),
            text_color=accent or pal["text"],
            anchor="w",
        )
        self._value.pack(fill="x")
        self._label = ctk.CTkLabel(
            inner, text=label, font=TYPE["small"], text_color=pal["text_muted"], anchor="w"
        )
        self._label.pack(fill="x")

    def set_value(self, value: str) -> None:
        self._value.configure(text=value)


class AppRow(ctk.CTkFrame):
    """One application in a dense list."""

    def __init__(
        self,
        master,
        pal: dict,
        app: dict,
        icon=None,
        on_click: Optional[Callable] = None,
        on_toggle: Optional[Callable] = None,
    ):
        super().__init__(
            master,
            fg_color=pal["surface"],
            border_color=pal["border"],
            border_width=1,
            corner_radius=RADIUS["md"],
            height=64,
        )
        self.pal = pal
        self.app = app
        self._on_click = on_click

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="both", expand=True, padx=SPACE["md"], pady=SPACE["sm"])

        # Icon
        if icon is not None:
            ctk.CTkLabel(row, text="", image=icon, width=36).pack(side="left", padx=(0, SPACE["md"]))
        else:
            ctk.CTkLabel(
                row, text="▣", font=(TYPE["body"][0], 20), text_color=pal["text_faint"], width=36
            ).pack(side="left", padx=(0, SPACE["md"]))

        # Name + path
        text_col = ctk.CTkFrame(row, fg_color="transparent")
        text_col.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(
            text_col, text=app.get("name", "Unknown"), font=TYPE["body_strong"],
            text_color=pal["text"], anchor="w"
        ).pack(fill="x")
        path = app.get("path", "")
        if len(path) > 62:
            path = "…" + path[-60:]
        ctk.CTkLabel(
            text_col, text=path, font=TYPE["caption"], text_color=pal["text_faint"], anchor="w"
        ).pack(fill="x")

        # Policy label
        policy = app.get("policy", "none")
        policy_text = {
            "always": "Always",
            "time": "Allowed hours",
            "schedule": "Schedule",
            "none": "Not protected",
        }.get(policy, policy)
        ctk.CTkLabel(
            row, text=policy_text, font=TYPE["small"], text_color=pal["text_muted"], width=110
        ).pack(side="left", padx=SPACE["md"])

        # Toggle
        self._switch = ctk.CTkSwitch(
            row,
            text="",
            width=44,
            progress_color=pal["accent"],
            button_color=pal["text_muted"],
            button_hover_color=pal["text"],
            command=self._toggle,
        )
        self._switch.pack(side="right", padx=(SPACE["md"], 0))
        if policy != "none":
            self._switch.select()
        else:
            self._switch.deselect()

        # Make the whole row clickable
        for widget in (self, row, text_col):
            widget.bind("<Button-1>", self._clicked)

    def _clicked(self, _event=None) -> None:
        if self._on_click:
            self._on_click(self.app)

    def _toggle(self) -> None:
        if self._on_toggle:
            self._on_toggle(self.app, bool(self._switch.get()))


class EmptyState(ctk.CTkFrame):
    """Friendly placeholder when a list has no items."""

    def __init__(self, master, pal: dict, glyph: str, title: str, body: str, action=None,
                 action_text: str = ""):
        super().__init__(master, fg_color="transparent")
        ctk.CTkLabel(
            self, text=glyph, font=(TYPE["body"][0], 40), text_color=pal["text_faint"]
        ).pack(pady=(SPACE["2xl"], SPACE["sm"]))
        ctk.CTkLabel(self, text=title, font=TYPE["heading"], text_color=pal["text"]).pack()
        ctk.CTkLabel(
            self, text=body, font=TYPE["body"], text_color=pal["text_muted"],
            wraplength=420, justify="center"
        ).pack(pady=(SPACE["xs"], SPACE["lg"]))
        if action:
            ctk.CTkButton(
                self, text=action_text, command=action, font=TYPE["body_strong"],
                fg_color=pal["accent"], hover_color=pal["accent_hover"],
                text_color=pal["accent_text"], corner_radius=RADIUS["md"], height=36,
            ).pack()


class Toast(ctk.CTkFrame):
    """Transient confirmation anchored to the bottom-right."""

    def __init__(self, master, pal: dict, message: str, kind: str = "info"):
        colour = {
            "success": pal["success"],
            "warning": pal["warning"],
            "danger": pal["danger"],
            "info": pal["info"],
        }.get(kind, pal["info"])
        super().__init__(
            master,
            fg_color=pal["surface_active"],
            border_color=colour,
            border_width=1,
            corner_radius=RADIUS["md"],
        )
        ctk.CTkLabel(
            self, text=message, font=TYPE["small"], text_color=pal["text"]
        ).pack(padx=SPACE["lg"], pady=SPACE["md"])


class SearchBox(ctk.CTkEntry):
    """Themed search field with placeholder."""

    def __init__(self, master, pal: dict, placeholder: str = "Search…", **kwargs):
        super().__init__(
            master,
            placeholder_text=placeholder,
            font=TYPE["body"],
            fg_color=pal["bg_alt"],
            border_color=pal["border"],
            text_color=pal["text"],
            placeholder_text_color=pal["text_faint"],
            corner_radius=RADIUS["md"],
            height=36,
            **kwargs,
        )


class PrimaryButton(ctk.CTkButton):
    def __init__(self, master, pal: dict, text: str, command=None, **kwargs):
        super().__init__(
            master,
            text=text,
            command=command,
            font=TYPE["body_strong"],
            fg_color=pal["accent"],
            hover_color=pal["accent_hover"],
            text_color=pal["accent_text"],
            corner_radius=RADIUS["md"],
            height=36,
            **kwargs,
        )


class SecondaryButton(ctk.CTkButton):
    def __init__(self, master, pal: dict, text: str, command=None, **kwargs):
        super().__init__(
            master,
            text=text,
            command=command,
            font=TYPE["body"],
            fg_color=pal["surface_hover"],
            hover_color=pal["surface_active"],
            text_color=pal["text"],
            border_color=pal["border"],
            border_width=1,
            corner_radius=RADIUS["md"],
            height=36,
            **kwargs,
        )


class DangerButton(ctk.CTkButton):
    def __init__(self, master, pal: dict, text: str, command=None, **kwargs):
        super().__init__(
            master,
            text=text,
            command=command,
            font=TYPE["body_strong"],
            fg_color=pal["danger"],
            hover_color=pal["danger"],
            text_color="#ffffff",
            corner_radius=RADIUS["md"],
            height=36,
            **kwargs,
        )