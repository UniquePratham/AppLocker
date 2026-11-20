"""Reusable UI widgets for the design system.

Implements small, polished building blocks used across all pages:

* ``Card`` — rounded panel with themed surface + border.
* ``Badge`` — status pill (active / paused / error / success…).
* ``Toggle`` — switch control with animated knob.
* ``EmptyState`` — friendly empty panel with icon + action.
* ``Toast`` — ephemeral in-app notification.
* ``PageHeader`` — consistent page title/subtitle.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from applocker.ui.theme import Palette


class Card(tk.Canvas):
    """A rounded surface panel with themed fill + border.

    Drawn on a Canvas so corners are genuinely rounded; child content is
    hosted via ``create_window`` so normal widget layout still applies.
    """

    def __init__(self, master, pal: Palette, padding: int = 16, radius: int = 12,
                 width: int | None = None, height: int | None = None,
                 fill: str | None = None, border: str | None = None, **kwargs):
        self.pal = pal
        self.radius = radius
        try:
            self.parent_bg = master.cget("bg")
        except tk.TclError:
            self.parent_bg = pal.bg
        super().__init__(master, bg=pal.bg, highlightthickness=0, bd=0, **kwargs)
        self.body_frame = ttk.Frame(self, style="Card.TFrame")
        self._content_id = None
        self._fill = fill or pal.surface
        self._border = border or pal.border
        self.bind("<Configure>", self._redraw, add="+")

    def _redraw(self, _event=None) -> None:
        w = max(0, self.winfo_width())
        h = max(0, self.winfo_height())
        if w == 1 or h == 1:
            return
        self.delete("bg")
        self.create_rounded_rect(0, 0, w, h, self.radius,
                                 fill=self._fill, outline=self._border, width=1, tags=("bg",))
        if self._content_id is None:
            self._content_id = self.create_window(w - 14, h - 14, anchor="se",
                                                  window=self.body_frame, width=max(1, w - 28),
                                                  height=max(1, h - 28))
        else:
            self.coords(self._content_id, w - 14, h - 14)
            self.itemconfigure(self._content_id, width=max(1, w - 28), height=max(1, h - 28))

    def create_rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [x1 + r, y1] + [x2 - r, y1] + [x2, y1] + [x2, y1 + r] + [x2, y2 - r] + \
                 [x2, y2] + [x2 - r, y2] + [x1 + r, y2] + [x1, y2] + [x1, y2 - r] + \
                 [x1, y1 + r] + [x1, y1]
        return self.create_polygon(points, smooth=True, **kwargs)

    def body(self) -> ttk.Frame:
        return self.body_frame


class Badge(ttk.Label):
    """Compact status pill."""

    KINDS = {
        "active": "StatusGood.TLabel",
        "paused": "StatusWarn.TLabel",
        "error": "Danger.TLabel",
        "info": "Status.TLabel",
        "muted": "Faint.TLabel",
    }

    def __init__(self, master, text: str, kind: str = "info", pal: Palette | None = None):
        style = self.KINDS.get(kind, "Status.TLabel")
        super().__init__(master, text=text, style=style)
        self.configure(padding=(10, 4))


class Toggle(ttk.Frame):
    """An on/off switch with a sliding knob.

    Paints itself on a Canvas so it can round the corners and animate.
    """

    def __init__(self, master, pal: Palette, value: bool = False,
                 command: Optional[Callable[[bool], None]] = None, width: int = 40, height: int = 22):
        self.pal = pal
        self.value = value
        self.command = command
        self.width = width
        self.height = height
        super().__init__(master, width=width, height=height)
        self._canvas = tk.Canvas(self, width=width, height=height, bg=pal.surface,
                                 highlightthickness=0, bd=0)
        self._canvas.pack()
        self._canvas.bind("<Button-1>", self._clicked)
        self._draw()

    def _draw(self) -> None:
        c = self._canvas
        c.delete("all")
        r = self.height // 2
        fill = self.pal.accent if self.value else self.pal.toggle_off
        c.create_oval(0, 0, self.width, self.height, fill=fill, outline="")
        c.create_rectangle(r, 0, self.width - r, self.height, fill=fill, outline="")
        knob_x = self.width - self.height + 2 if self.value else 2
        c.create_oval(knob_x, 2, knob_x + self.height - 4, self.height - 2,
                      fill=self.pal.toggle_knob, outline="")

    def _clicked(self, _event=None) -> None:
        self.value = not self.value
        self._draw()
        if self.command:
            self.command(self.value)

    def set(self, value: bool) -> None:
        if value != self.value:
            self.value = value
            self._draw()


class EmptyState(ttk.Frame):
    """A helpful empty-state panel with an optional action button."""

    def __init__(self, master, title: str, subtitle: str, pal: Palette,
                 icon_text: str = "", action_text: str = "", action: Optional[Callable] = None):
        self.pal = pal
        super().__init__(master, style="Surface.TFrame")
        inner = ttk.Frame(self, style="Surface.TFrame")
        inner.grid(row=0, column=0, sticky="nsew", padx=60, pady=50)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        if icon_text:
            ttk.Label(inner, text=icon_text, style="Faint.TLabel",
                      font=(_FONT, 34)).grid(row=0, column=0, pady=(0, 12))
        ttk.Label(inner, text=title, style="TLabel",
                  font=(_FONT, 13, "bold")).grid(row=1, column=0, pady=(0, 4))
        ttk.Label(inner, text=subtitle, style="Faint.TLabel", wraplength=380,
                  justify="center").grid(row=2, column=0, pady=(0, 16))
        if action_text and action:
            ttk.Button(inner, text=action_text, command=action).grid(row=3, column=0)


_FONT = "Segoe UI"


def make_rounded_button(parent: tk.Misc, text: str, pal: Palette,
                        command: Optional[Callable] = None,
                        kind: str = "primary") -> ttk.Button:
    """Return a styled button. ``kind`` ∈ primary/secondary/ghost."""
    if kind == "secondary":
        style = "Secondary.TButton"
    elif kind == "ghost":
        style = "Ghost.TButton"
    else:
        style = "TButton"
    return ttk.Button(parent, text=text, style=style, command=command)


class CheckButton(ttk.Frame):
    """A styled checkbox with a drawn tick (no platform glyphs).

    Paints itself on a Canvas, so the checked state is always a crisp
    white tick on the accent color rather than a theme icon (which some
    Windows styles render as an X).
    """

    def __init__(self, master, text: str, pal: Palette,
                 variable: Optional[tk.BooleanVar] = None,
                 command: Optional[Callable[[bool], None]] = None):
        self.pal = pal
        self.text = text
        self.variable = variable or tk.BooleanVar(value=False)
        self.command = command
        super().__init__(master, style="TFrame")
        self.canvas = tk.Canvas(self, width=20, height=20, bg=pal.bg,
                                highlightthickness=0, bd=0)
        self.canvas.pack(side="left", padx=(0, 8))
        self.label = tk.Label(self, text=text, bg=pal.bg, fg=pal.text,
                              cursor="hand2", font=("Segoe UI", 10), anchor="w")
        self.label.pack(side="left")
        for widget in (self.canvas, self.label, self):
            widget.bind("<Button-1>", self._clicked)
        self._draw()

    def _draw(self) -> None:
        c = self.canvas
        c.delete("all")
        size, o, r = 18, 1, 4
        checked = self.variable.get()
        x1, y1, x2, y2 = o, o, size, size
        pts = [x1 + r, y1] + [x2 - r, y1] + [x2, y1] + [x2, y1 + r] + [x2, y2 - r] + \
              [x2, y2] + [x2 - r, y2] + [x1 + r, y2] + [x1, y2] + [x1, y2 - r] + \
              [x1, y1 + r] + [x1, y1]
        c.create_polygon(pts, smooth=True,
                         fill=self.pal.accent if checked else self.pal.bg,
                         outline=self.pal.accent if checked else self.pal.border_strong,
                         width=1.5)
        if checked:
            c.create_line(o + 4, size * 0.52, o + 7, size * 0.74, o + size - 5, o + 5.5,
                          fill="#ffffff", width=2.2, capstyle="round", joinstyle="round")

    def _clicked(self, _event=None) -> None:
        self.variable.set(not self.variable.get())
        self._draw()
        if self.command:
            self.command(self.variable.get())

    def get(self) -> bool:
        return self.variable.get()

    def set(self, value: bool) -> None:
        if value != self.variable.get():
            self.variable.set(value)
            self._draw()


class Toast(ttk.Frame):
    """A transient in-app message shown near the bottom of the window."""

    def __init__(self, parent: tk.Misc, message: str, kind: str = "info",
                 duration_ms: int = 3200, pal: Palette | None = None):
        super().__init__(parent, style="Card.TFrame")
        bg = "#ffffff"
        fg = "#0d1117"
        if pal:
            if kind == "success":
                bg, fg = pal.success_soft, pal.success
            elif kind == "error":
                bg, fg = pal.danger_soft, pal.danger
            elif kind == "warning":
                bg, fg = pal.warning_soft, pal.warning
            else:
                bg, fg = pal.accent_soft, pal.accent
        self.configure(style="Card.TFrame")
        tk.Frame(self, bg=bg).pack()
        lbl = tk.Label(self, text=message, bg=bg, fg=fg, font=(_FONT, 10),
                       padx=18, pady=10)
        lbl.pack()
        self.message = message

    def show(self) -> None:
        self.lift()
        self.place(relx=0.5, rely=0.97, anchor="s")
        self.after(3200, self.destroy)


class PageHeader(ttk.Frame):
    """Page title + subtitle, consistent across pages."""

    def __init__(self, master, pal: Palette, title: str, subtitle: str = ""):
        super().__init__(master, style="TFrame")
        ttk.Label(self, text=title, style="PageTitle.TLabel").pack(anchor="w")
        if subtitle:
            ttk.Label(self, text=subtitle, style="Faint.TLabel").pack(anchor="w", pady=(2, 0))