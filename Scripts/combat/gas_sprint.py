"""The unarmed sprint straight ahead is the sample's relaxed loop: its three
sprint-loop databases have M_Relaxed_Sprint_Loop_F where they had
M_Neutral_Sprint_Loop_F.

WHICH DATABASES
---------------
Every one the CHT_PoseSearchDatabases chooser can offer for a sprint that
plays the neutral forward loop: the dense, sparse and extreme-sparse sets'
Stand_Sprint_Loops (index 0 in each; read off the asset registry's
referencers of the clip). The other referencer, PSD_SM_CMC_Loops, belongs to
the sample's experimental state machine, which the game does not run. The
diagonals (M_Neutral_Sprint_Loop_FL, _FR), the run- and walk-to-sprint
transitions, and the sprint starts, stops and pivots stay neutral.

WHY THIS CLIP FITS
------------------
Its root travels 585 cm/s (1326 cm in 2.267 s); the neutral loop's 700
(1400 cm in 2.0 s). The game sprints at 600 (player_tuning.csv), so the
motion matching plays the relaxed loop at 1.03 of its speed where it played
the neutral one at 0.86, the bottom of its 0.85 to 1.15 range. Its stride is
the neutral one's to a few cm relative to the pelvis, which sits about 5 cm
off it: the veer to a diagonal blends without a pop
(probes/probe_relaxed_sprint.py measures the cadence, the pick and the pelvis).

HOW
---
A pose search database's entries are a plain UPROPERTY() Python can neither
read the settings of nor write, so the swap is the editor module's
OtherworldPoseSearchLibrary.ReplaceDatabaseAnimation: the entry keeps its
enabled flag, reselection, mirroring and sampling range, and only its clip
changes. The databases are rows of gas_paths.PATCHED, so import_gas.py does
not copy the sample's back over them. The search index is rebuilt from the
saved database as a game starts (or as it cooks), like any database change.
Off (RELAXED_SPRINT False) the swap goes back the other way.
"""
import unreal

from asset_pipeline.gas_paths import SPRINT_LOOP_DBS as SAMPLE_DBS, UEFN, gas
from combat.log import _log

# The one switch: False puts the neutral forward loop back.
RELAXED_SPRINT = True

SPRINT = UEFN + "/Animations/Sprint"
NEUTRAL_F = SPRINT + "/M_Neutral_Sprint_Loop_F"
RELAXED_F = SPRINT + "/M_Relaxed_Sprint_Loop_F"
# Stay as they are: the diagonals the forward loop blends with.
DIAGONALS = (SPRINT + "/M_Neutral_Sprint_Loop_FL", SPRINT + "/M_Neutral_Sprint_Loop_FR")
# The dense, sparse and extreme-sparse sets' (gas_paths: rows of PATCHED).
SPRINT_LOOP_DBS = tuple(gas(p) for p in SAMPLE_DBS)
# The forward loop's entry as the sample has it in all three, which the swap
# keeps: (enabled, disable reselection, mirror option, sampling range).
# Mirror option 0 is "original only"; a range of (0, 0) is the whole clip.
FORWARD_ENTRY = (True, True, 0, (0.0, 0.0))


def forward_loop():
    """(the clip the databases should play, the one they should not)."""
    return (RELAXED_F, NEUTRAL_F) if RELAXED_SPRINT else (NEUTRAL_F, RELAXED_F)


def _must_load(path):
    asset = unreal.EditorAssetLibrary.load_asset(path)
    if asset is None:
        raise RuntimeError(f"{path} is not here: run import_gas.py")
    return asset


def entries(db):
    """[(clip path, (enabled, reselection, mirror, (min, max)))] of a database."""
    lib = unreal.OtherworldPoseSearchLibrary
    got = []
    for i in range(db.get_num_animation_assets()):
        asset, enabled, reselect, mirror, rng = lib.get_database_entry(db, i)
        path = asset.get_path_name().split(".")[0] if asset else None
        got.append((path, (enabled, reselect, mirror, (rng.x, rng.y))))
    return got


def swap_sprint_loop():
    want, gone = forward_loop()
    to, frm = _must_load(want), _must_load(gone)
    for path in SPRINT_LOOP_DBS:
        db = _must_load(path)
        n = unreal.OtherworldPoseSearchLibrary.replace_database_animation(db, frm, to)
        clips = [c for c, _s in entries(db)]
        if want not in clips or gone in clips:
            raise RuntimeError(f"{path}: the forward loop is not {want.rsplit('/', 1)[1]} "
                               f"after the swap: {clips}")
        if n and not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
            raise RuntimeError(f"{path} was not saved")
        _log(f"sprint loops: {path.rsplit('/', 1)[1]} plays {want.rsplit('/', 1)[1]}"
             f"{' (swapped)' if n else ' (already)'}")
