"""The unarmed sprint straight ahead is the sample's relaxed set: its sprint
databases have M_Relaxed_Sprint_Loop_F where they had M_Neutral_Sprint_Loop_F,
and the relaxed starts and walk- and run-to-sprint transitions where they had
the neutral ones.

WHICH DATABASES
---------------
Every one the CHT_PoseSearchDatabases chooser can offer for a sprint that
plays a neutral clip the relaxed set has a twin of: the dense, sparse and
extreme-sparse sets' Stand_Sprint_Loops (the forward loop and the
transitions) and Stand_Sprint_Starts (the starts straight ahead and the
refacing starts; read off the asset registry's referencers of the clips). The
other referencers, PSD_SM_CMC_Loops and PSD_SM_CMC_Transitions, belong to the
sample's experimental state machine, which the game does not run. The
diagonals (M_Neutral_Sprint_Loop_FL, _FR, the FL and FR starts), the stops
and the pivots stay neutral: the relaxed set has no diagonals.

WHY THE STARTS TOO
------------------
A neutral start pushes off with the chest and head pitched down; it blended
into the upright relaxed loop, so a sprint from standing or from a walk dipped
the head and came back up. The relaxed starts and transitions end in the
relaxed loop's posture.

WHY THE LOOP FITS
-----------------
The relaxed loop's root travels 585 cm/s (1326 cm in 2.267 s); the neutral
loop's 700 (1400 cm in 2.0 s). The game sprints at 600 (player_tuning.csv), so
the motion matching plays the relaxed loop at 1.03 of its speed where it played
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

from asset_pipeline.gas_paths import SPRINT_LOOP_DBS as SAMPLE_LOOPS
from asset_pipeline.gas_paths import SPRINT_START_DBS as SAMPLE_STARTS, UEFN, gas
from combat.log import _log

# The one switch: False puts the neutral loop, starts and transitions back.
RELAXED_SPRINT = True

SPRINT = UEFN + "/Animations/Sprint"
NEUTRAL_F = SPRINT + "/M_Neutral_Sprint_Loop_F"
RELAXED_F = SPRINT + "/M_Relaxed_Sprint_Loop_F"
# Stay as they are: the diagonals the forward loop blends with.
DIAGONALS = (SPRINT + "/M_Neutral_Sprint_Loop_FL", SPRINT + "/M_Neutral_Sprint_Loop_FR")
# The dense, sparse and extreme-sparse sets' (gas_paths: rows of PATCHED).
SPRINT_LOOP_DBS = tuple(gas(p) for p in SAMPLE_LOOPS)
SPRINT_START_DBS = tuple(gas(p) for p in SAMPLE_STARTS)
SPRINT_DBS = SPRINT_LOOP_DBS + SPRINT_START_DBS
# (neutral, relaxed): every clip of the sprint databases the relaxed set has a
# twin of. Each is swapped wherever its database has it.
PAIRS = tuple((SPRINT + "/" + n, SPRINT + "/" + r) for n, r in (
    ("M_Neutral_Sprint_Loop_F", "M_Relaxed_Sprint_Loop_F"),
    ("M_Neutral_Transition_Run_to_Sprint_Lfoot", "M_Relaxed_Transition_Run_to_Sprint_Lfoot"),
    ("M_Neutral_Transition_Run_to_Sprint_Rfoot", "M_Relaxed_Transition_Run_to_Sprint_Rfoot"),
    ("M_Neutral_Transition_Walk_to_Sprint_Lfoot", "M_Relaxed_Transition_Walk_to_Sprint_Lfoot"),
    ("M_Neutral_Transition_Walk_to_Sprint_Rfoot", "M_Relaxed_Transition_Walk_to_Sprint_Rfoot"),
    ("M_Neutral_Sprint_Start_F_Lfoot", "M_Relaxed_Sprint_Start_F_Lfoot"),
    ("M_Neutral_Sprint_Start_F_Rfoot", "M_Relaxed_Sprint_Start_F_Rfoot"),
    ("M_Neutral_Sprint_Reface_Start_F_L_090", "M_Relaxed_Sprint_Reface_Start_090_L"),
    ("M_Neutral_Sprint_Reface_Start_F_L_180", "M_Relaxed_Sprint_Reface_Start_180_L"),
    ("M_Neutral_Sprint_Reface_Start_F_R_090", "M_Relaxed_Sprint_Reface_Start_090_R"),
    ("M_Neutral_Sprint_Reface_Start_F_R_180", "M_Relaxed_Sprint_Reface_Start_180_R"),
))
# The forward loop's entry as the sample has it in all three, which the swap
# keeps: (enabled, disable reselection, mirror option, sampling range).
# Mirror option 0 is "original only"; a range of (0, 0) is the whole clip.
FORWARD_ENTRY = (True, True, 0, (0.0, 0.0))


def forward_loop():
    """(the clip the databases should play, the one they should not)."""
    return (RELAXED_F, NEUTRAL_F) if RELAXED_SPRINT else (NEUTRAL_F, RELAXED_F)


def swaps():
    """[(the clip the databases should play, the one it replaces)]."""
    return [(r, n) if RELAXED_SPRINT else (n, r) for n, r in PAIRS]

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


def swap_sprint_clips():
    pairs = [(want, gone, _must_load(want), _must_load(gone)) for want, gone in swaps()]
    for path in SPRINT_DBS:
        db = _must_load(path)
        n = sum(unreal.OtherworldPoseSearchLibrary.replace_database_animation(db, frm, to)
                for _w, _g, to, frm in pairs)
        clips = [c for c, _s in entries(db)]
        left = [g.rsplit("/", 1)[1] for _w, g, _t, _f in pairs if g in clips]
        if left:
            raise RuntimeError(f"{path}: {left} still in it after the swap: {clips}")
        if n and not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
            raise RuntimeError(f"{path} was not saved")
        _log(f"sprint clips: {path.rsplit('/', 1)[1]} plays the "
             f"{'relaxed' if RELAXED_SPRINT else 'neutral'} set"
             f"{f' ({n} swapped)' if n else ' (already)'}")
