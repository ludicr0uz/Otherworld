"""The player steps round after the view while standing: the sample's own
turn-in-place, switched on.

The motion matching's root lags the capsule (Offset Root Bone, Accumulate),
and the player's capsule takes the view's yaw at once. The sample walks the
root back under it with its turn-in-place databases, which its chooser offers
only while ShouldTurnInPlace: the root 50 degrees or more off the actor AND
(InputState.WantsToAim OR the frame it stopped). The patched properties
function never filled WantsToAim, so a standing player's legs stayed planted
while the view turned and the aim offset wound the spine round over them, up
to a full circle (measured: the root 270 degrees behind, the pick an idle,
PSD_Dense_Stand_Idles the one database offered).

So WantsToAim is filled here: true while the pawn stands still and is not
lying down. The player faces the view whatever it holds, as the sample's
character does only while it aims, so it is not read off the weapon:
    standing still   the sample reads WantsToAim in one more place, the
                     thresholds between its strafe loops (narrower aiming).
                     Moving, the flag stays false and those stay as they were
    not prone        the prone body is the weapon layers' clip over this
                     graph (stance_clips.py): there are no steps under it to
                     take, and the root is left as it was
The velocity and the stance are the movement's own on every machine, so
another player's copy and the server's turn with it and nothing replicates.
Which clip turns it, and how fast, is the sample's chooser's and its
databases' business (the crouched set has its own).

With a gun up there was a second cause. The sample lets the root go back
under the capsule at once (Offset Root Bone's mode Release, for the rotation
and for the translation) while a montage plays in its slot, asking
IsSlotActive(DefaultSlot). The weapon layers' ready and hold poses play in a
slot of that name on the same instance (anim_blueprint.AIM_SLOT), so with a
gun raised, the sights up or a knife in hand the root never lagged: nothing
for a turn clip to walk back, and the legs spun on the spot with the capsule
(measured down the sights: the root 0.4 degrees off through a half circle,
both feet sliding all the way). The two functions that pick the mode
(ROOT_MODE_GRAPHS) ask OwTraversing here instead: the one case in which the
sample's own slot is in the pose line (gas_traversal_slot.py).
"""
from combat.gas_locomotion_consts import TRAVERSING
from uebp.graph import BEL, BGE, PIN, _connect, _pin, out
from uebp.nodes.actor import FN_VELOCITY
from uebp.nodes.math import FN_AND, FN_LESS_FF, FN_NEQ_II, FN_VSIZE_XY
from uebp.nodes.move import FN_GET_STANCE

# The struct's field (S_PlayerInputState) the sample's ShouldTurnInPlace reads.
FIELD = "WantsToAim"
# Under this the pawn stands. A turn clip moves the root, never the capsule,
# so the flag holds through the turn it starts.
STANDING_BELOW_CMS = 10.0
PRONE = "2"   # GetStance: 0 standing, 1 crouched, 2 prone
# The sample's functions that pick Offset Root Bone's rotation and translation
# mode, each behind a Branch on IsSlotActive(DefaultSlot).
ROOT_MODE_GRAPHS = ("Get_OffsetRootRotationMode", "Get_OffsetRootTranslationMode")
SLOT_PIN = "SlotNodeName"


def turns_in_place(g, char):
    """The pin for InputState.WantsToAim: standing still and not prone."""
    speed = g.call(FN_VSIZE_XY, A=out(g.call(FN_VELOCITY, self=char)))
    still = g.call(FN_LESS_FF, A=out(speed), B=str(STANDING_BELOW_CMS))
    upright = g.call(FN_NEQ_II, A=out(g.call(FN_GET_STANCE, Character=char)), B=PRONE)
    return out(g.call(FN_AND, A=out(still), B=out(upright)))


def release_flags(ed):
    """(Branch, the node feeding its Condition) for the branch of a root-mode
    function that releases the root: fed by the slot question as the sample
    has it, by Get OwTraversing once patched."""
    found = []
    for node in ed.list_all_nodes():
        if node.get_class().get_name() != "K2Node_IfThenElse":
            continue
        for link in PIN.list_connected_pins(_pin(node, "Condition")):
            source = PIN.get_owning_node(link)
            names = {str(PIN.get_pin_name(q)) for q in BEL.list_input_pins(source)}
            if SLOT_PIN in names or str(BEL.get_node_title(source)) == f"Get {TRAVERSING}":
                found.append((node, source))
    return found


def root_modes_ask_traversing(bp):
    """Each root-mode function releases the root while OwTraversing, not while
    the slot's name is busy. Idempotent: a patched function is left alone."""
    for name in ROOT_MODE_GRAPHS:
        ed = BGE.get_graph_editor_by_name(bp, name)
        found = release_flags(ed) if ed else []
        if not found and ed:
            # A patched function whose Get OwTraversing went with a failed
            # build: its Branch is the one with nothing on the Condition.
            bare = [n for n in ed.list_all_nodes()
                    if n.get_class().get_name() == "K2Node_IfThenElse"
                    and not PIN.list_connected_pins(_pin(n, "Condition"))]
            if len(bare) == 1:
                flag = ed.add_get_member_variable_node(TRAVERSING)
                _connect(out(flag, TRAVERSING), _pin(bare[0], "Condition"))
                continue
        if len(found) != 1:
            raise RuntimeError(f"{name}: expected one Branch on the slot question, "
                               f"found {len(found)}")
        branch, source = found[0]
        if str(BEL.get_node_title(source)) == f"Get {TRAVERSING}":
            continue
        ed.remove_nodes([source])
        flag = ed.add_get_member_variable_node(TRAVERSING)
        _connect(out(flag, TRAVERSING), _pin(branch, "Condition"))
