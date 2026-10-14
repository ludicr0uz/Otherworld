"""Checks for the relaxed sprint (combat/gas_sprint.py), run by the
gas_locomotion section: each of the sample's sprint-loop databases plays the
forward loop the switch names, with the entry's settings as the sample had
them, and keeps its neutral diagonals; no sprint database, loops or starts,
keeps a clip the switch swapped out, and none gained or lost an entry."""
import unreal

from combat.gas_sprint import (
    DIAGONALS, FORWARD_ENTRY, SPRINT_LOOP_DBS, SPRINT_START_DBS, entries, forward_loop,
    swaps)
from combat.verify.common import check

# How many entries each has, as the sample made them: the swap adds none.
COUNTS = (7, 7, 2)
START_COUNTS = (10, 6, 2)


def _short(path):
    return path.rsplit("/", 1)[1] if path else path


def check_sprint_loops():
    want, gone = forward_loop()
    name = _short(want)
    for path, count in zip(SPRINT_LOOP_DBS, COUNTS):
        db = unreal.EditorAssetLibrary.load_asset(path)
        got = entries(db) if db is not None else []
        clips = [c for c, _s in got]
        forward = [s for c, s in got if c == want]
        diagonals = [d for d in DIAGONALS if d in clips]
        check(f"{_short(path)} plays {name} straight ahead in place of "
              f"{_short(gone)}, its entry's settings the sample's "
              f"(enabled, reselection, mirroring, sampling range {FORWARD_ENTRY}), "
              f"its {count} entries and its neutral diagonals kept",
              forward == [FORWARD_ENTRY] and gone not in clips and len(got) == count
              and (len(diagonals) == 2 or count == 2),
              f"{[(_short(c), s) for c, s in got]}")
    gones = {g for _w, g in swaps()}
    for path, count in zip(SPRINT_LOOP_DBS + SPRINT_START_DBS, COUNTS + START_COUNTS):
        db = unreal.EditorAssetLibrary.load_asset(path)
        clips = [c for c, _s in entries(db)] if db is not None else []
        check(f"{_short(path)} keeps none of the sprint clips the switch swapped out "
              f"(starts, transitions, loop) and its {count} entries",
              len(clips) == count and not gones.intersection(clips),
              f"{[_short(c) for c in clips]}")
