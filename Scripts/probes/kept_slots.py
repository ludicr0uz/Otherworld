"""The developer's save slots, kept out of a probe run.

A kept tuning tab loads its slot at BeginPlay and saves it on a nudge
(graphics_menu/tune_keep.py); the profile, the saved game, is read back onto
the player as the level starts (graphics_menu/profile_read.py). A probe has
to start from the built table and the issued loadout, whatever the developer
nudged or saved in their own games, and must leave nothing of its own behind,
for the next probe or for them.

    set_aside   before the run: each slot's file moved beside itself
    clear       after each probe: what it saved, deleted
    put_back    after the run: cleared, then the files moved back

A run that was killed leaves the moved files where they are: the next
set_aside finds them, keeps them, and deletes the dead run's own saves.

Two suffixes. BACKUP is the tabs', and the one a probe's own ``probe()``
wrapper uses to set the profile aside for itself (too late: the level has
read it by then). The profile is kept under RUN_BACKUP, a name that wrapper
does not know, or it would find the run's copy and put it back after the
first probe.

Pure Python (no unreal import): boot.py gives it the folder and the slots.
"""

import os
import shutil

BACKUP = ".probe-backup"
RUN_BACKUP = ".probe-run"
SUFFIXES = (BACKUP, RUN_BACKUP)


def _files(save_dir, slots):
    return [os.path.join(save_dir, f"{slot}.sav") for slot in slots]


def set_aside(save_dir, slots, suffix=BACKUP):
    for live in _files(save_dir, slots):
        if os.path.exists(live + suffix):
            if os.path.exists(live):
                os.remove(live)
        elif os.path.exists(live):
            shutil.move(live, live + suffix)


def clear(save_dir, slots):
    for live in _files(save_dir, slots):
        if os.path.exists(live):
            os.remove(live)


def put_back(save_dir, slots, suffix=BACKUP):
    clear(save_dir, slots)
    for live in _files(save_dir, slots):
        if os.path.exists(live + suffix):
            shutil.move(live + suffix, live)
