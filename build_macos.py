#!/usr/bin/env python3
"""Build script for Olga English Coach macOS DMG (no .py source files).

Produces:
  - dist/Olga English Coach.app  (standalone, embedded Python)
  - dist/OlgaEnglishCoach-2.1.1.dmg

Requirements:
  - pip install pyinstaller
  - pip install create-dmg  (or brew install create-dmg)

The resulting .app contains only .pyc / binary files — no .py sources.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

APP_NAME = "Olga English Coach"
BUNDLE_ID = "local.olga-english-coach"
VERSION = "2.1.1"
RESOURCES = Path(__file__).resolve().parent / "Contents" / "Resources"
DIST_DIR = Path(__file__).resolve().parent / "dist"
BUILD_DIR = Path(__file__).resolve().parent / "build"

HIDDEN_IMPORTS = [
    "customtkinter",
    "darkdetect",
    "PIL",
    "PIL.Image",
    "PIL.ImageTk",
    "tkinter",
    "tkinter.ttk",
    "objc",
    "Quartz",
    "Foundation",
    "AppKit",
    "SpeechRecognition",
    "pyaudio",
    "playsound",
    "requests",
    "urllib3",
    "sqlite3",
    "json",
    "queue",
    "threading",
    "datetime",
    "pathlib",
    "hashlib",
    "hmac",
    "random",
    "re",
    "statistics",
    "math",
    "copy",
    "dataclasses",
    "typing",
    "webbrowser",
    "subprocess",
    "platform",
    "logging",
    "traceback",
    "tempfile",
    "time",
    "inspect",
    "collections",
    "functools",
    "itertools",
    "heapq",
    "bisect",
    "decimal",
    "fractions",
    "numbers",
    "email",
    "email.mime",
    "email.mime.text",
    "email.mime.multipart",
    "smtplib",
    "calendar",
    "zoneinfo",
    "xml.etree.ElementTree",
    "html.parser",
    "html.entities",
    "string",
    "csv",
    "pickle",
    "gzip",
    "base64",
    "binascii",
    "uuid",
    "mimetypes",
    "ftplib",
    "http.client",
    "http.server",
    "socketserver",
    "socket",
    "ssl",
    "certifi",
    "charset_normalizer",
    "idna",
]


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def clean() -> None:
    for d in [DIST_DIR, BUILD_DIR]:
        if d.exists():
            shutil.rmtree(d)
            print(f"Removed {d}")


def build_app() -> Path:
    """Run PyInstaller to create a standalone .app bundle."""
    clean()

    app_py = RESOURCES / "app.py"
    icon_icns = RESOURCES / "icon.icns"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--windowed",
        "--name", APP_NAME,
        "--icon", str(icon_icns),
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
        "--specpath", str(BUILD_DIR),
        "--noconfirm",
        "--clean",
        "--osx-bundle-identifier", BUNDLE_ID,
    ]
    for mod in HIDDEN_IMPORTS:
        cmd += ["--hidden-import", mod]

    # Add data files
    data_items = [
        (str(RESOURCES / "assets"), "assets"),
        (str(RESOURCES / "bin"), "bin"),
        (str(RESOURCES / "version.json"), "."),
        (str(RESOURCES / "voice_helper.swift"), "."),
    ]
    for src, dst in data_items:
        cmd += ["--add-data", f"{src}{os.pathsep}{dst}"]

    cmd += [str(app_py)]
    run(cmd)

    app_path = DIST_DIR / f"{APP_NAME}.app"
    if not app_path.exists():
        raise RuntimeError(f"PyInstaller did not create {app_path}")

    # Replace Info.plist with ours
    plist_src = RESOURCES.parent / "Info.plist"
    plist_dst = app_path / "Contents" / "Info.plist"
    shutil.copy2(plist_src, plist_dst)
    print(f"Updated Info.plist: {plist_dst}")

    return app_path


def remove_py_files(app_path: Path) -> None:
    """Remove all .py source files from the bundle (keep compiled)."""
    count = 0
    for root, _, files in os.walk(app_path):
        for f in files:
            if f.endswith(".py"):
                p = Path(root) / f
                p.unlink()
                count += 1
    print(f"Removed {count} .py source files from bundle")

    # Also remove keygen.py from the bundle if PyInstaller picked it up
    keygen_path = app_path / "Contents" / "MacOS" / "keygen"
    if keygen_path.exists():
        keygen_path.unlink()
        print("Removed keygen binary from bundle")


def create_dmg(app_path: Path) -> Path:
    """Create a DMG from the .app bundle."""
    dmg_name = f"OlgaEnglishCoach-{VERSION}.dmg"
    dmg_path = DIST_DIR / dmg_name
    temp_dir = DIST_DIR / "dmg_tmp"
    temp_dir.mkdir(exist_ok=True)

    # Copy app into temp dir
    app_copy = temp_dir / app_path.name
    if app_copy.exists():
        shutil.rmtree(app_copy)
    shutil.copytree(app_path, app_copy, symlinks=True)

    # Create /Applications symlink
    applications_link = temp_dir / "Applications"
    if applications_link.exists():
        applications_link.unlink()
    applications_link.symlink_to("/Applications")

    # Use hdiutil if create-dmg is not available
    try:
        subprocess.run(["create-dmg", "--version"], check=True, capture_output=True)
        cmd = [
            "create-dmg",
            "--volname", APP_NAME,
            "--window-pos", "200", "120",
            "--window-size", "800", "400",
            "--icon-size", "100",
            "--app-drop-link", "620", "185",
            "--icon", app_path.name, "180", "185",
            str(dmg_path),
            str(temp_dir),
        ]
        run(cmd)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("create-dmg not found, using hdiutil fallback")
        temp_dmg = DIST_DIR / "temp.dmg"
        run([
            "hdiutil", "create", "-srcfolder", str(temp_dir),
            "-volname", APP_NAME, "-fs", "HFS+",
            "-format", "UDRW", "-size", "2g", str(temp_dmg),
        ])
        run(["hdiutil", "convert", str(temp_dmg), "-format", "UDZO",
             "-o", str(dmg_path)])
        temp_dmg.unlink()

    print(f"DMG created: {dmg_path}")
    return dmg_path


def main() -> int:
    print(f"Building {APP_NAME} v{VERSION}")
    app_path = build_app()
    remove_py_files(app_path)
    dmg_path = create_dmg(app_path)
    print(f"\nDone! {dmg_path}")
    print(f"App bundle: {app_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
