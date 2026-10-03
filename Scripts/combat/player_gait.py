"""The player's gait: the jog plays the jog clip.

The body's locomotion blend space (a retargeted copy of the mannequin's
BS_Idle_Walk_Run) has its walk clips at 300 cm/s and its jog clips at 600, and
the anim Blueprint feeds it GroundSpeed, the character's own speed. The jog is
400 cm/s, so the player moved in a blend that was two thirds walk: they walked.

patch_gait() scales GroundSpeed in the anim Blueprint's event graph:

    GroundSpeed = VectorLengthXY(Velocity) x (JOG_ROW_CMS / COMBAT.jog_speed_cms)

so at the jog's speed the blend space is on its jog row, at half of it (the
aim's slowdown) on its walk row, and a sprint, past the last row, keeps the
jog clip as it always did. GroundSpeed is therefore in the blend space's
units, not cm/s; its other readers (ShouldMove, the stance clips' Move) only
ask whether the body is moving.

The rows themselves cannot be moved: a blend space looks its samples up in
data baked by UBlendSpace::ResampleData, which only the blend space editor's
widget calls. Samples moved, added or reordered from Python are saved but the
game goes on reading the old layout by index (tried: the idle played jog
clips).

The scale is baked from player_tuning.csv, so a jog nudged live on the PLAYER
SETTINGS tab keeps the old scale until the next weapons build.

The mannequin fallback's ABP_Unarmed is left alone: its speed is in cm/s for
whatever else wears it.
"""

from combat.graph import BEL, BGE, PIN, _assets, _connect, _log, _node, _pin, _set
from uebp.layout import arrange
from combat.nodes import FN_MUL_FF
from combat.tuning import COMBAT

# The Speed the blend space's jog row sits at.
JOG_ROW_CMS = 600.0
GROUND_SPEED = "GroundSpeed"
STOCK_DIR = "/Game/Characters/Mannequins/"


def gait_scale():
    """What GroundSpeed is multiplied by: the jog's speed lands on the jog row."""
    return JOG_ROW_CMS / COMBAT.jog_speed_cms


def _title(node):
    return str(BEL.get_node_title(node)).replace("\n", " ")


def speed_feeders(ed):
    """(the Set GroundSpeed node, the nodes wired into its value pin)."""
    sets = [n for n in ed.list_all_nodes() if _title(n) == f"Set {GROUND_SPEED}"]
    if len(sets) != 1:
        raise RuntimeError(f"{len(sets)} Set {GROUND_SPEED} nodes, expected 1")
    value = _pin(sets[0], GROUND_SPEED)
    return sets[0], [PIN.get_owning_node(p) for p in PIN.list_connected_pins(value)]


def is_scale_node(node):
    """Is this the multiply patch_gait() put in front of Set GroundSpeed?"""
    names = {str(PIN.get_pin_name(p)) for p in BEL.list_input_pins(node)}
    return names == {"A", "B"}


def patch_gait(skin):
    """Scale the GroundSpeed the skin's anim Blueprint feeds its blend space."""
    if skin.anim_bp.startswith(STOCK_DIR):
        _log("player gait: the mannequin's anim Blueprint is left in cm/s")
        return
    bp = _assets().load_asset(skin.anim_bp)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    setter, feeders = speed_feeders(ed)
    if len(feeders) != 1:
        raise RuntimeError(f"Set {GROUND_SPEED} has {len(feeders)} feeders, expected 1")
    scale = feeders[0]
    if not is_scale_node(scale):
        # First build on this anim Blueprint: splice the multiply in.
        length = _pin(scale, "ReturnValue", is_input=False)
        value = _pin(setter, GROUND_SPEED)
        PIN.break_pin_links(value)
        scale = _node(ed, FN_MUL_FF)
        _connect(length, _pin(scale, "A"))
        _connect(_pin(scale, "ReturnValue", is_input=False), value)
    # The constant is on B: a math node's A holds no literal.
    _set(scale, "B", round(gait_scale(), 4))
    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{bp.get_name()} failed to compile after the gait patch")
    _assets().save_loaded_asset(bp)
    _log(f"player gait: GroundSpeed x {gait_scale():.3f}, so the "
         f"{COMBAT.jog_speed_cms:.0f} cm/s jog plays the blend space's "
         f"{JOG_ROW_CMS:.0f} row: the jog clip ({bp.get_name()})")
