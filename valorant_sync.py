"""Copy VALORANT settings between several Riot accounts, using named profiles.

Settings (sensitivity, crosshairs, keybinds, audio, HUD...) are stored
server-side by Riot, per account (the "Ares.PlayerSettings" preference). This module
uses the Riot Client's local API to read and write those preferences.
The user interface lives in interface.py.
"""

import base64
import json
import os
import re
import shutil
import subprocess
import time
import zlib
from pathlib import Path

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

LOCALAPPDATA = Path(os.environ["LOCALAPPDATA"])
LOCKFILE = LOCALAPPDATA / "Riot Games" / "Riot Client" / "Config" / "lockfile"
VALORANT_CONFIG = LOCALAPPDATA / "VALORANT" / "Saved" / "Config"
LOCAL_FILES = ["Windows/RiotUserSettings.ini", "WindowsClient/BackupKeybinds.json"]

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
PROFILES = DATA_DIR / "profiles"
BACKUPS = DATA_DIR / "backups"
ACCOUNTS = DATA_DIR / "accounts.json"

PREF_URL = "https://player-preferences-usw2.pp.sgp.pvp.net/playerPref/v3"
PREF_TYPE = "Ares.PlayerSettings"
GAME_PROCESS = "VALORANT-Win64-Shipping.exe"


class NotConnected(Exception):
    pass


# --- Riot Client ---------------------------------------------------------

class Account:
    """Account currently signed in to the Riot Client."""

    def __init__(self):
        try:
            _, _, port, password, protocol = LOCKFILE.read_text().split(":")
            self._base = f"{protocol}://127.0.0.1:{port}"
            self._auth = ("riot", password)
            t = self._local("/entitlements/v1/token")
        except (OSError, ValueError, requests.RequestException) as e:
            raise NotConnected("Riot Client is not running") from e
        if t is None:
            raise NotConnected("no account signed in")
        self.puuid = t["subject"]
        self.headers = {
            "Authorization": f"Bearer {t['accessToken']}",
            "X-Riot-Entitlements-JWT": t["token"],
        }
        self.name = self._riot_id()
        remember_account(self.puuid, self.name)

    def _local(self, path):
        r = requests.get(self._base + path, auth=self._auth, verify=False, timeout=5)
        return r.json() if r.status_code == 200 else None

    def _riot_id(self):
        try:
            s = self._local("/chat/v1/session")
        except requests.RequestException:
            s = None
        if s and s.get("game_name"):
            return f"{s['game_name']}#{s['game_tag']}"
        return account_name(self.puuid)

    def fetch(self):
        r = requests.get(f"{PREF_URL}/getPreference/{PREF_TYPE}",
                         headers=self.headers, timeout=10)
        r.raise_for_status()
        data = r.json().get("data")
        if not data:
            return None
        return json.loads(zlib.decompress(base64.b64decode(data), -15))

    def push(self, settings):
        raw = json.dumps(settings, separators=(",", ":")).encode()
        comp = zlib.compressobj(wbits=-15)
        data = base64.b64encode(comp.compress(raw) + comp.flush()).decode()
        r = requests.put(f"{PREF_URL}/savePreference", headers=self.headers, timeout=10,
                         json={"type": PREF_TYPE, "data": data})
        r.raise_for_status()


def game_running():
    out = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {GAME_PROCESS}", "/NH"],
        capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW,
    ).stdout
    return GAME_PROCESS.lower() in out.lower()


# --- Account names -------------------------------------------------------

def _read_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def remember_account(puuid, name):
    accounts = _read_json(ACCOUNTS, {})
    if name and not name.startswith(puuid[:8]) and accounts.get(puuid) != name:
        accounts[puuid] = name
        _write_json(ACCOUNTS, accounts)


def account_name(puuid):
    return _read_json(ACCOUNTS, {}).get(puuid) or f"{puuid[:8]}…"


# --- Local files ---------------------------------------------------------

def account_dir(puuid):
    dirs = sorted(VALORANT_CONFIG.glob(f"{puuid}-*"), key=lambda p: p.stat().st_mtime)
    return dirs[-1] if dirs else None


def _copy_local(src, dst):
    if not src or not dst:
        return
    for rel in LOCAL_FILES:
        if (src / rel).exists():
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src / rel, dst / rel)


# --- Profiles ------------------------------------------------------------

def _slug(name):
    return re.sub(r"[^\w-]+", "_", name.strip().lower()).strip("_") or "profile"


def list_profiles():
    if not PROFILES.exists():
        return []
    profiles = [_read_json(p, None) for p in PROFILES.glob("*.json")]
    return sorted((p for p in profiles if p), key=lambda p: p["name"].lower())


def get_profile(name):
    return _read_json(PROFILES / f"{_slug(name)}.json", None)


def save_profile(account, name, settings=None):
    """Saves the signed-in account's settings under the given name."""
    settings = settings or account.fetch()
    if not settings:
        raise ValueError("this account has no settings stored by Riot")
    slug = _slug(name)
    _write_json(PROFILES / f"{slug}.json", {
        "name": name.strip(), "source": account.puuid, "source_name": account.name,
        "saved": time.time(), "settings": settings,
    })
    _copy_local(account_dir(account.puuid), PROFILES / slug)


def rename_profile(old, new):
    p = get_profile(old)
    old_slug, new_slug = _slug(old), _slug(new)
    if old_slug != new_slug and (PROFILES / f"{new_slug}.json").exists():
        raise ValueError(f"a profile named \"{new}\" already exists")
    p["name"] = new.strip()
    (PROFILES / f"{old_slug}.json").unlink()
    _write_json(PROFILES / f"{new_slug}.json", p)
    if (PROFILES / old_slug).is_dir() and old_slug != new_slug:
        (PROFILES / old_slug).rename(PROFILES / new_slug)


def delete_profile(name):
    slug = _slug(name)
    (PROFILES / f"{slug}.json").unlink(missing_ok=True)
    shutil.rmtree(PROFILES / slug, ignore_errors=True)


def apply_profile(account, name):
    """Applies a profile to the signed-in account. Returns False if it already had it."""
    profile = get_profile(name)
    current = account.fetch()
    if current == profile["settings"]:
        return False
    if current:
        _write_json(BACKUPS / f"{account.puuid}-{int(time.time())}.json", current)
    account.push(profile["settings"])
    _copy_local(PROFILES / _slug(name), account_dir(account.puuid))
    return True


def matching_profile(settings):
    for p in list_profiles():
        if p["settings"] == settings:
            return p["name"]
    return None


# --- Automatic backups ---------------------------------------------------

def list_backups(puuid):
    """Backups of the account, newest first: (timestamp, path)."""
    out = []
    for path in BACKUPS.glob(f"{puuid}-*.json"):
        out.append((int(path.stem.rsplit("-", 1)[1]), path))
    return sorted(out, reverse=True)


def restore_backup(account, path):
    current = account.fetch()
    if current:
        _write_json(BACKUPS / f"{account.puuid}-{int(time.time())}.json", current)
    account.push(_read_json(path, None))
