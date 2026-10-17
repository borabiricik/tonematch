"""Paths and settings. Heavy data lives outside OneDrive (%LOCALAPPDATA%/tonematch)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
IS_MAC = sys.platform == "darwin"


def _local_base() -> Path:
    """Per-user app data outside OneDrive/iCloud (same place the launchers put the venv)."""
    if IS_MAC:
        return Path.home() / "Library" / "Application Support"
    return Path(os.environ.get("LOCALAPPDATA", Path.home()))


DATA_DIR = Path(os.environ.get("TONEMATCH_DATA", _local_base() / "tonematch" / "data"))
TRACKS_DIR = DATA_DIR / "tracks"
BACKUP_DIR = DATA_DIR / "backups"
MODELS_DIR = DATA_DIR / "models"

# BOSS TONE STUDIO (Adobe AIR): preset bank in the install, downloaded livesets in AIR's "Local Store".
# macOS locations follow the AIR layout (app resources inside the .app, store under ~/Library/Preferences);
# not verified on a Mac yet -> override with BTS_INSTALL / BTS_APPDATA if needed.
if IS_MAC:
    _bts_install = "/Applications/BOSS TONE STUDIO for GT-1.app/Contents/Resources"
    _bts_appdata = Path.home() / "Library" / "Preferences" / "BOSS-TONE-STUDIO-for-GT-1" / "Local Store"
else:
    _bts_install = r"C:\Program Files (x86)\BOSS TONE STUDIO for GT-1"
    _bts_appdata = Path(os.environ.get("APPDATA", "")) / "BOSS-TONE-STUDIO-for-GT-1" / "Local Store"
BTS_INSTALL = Path(os.environ.get("BTS_INSTALL", _bts_install))
BTS_APPDATA = Path(os.environ.get("BTS_APPDATA", _bts_appdata))

SR = 44100

# Source separation: first available model wins (audio-separator model filenames).
SEPARATION_MODELS = [
    "BS-Roformer-SW.ckpt",  # 6 stems incl. guitar
    "htdemucs_6s.yaml",     # fallback, 6 stems incl. guitar
]

for d in (TRACKS_DIR, BACKUP_DIR, MODELS_DIR):
    d.mkdir(parents=True, exist_ok=True)
