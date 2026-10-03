"""Terminal interface for managing VALORANT settings profiles."""

import os
import sys
from datetime import datetime

import requests

import valorant_sync as vs

os.system("")  # enables ANSI colors in the Windows console
B, DIM, G, R, Y, C, X = ("\033[1m", "\033[2m", "\033[32m", "\033[31m",
                         "\033[33m", "\033[36m", "\033[0m")


def date(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def ask(prompt):
    try:
        return input(f"{C}> {X}{prompt}").strip().lstrip("﻿")
    except EOFError:
        sys.exit()


def confirm(prompt):
    return ask(f"{prompt} {DIM}(y/n){X} ").lower() in ("y", "yes")


def pause():
    ask(f"{DIM}Press Enter to continue…{X}")


def pick_profile(profiles, action):
    if not profiles:
        print(f"{Y}No saved profiles.{X}")
        return None
    choice = ask(f"Number of the profile to {action}: ")
    if choice.isdigit() and 1 <= int(choice) <= len(profiles):
        return profiles[int(choice) - 1]
    print(f"{R}Invalid choice.{X}")
    return None


def connected():
    """Returns (account, current settings) or (None, reason)."""
    try:
        account = vs.Account()
        return account, account.fetch()
    except vs.NotConnected as e:
        return None, str(e)
    except requests.RequestException as e:
        return None, f"network error ({e.__class__.__name__})"


def header(account, current, running, profiles):
    os.system("cls")
    print(f"{B}=== VALORANT · Settings profiles ==={X}\n")
    if account:
        actual = vs.matching_profile(current) if current else None
        tag = f"{G}{actual}{X}" if actual else f"{DIM}no saved profile{X}"
        print(f"Signed-in account : {B}{account.name}{X}   settings: {tag}")
    else:
        print(f"Signed-in account : {R}none{X} {DIM}({current}){X}")
    print(f"VALORANT          : {R + 'running' if running else G + 'closed'}{X}\n")

    print(f"{B}Profiles{X}")
    if not profiles:
        print(f"  {DIM}(none){X}")
    for i, p in enumerate(profiles, 1):
        print(f"  {B}{i}.{X} {p['name']}  {DIM}— from {vs.account_name(p['source'])}, "
              f"{date(p['saved'])}{X}")
    print(f"""
{B}Actions{X}
  {C}a{X}  Apply a profile to the signed-in account
  {C}s{X}  Save the signed-in account's settings to a profile
  {C}n{X}  Rename a profile
  {C}d{X}  Delete a profile
  {C}b{X}  Restore a backup of the signed-in account
  {C}r{X}  Refresh        {C}q{X}  Quit
""")


def do_apply(account, running, profiles):
    if not account:
        return print(f"{R}Sign in to an account in the Riot Client first.{X}")
    if running:
        return print(f"{R}Close VALORANT before applying a profile "
                     f"(the game would overwrite the settings).{X}")
    p = pick_profile(profiles, "apply")
    if p and confirm(f"Apply \"{p['name']}\" to {account.name}?"):
        if vs.apply_profile(account, p["name"]):
            print(f"{G}Profile applied. The previous settings were backed up.{X}")
        else:
            print(f"{G}This account already has these settings.{X}")


def do_save(account, current, profiles):
    if not account:
        return print(f"{R}Sign in to an account in the Riot Client first.{X}")
    if not current:
        return print(f"{R}This account has no settings stored by Riot.{X}")
    name = ask("Profile name (an existing one to update it): ")
    if not name:
        return
    existing = vs.get_profile(name)
    if existing and not confirm(f"Replace the profile \"{existing['name']}\"?"):
        return
    vs.save_profile(account, name, current)
    print(f"{G}Profile \"{name}\" saved from {account.name}.{X}")


def do_rename(profiles):
    p = pick_profile(profiles, "rename")
    if p:
        new = ask("New name: ")
        if new:
            vs.rename_profile(p["name"], new)
            print(f"{G}Renamed to \"{new}\".{X}")


def do_delete(profiles):
    p = pick_profile(profiles, "delete")
    if p and confirm(f"Permanently delete the profile \"{p['name']}\"?"):
        vs.delete_profile(p["name"])
        print(f"{G}Profile deleted.{X}")


def do_restore(account, running):
    if not account:
        return print(f"{R}Sign in to an account in the Riot Client first.{X}")
    if running:
        return print(f"{R}Close VALORANT before restoring a backup.{X}")
    backups = vs.list_backups(account.puuid)
    if not backups:
        return print(f"{Y}No backups for {account.name}.{X}")
    print(f"\nBackups of {account.name} (taken before each change):")
    for i, (ts, _) in enumerate(backups, 1):
        print(f"  {B}{i}.{X} {date(ts)}")
    choice = ask("Backup number: ")
    if choice.isdigit() and 1 <= int(choice) <= len(backups):
        ts, path = backups[int(choice) - 1]
        if confirm(f"Restore the settings from {date(ts)} to {account.name}?"):
            vs.restore_backup(account, path)
            print(f"{G}Backup restored.{X}")
    else:
        print(f"{R}Invalid choice.{X}")


def main():
    while True:
        account, current = connected()
        running = vs.game_running()
        profiles = vs.list_profiles()
        header(account, current, running, profiles)
        cmd = ask("Action: ").lower()
        if cmd == "q":
            return
        if cmd in ("", "r"):
            continue
        try:
            if cmd == "a":
                do_apply(account, running, profiles)
            elif cmd == "s":
                do_save(account, current, profiles)
            elif cmd == "n":
                do_rename(profiles)
            elif cmd == "d":
                do_delete(profiles)
            elif cmd == "b":
                do_restore(account, running)
            else:
                print(f"{R}Unknown action.{X}")
        except (requests.RequestException, ValueError, OSError) as e:
            print(f"{R}Failed: {e}{X}")
        pause()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
