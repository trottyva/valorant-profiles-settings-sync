# VALORANT Profiles Settings Sync

Save your VALORANT settings as named profiles and apply them to any of your Riot accounts —
sensitivity, crosshairs, keybinds, audio, HUD and everything else stored in your account settings.

VALORANT keeps settings server-side, per account. This tool talks to the Riot Client's local API
to read the settings of the signed-in account and write them to another one.

## Requirements

- Windows
- Python 3.10+
- `requests` (`pip install requests`)

## Usage

Double-click `VALORANT Profiles.bat` (or run `python interface.py`).

```
=== VALORANT · Settings profiles ===

Signed-in account : player#tag   settings: Main profile
VALORANT          : closed

Profiles
  1. Main profile  — from player#tag, 2026-10-03 15:35

Actions
  a  Apply a profile to the signed-in account
  s  Save the signed-in account's settings to a profile
  n  Rename a profile
  d  Delete a profile
  b  Restore a backup of the signed-in account
  r  Refresh        q  Quit
```

Typical workflow:

1. Sign in to the account whose settings you want to copy in the Riot Client, then press `s` and give the profile a name.
2. Sign in to the target account, **with VALORANT closed**, then press `a` and pick the profile.
3. Launch VALORANT.

VALORANT must be closed when applying a profile: the game loads its settings at launch and would
overwrite the new ones when you change an option or quit.

Before each change, the account's current settings are backed up and can be restored with `b`.

## Data

Profiles, backups and known account names are stored locally in `data/`.

## Disclaimer

This project uses the Riot Client's unofficial local API. It only reads and writes your own
account settings, but it is not endorsed by Riot Games and may break after an update.
Use it at your own risk.
