# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Aegis (one-file, windowed EXE)."""

import os
import sys

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

app_dir = os.path.abspath(os.path.join(HOMEPATH and SPECPATH or "", "applocker"))

datas = [
    (os.path.join("applocker", "assets"), "assets"),
]

# CustomTkinter ships theme JSON and fonts as package data; without them the
# frozen build cannot construct a single widget.
datas += collect_data_files("customtkinter")

hiddenimports = (
    collect_submodules("pystray")
    + collect_submodules("win32timezone")
    + ["pystray._win32", "win32gui", "win32con", "win32api", "win32process", "win32event",
       "win32com.shell.shell", "win32com.client"]
)

a = Analysis(
    ["app.py"],
    pathex=[os.path.dirname(SPECPATH)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["IPython", "matplotlib", "numpy"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Aegis",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join("applocker", "assets", "aegis.ico"),
)