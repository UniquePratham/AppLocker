"""Fluent-inspired design system for AppLocker.

Provides a single source of truth for colors, typography, spacing and radii,
plus the concrete ttk/tk theming used across every surface — dashboard,
applications, groups, activity, settings, lock screen and the setup wizard.

Theme choices: ``light``, ``dark``, ``system`` (follows Windows app theme).

Design tokens are chosen to feel like a modern Windows utility: flat surfaces
with subtle borders, an accent used sparingly, high contrast, consistent
spacing, and rounded (but not comically large) corners.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from dataclasses import dataclass, field


@dataclass
class Palette:
    name: str
    bg: str
    bg_sunken: str
    surface: str
    surface_alt: str
    border: str
    border_strong: str
    text: str
    text_muted: str
    text_faint: str
    accent: str
    accent_hover: str
    accent_active: str
    accent_soft: str
    success: str
    success_soft: str
    warning: str
    warning_soft: str
    danger: str
    danger_soft: str
    info: str
    info_soft: str
    selection: str
    hover_row: str
    focus: str
    shadow: str
    scroll_track: str
    scroll_thumb: str
    input_bg: str
    toggle_off: str
    toggle_knob: str


LIGHT = Palette(
    name="light",
    bg="#f3f6fb",
    bg_sunken="#e8edf5",
    surface="#ffffff",
    surface_alt="#f7f9fd",
    border="#dfe5ee",
    border_strong="#b6c1d0",
    text="#0d1117",
    text_muted="#4e5868",
    text_faint="#7d8796",
    accent="#0b6bce",
    accent_hover="#0c7be2",
    accent_active="#08539f",
    accent_soft="#e6f0fb",
    success="#12863b",
    success_soft="#e4f6ea",
    warning="#b25d00",
    warning_soft="#fff2e0",
    danger="#d02f2f",
    danger_soft="#fdeded",
    info="#0b6f9d",
    info_soft="#e3f4f9",
    selection="#c9e3f9",
    hover_row="#eef4fb",
    focus="#0b6bce",
    shadow="#0f172a1c",
    scroll_track="#0f172a0a",
    scroll_thumb="#0f172a38",
    input_bg="#ffffff",
    toggle_off="#b6c1d0",
    toggle_knob="#ffffff",
)

DARK = Palette(
    name="dark",
    bg="#14161a",
    bg_sunken="#101216",
    surface="#1d2026",
    surface_alt="#23272e",
    border="#31363f",
    border_strong="#4a5160",
    text="#f2f5f9",
    text_muted="#a6aebd",
    text_faint="#6d7688",
    accent="#3d9bff",
    accent_hover="#63b0ff",
    accent_active="#2b82e0",
    accent_soft="#1c3550",
    success="#4ec67a",
    success_soft="#1a3323",
    warning="#f2ad4e",
    warning_soft="#3a2c17",
    danger="#ff6d6d",
    danger_soft="#3a2123",
    info="#57b7de",
    info_soft="#173240",
    selection="#2b4a6e",
    hover_row="#262b33",
    focus="#3d9bff",
    shadow="#00000055",
    scroll_track="#00000033",
    scroll_thumb="#ffffff3a",
    input_bg="#131519",
    toggle_off="#4a5160",
    toggle_knob="#e6eaf0",
)


SYSTEM = "system"


def system_prefers_dark() -> bool:
    """Follow the Windows app-mode setting (AppsUseLightTheme)."""
    try:
        import ctypes
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 0
    except Exception:  # noqa: BLE001
        return False


def resolve_palette(theme: str) -> Palette:
    if theme == "dark":
        return DARK
    if theme == "light":
        return LIGHT
    return DARK if system_prefers_dark() else LIGHT


# --------------------------------------------------------------------------- #
# Fonts
# --------------------------------------------------------------------------- #
_FONT_STACK = ("Segoe UI Variable Text", "Segoe UI", "TkDefaultFont")


def font_size_pt(root: tk.Misc) -> int:
    try:
        return max(8, int(float(str(root.tk.call("tk", "scaling"))) * 9.0))
    except Exception:  # noqa: BLE001
        return 9


def build_fonts(root: tk.Misc) -> dict:
    base = font_size_pt(root)
    return {
        "display": (root, _FONT_STACK, base + 13, "bold"),
        "title": (root, _FONT_STACK, base + 6, "bold"),
        "subtitle": (root, _FONT_STACK, base + 2, "bold"),
        "body": (root, _FONT_STACK, base, "normal"),
        "body_bold": (root, _FONT_STACK, base, "bold"),
        "small": (root, _FONT_STACK, max(8, base - 1), "normal"),
        "small_bold": (root, _FONT_STACK, max(8, base - 1), "bold"),
        "caption": (root, _FONT_STACK, max(8, base - 2), "normal"),
        "mono": (root, ("Cascadia Mono", "Consolas"), base - 1, "normal"),
    }


# --------------------------------------------------------------------------- #
# Table of widget names → colors (for quick JS-free themable styling)
# --------------------------------------------------------------------------- #
def apply_theme(root: tk.Tk, theme: str, fonts: dict, accent: str | None = None) -> Palette:
    """Apply the palette + fonts to the whole widget tree via ttk styles.

    ``accent`` overrides the default accent (user choice in Settings).
    """
    pal = resolve_palette(theme)
    if accent and accent != "system":
        pal = _recolor_accent(pal, accent)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    # Root + defaults
    root.configure(bg=pal.bg, padx=0, pady=0)
    root.option_add("*Background", pal.bg)
    root.option_add("*Foreground", pal.text)

    # ttk fonts
    body_font = (_FONT_STACK, 10)

    style.configure(".", background=pal.bg, foreground=pal.text, bordercolor=pal.border,
                    lightcolor=pal.surface, darkcolor=pal.bg, troughcolor=pal.bg_sunken,
                    font=body_font, focuscolor="#ffffff00")

    # Frames
    style.configure("TFrame", background=pal.bg)
    style.configure("Card.TFrame", background=pal.surface, borderwidth=1, relief="solid")
    style.configure("Surface.TFrame", background=pal.surface)
    style.configure("SurfaceAlt.TFrame", background=pal.surface_alt)

    # PanedWindow / notepads
    style.configure("Left.TPanedwindow", background=pal.bg)
    style.configure("TPanedwindow", background=pal.bg)

    # Labels
    style.configure("TLabel", background=pal.bg, foreground=pal.text, font=body_font)
    style.configure("Card.TLabel", background=pal.surface, foreground=pal.text, font=body_font)
    style.configure("Surface.TLabel", background=pal.surface, foreground=pal.text)
    style.configure("Muted.TLabel", background=pal.surface, foreground=pal.text_muted)
    style.configure("Faint.TLabel", background=pal.surface, foreground=pal.text_faint)
    style.configure("Title.TLabel", background=pal.surface, foreground=pal.text,
                    font=(_FONT_STACK, 15, "bold"))
    style.configure("PageTitle.TLabel", background=pal.bg, foreground=pal.text,
                    font=(_FONT_STACK, 18, "bold"))
    style.configure("Section.TLabel", background=pal.bg, foreground=pal.text,
                    font=(_FONT_STACK, 11, "bold"))
    style.configure("Accent.TLabel", background=pal.surface, foreground=pal.accent)
    style.configure("Success.TLabel", background=pal.surface, foreground=pal.success)
    style.configure("Danger.TLabel", background=pal.surface, foreground=pal.danger)
    style.configure("Warning.TLabel", background=pal.surface, foreground=pal.warning)
    style.configure("Info.TLabel", background=pal.surface, foreground=pal.info)

    # Rounded-ish separator
    style.configure("TSeparator", background=pal.border)

    # Buttons
    style.configure("TButton", background=pal.accent, foreground="#ffffff", font=body_font,
                    padding=(14, 7), borderwidth=0, focusthickness=0, relief="flat")
    style.map("TButton",
              background=[("disabled", pal.surface_alt), ("pressed", pal.accent_active),
                          ("active", pal.accent_hover)],
              foreground=[("disabled", pal.text_faint)])
    style.configure("Secondary.TButton", background=pal.surface_alt, foreground=pal.text)
    style.map("Secondary.TButton",
              background=[("disabled", pal.surface_alt), ("pressed", pal.bg_sunken),
                          ("active", pal.border)],
              foreground=[("disabled", pal.text_faint)])
    style.configure("Ghost.TButton", background=pal.surface, foreground=pal.text)
    style.map("Ghost.TButton",
              background=[("disabled", pal.surface), ("pressed", pal.bg_sunken),
                          ("active", pal.hover_row)],
              foreground=[("disabled", pal.text_faint)])
    style.configure("Danger.TButton", background=pal.danger, foreground="#ffffff")
    style.map("Danger.TButton", background=[("pressed", "#a83232"), ("active", "#e05555")])

    # Entry / Combobox / Spinbox
    for widget in ("TEntry", "TCombobox", "TSpinbox"):
        style.configure(widget, fieldbackground=pal.input_bg, background=pal.input_bg,
                        foreground=pal.text, bordercolor=pal.border, lightcolor=pal.border,
                        darkcolor=pal.border, insertcolor=pal.text, padding=(8, 6))
    style.map("TCombobox", fieldbackground=[("readonly", pal.input_bg)],
              foreground=[("readonly", pal.text)], background=[("active", pal.input_bg)])

    # Checkbutton / Radiobutton
    style.configure("TCheckbutton", background=pal.surface, foreground=pal.text, font=body_font)
    style.map("TCheckbutton", background=[("active", pal.surface)])
    style.configure("TRadiobutton", background=pal.surface, foreground=pal.text, font=body_font)
    style.map("TRadiobutton", background=[("active", pal.surface)])

    # Spinbox arrows
    style.layout(
        "TSpinbox",
        [("Spinbox.field", {"children": [
            ("Spinbox.downarrow", {"side": "right", "sticky": ""}),
            ("Spinbox.uparrow", {"side": "left", "sticky": ""}),
            ("Spinbox.padding", {"children": [("Spinbox.inner", {"children": [
                ("Spinbox.textarea", {"sticky": "we"})]})]})]})],
    )

    # Treeview
    style.configure("Treeview", background=pal.surface, fieldbackground=pal.surface,
                    foreground=pal.text, rowheight=40, borderwidth=0,
                    font=body_font, focusthickness=0)
    style.map("Treeview", background=[("selected", pal.selection)],
              foreground=[("selected", pal.text)])
    style.configure("Treeview.Heading", background=pal.bg_sunken, foreground=pal.text_muted,
                    font=(_FONT_STACK, 9, "bold"), padding=(8, 8), relief="flat")
    style.map("Treeview.Heading", background=[("active", pal.bg)])
    style.configure("Notebook", background=pal.bg, borderwidth=0)
    style.configure("TNotebook.Tab", background=pal.bg_sunken, foreground=pal.text_muted,
                    padding=(18, 8), borderwidth=0)
    style.map("TNotebook.Tab", background=[("selected", pal.surface)],
              foreground=[("selected", pal.accent)])

    # Scrollbars
    style.configure("Vertical.TScrollbar", background=pal.scroll_thumb, troughcolor=pal.bg,
                    borderwidth=0, arrowsize=0, gripcount=0)
    style.map("Vertical.TScrollbar", background=[("active", pal.scroll_thumb), ("pressed", pal.border_strong)])
    style.configure("Horizontal.TScrollbar", background=pal.scroll_thumb, troughcolor=pal.bg,
                    borderwidth=0, arrowsize=0, gripcount=0)
    style.map("Horizontal.TScrollbar", background=[("active", pal.scroll_thumb), ("pressed", pal.border_strong)])

    # Progressbar
    style.configure("TProgressbar", background=pal.accent, troughcolor=pal.bg_sunken,
                    borderwidth=0, thickness=6)

    # Tooltip-ish labels
    style.configure("Status.TLabel", background=pal.accent_soft, foreground=pal.accent,
                    padding=(10, 5), font=(_FONT_STACK, 9, "bold"))
    style.configure("StatusGood.TLabel", background=pal.success_soft, foreground=pal.success,
                    padding=(10, 5), font=(_FONT_STACK, 9, "bold"))
    style.configure("StatusWarn.TLabel", background=pal.warning_soft, foreground=pal.warning,
                    padding=(10, 5), font=(_FONT_STACK, 9, "bold"))
    return pal


def _recolor_accent(pal: Palette, accent: str) -> Palette:
    import copy
    pal = copy.copy(pal)
    pal.accent = accent
    pal.accent_hover = _lighten(accent, 0.10)
    pal.accent_active = _darken(accent, 0.10)
    pal.accent_soft = _soften(accent, pal.surface)
    return pal


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _lighten(hex_color: str, amt: float) -> str:
    r, g, b = _hex_to_rgb(hex_color)
    return "#%02x%02x%02x" % (min(255, int(r + (255 - r) * amt)),
                              min(255, int(g + (255 - g) * amt)),
                              min(255, int(b + (255 - b) * amt)))


def _darken(hex_color: str, amt: float) -> str:
    r, g, b = _hex_to_rgb(hex_color)
    return "#%02x%02x%02x" % (int(r * (1 - amt)), int(g * (1 - amt)), int(b * (1 - amt)))


def _soften(hex_color: str, surface: str) -> str:
    """Blend accent toward the surface for a soft background tint."""
    import colorsys
    r, g, b = _hex_to_rgb(hex_color)
    sr, sg, sb = _hex_to_rgb(surface)
    # Convert accent to HSL and lighten strongly.
    h, l, s_ = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    target_l = 0.94 if l < 0.5 else 0.90
    nr, ng, nb = colorsys.hls_to_rgb(h, target_l, s_)
    # Blend with surface by 50% for harmony.
    return "#%02x%02x%02x" % (int(nr * 255 * 0.5 + sr * 0.5),
                              int(ng * 255 * 0.5 + sg * 0.5),
                              int(nb * 255 * 0.5 + sb * 0.5))