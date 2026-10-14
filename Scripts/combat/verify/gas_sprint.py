"""Checks for the relaxed forward sprint loop (combat/gas_sprint.py), run by the
gas_locomotion section: each of the sample's sprint-loop databases plays the
forward loop the switch names, with the entry's settings as the sample had
them, and keeps its neutral diagonals."""
import unreal

from combat.gas_sprint import (
    DIAGONALS, FORWARD_ENTRY, SPRINT_LOOP_DBS, entries, forward_loop)
from combat.verify.common import check

# How many entries each has, as the sample made them: the swap adds none.
COUNTS = (7, 7, 2)


def check_sprint_loops():
    want, gone = forward_loop()
    name = want.rsplit("/", 1)[1]
    for path, count in zip(SPRINT_LOOP_DBS, COUNTS):
        db = unreal.EditorAssetLibrary.load_asset(path)
        got = entries(db) if db is not None else []
        clips = [c for c, _s in got]
        forward = [s for c, s in got if c == want]
        diagonals = [d for d in DIAGONALS if d in clips]
        check(f"{path.rsplit('/', 1)[1]} plays {name} straight ahead in place of "
              f"{gone.rsplit('/', 1)[1]}, its entry's settings the sample's "
              f"(enabled, reselection, mirroring, sampling range {FORWARD_ENTRY}), "
              f"its {count} entries and its neutral diagonals kept",
              forward == [FORWARD_ENTRY] and gone not in clips and len(got) == count
              and (len(diagonals) == 2 or count == 2),
              f"{[(c.rsplit('/', 1)[1] if c else c, s) for c, s in got]}")
