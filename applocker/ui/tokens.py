"""Design tokens for the Aegis UI.

One place for colour, spacing, radius and type. Every screen reads from here so
the product stays visually consistent and a theme change is a single edit.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Spacing scale (4px base)
# --------------------------------------------------------------------------- #
SPACE = {
    "xs": 4,
    "sm": 8,
    "md": 12,
    "lg": 16,
    "xl": 24,
    "2xl": 32,
    "3xl": 48,
}

RADIUS = {"sm": 6, "md": 10, "lg": 14, "xl": 18, "pill": 999}

# --------------------------------------------------------------------------- #
# Type scale
# --------------------------------------------------------------------------- #
FONT_FAMILY = "Segoe UI"

TYPE = {
    "display": (FONT_FAMILY, 26, "bold"),
    "title": (FONT_FAMILY, 19, "bold"),
    "heading": (FONT_FAMILY, 15, "bold"),
    "subheading": (FONT_FAMILY, 13, "bold"),
    "body": (FONT_FAMILY, 12),
    "body_strong": (FONT_FAMILY, 12, "bold"),
    "small": (FONT_FAMILY, 11),
    "caption": (FONT_FAMILY, 10),
    "mono": ("Cascadia Mono", 11),
}

# --------------------------------------------------------------------------- #
# Palettes
# --------------------------------------------------------------------------- #
DARK = {
    "bg": "#0f1115",
    "bg_alt": "#151821",
    "surface": "#1a1e28",
    "surface_hover": "#222735",
    "surface_active": "#2a3040",
    "border": "#2b3140",
    "border_strong": "#3a4254",
    "text": "#eef2f8",
    "text_muted": "#9aa4b8",
    "text_faint": "#6b7488",
    "accent": "#3d9bff",
    "accent_hover": "#5aabff",
    "accent_text": "#04121f",
    "success": "#3ddc97",
    "warning": "#f5b544",
    "danger": "#ff5f6d",
    "info": "#7c9cff",
}

LIGHT = {
    "bg": "#f4f6fa",
    "bg_alt": "#eaeef5",
    "surface": "#ffffff",
    "surface_hover": "#f2f5fa",
    "surface_active": "#e6ecf6",
    "border": "#dde3ed",
    "border_strong": "#c3ccdb",
    "text": "#10141c",
    "text_muted": "#5a6478",
    "text_faint": "#8b94a6",
    "accent": "#0b6bce",
    "accent_hover": "#0a5cb0",
    "accent_text": "#ffffff",
    "success": "#0f9d63",
    "warning": "#b8760a",
    "danger": "#d92d3c",
    "info": "#3b5bdb",
}

ACCENTS = {
    "blue": "#3d9bff",
    "violet": "#8b7bff",
    "teal": "#2fd4c4",
    "green": "#3ddc97",
    "amber": "#f5b544",
    "rose": "#ff6b8a",
}


def palette(theme: str = "dark", accent: str = "blue") -> dict:
    """Return the colour map for ``theme`` with the chosen accent applied."""
    pal = dict(DARK if theme == "dark" else LIGHT)
    if accent in ACCENTS:
        pal["accent"] = ACCENTS[accent]
        pal["accent_hover"] = ACCENTS[accent]
    return pal


def resolve_theme(preference: str) -> str:
    """Map a stored preference (light/dark/system) to a concrete theme."""
    if preference in ("light", "dark"):
        return preference
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return "light" if value else "dark"
    except Exception:  # noqa: BLE001
        return "dark"