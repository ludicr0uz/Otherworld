"""The tuning tabs' save slots, kept out of a probe run.

A kept tab loads its slot at BeginPlay and saves it on a nudge
(graphics_menu/tune_keep.py). A probe has to start from the built table,
whatever the developer nudged in their own games, and must leave nothing of
its own nudges behind, for the next probe or for them.

    set_aside   before the run: each slot's file moved beside itself
    clear       after each probe: what it saved, deleted
    put_back    after the run: cleared, then the files moved back

A run that was killed leaves the moved files where they are: the next
set_aside finds them, keeps them, and deletes the dead run's own saves.

Pure Python (no unreal import): boot.py gives it the folder and the slots.
"""

import os
import shutil

BACKUP = ".probe-backup"


def _files(save_dir, slots):
    return [os.path.join(save_dir, f"{slot}.sav") for slot in slots]


def set_aside(save_dir, slots):
    for live in _files(save_dir, slots):
        if os.path.exists(live + BACKUP):
            if os.path.exists(live):
                os.remove(live)
        elif os.path.exists(live):
            shutil.move(live, live + BACKUP)


def clear(save_dir, slots):
    for live in _files(save_dir, slots):
        if os.path.exists(live):
            os.remove(live)


def put_back(save_dir, slots):
    clear(save_dir, slots)
    for live in _files(save_dir, slots):
        if os.path.exists(live + BACKUP):
            shutil.move(live + BACKUP, live)
