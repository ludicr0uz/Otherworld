"""The kneel that goes with the loot window: while it is open the player is
down on one knee over the body, and stays there.

    every Tick, once loot_tick has settled LootOpen:
        LootOpen != LootKneeling  ->  LootKneeling = LootOpen
                                      controller.SetIgnoreMoveInput(LootOpen)
        the pawn's BP_WeaponComponent.Searching = LootOpen

Searching is all the HUD says about the pose: the weapon component eases the
anim BP's PoseKneel from it (combat/weapon_component/pose_weights.py), and the
clip is combat/stance_clips.py's.

SetIgnoreMoveInput counts its calls, so it is made on the edge only (a true
per frame would take sixty falses to undo); LootKneeling is that edge's memory.
The walk is taken at the controller rather than as a speed of zero because
MaxWalkSpeed already has two writers a frame (sprint, the aim slowdown), and
rather than DisableMovement because that is save-and-exit's, which also gives
it back. The view is already still: the window frees the cursor, which stops
the mouse-look (cursor.py).
"""

import unreal

from combat.graph import BEL, _at, _connect, _loose_pin, _palette, _pin
from uebp.graph import out
from combat.nodes import FN_GET_COMP, FN_GET_PLAYER_PAWN, FN_IS_VALID, FN_NEQ_BB
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.weapon_component.pose_weights import SEARCHING_VAR
from graphics_menu.dev_guns import _branch, _call, _get
from graphics_menu.loot_consts import LOOT_KNEELING_VAR, LOOT_OPEN_VAR
from graphics_menu.loot_find import put

FN_IGNORE_MOVE = "/Script/Engine.Controller.SetIgnoreMoveInput"
NODE_CAST_WEAPON = "Utilities|Casting|CastToBP_WeaponComponent"


def author_kneel(ed, pc_out, in_execs, x0, y0):
    """The fragment (see the module docstring). Returns the exec tails."""
    made = []

    def is_open(x, y):
        return _get(ed, LOOT_OPEN_VAR, x, y, made)

    changed = _call(ed, FN_NEQ_BB, x0 + 240, y0 + 300, made, A=is_open(x0, y0 + 300),
                    B=_get(ed, LOOT_KNEELING_VAR, x0, y0 + 440, made))
    edge, same = _branch(ed, out(changed), in_execs, x0 + 500, y0, made)
    flow = put(ed, LOOT_KNEELING_VAR, is_open(x0 + 520, y0 + 300), [edge],
               x0 + 760, y0, made)
    still = _call(ed, FN_IGNORE_MOVE, x0 + 1020, y0, made, self=pc_out,
                  bNewMoveInput=is_open(x0 + 780, y0 + 300))
    _connect(flow, _pin(still, "execute"))

    pawn = out(_call(ed, FN_GET_PLAYER_PAWN, x0 + 1020, y0 + 440, made, PlayerIndex=0))
    here, no_pawn = _branch(ed, out(_call(ed, FN_IS_VALID, x0 + 1280, y0 + 440, made,
                                           Object=pawn)),
                            [BEL.find_then_pin(still), same], x0 + 1540, y0, made)
    comp = _call(ed, FN_GET_COMP, x0 + 1540, y0 + 440, made, self=pawn)
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)
    unreal.load_asset(WEAPON_COMP_BP_PATH)   # for its cast node
    cast = _at(_palette(ed, NODE_CAST_WEAPON), x0 + 1800, y0)
    made.append(cast)
    _connect(out(comp), _pin(cast, "Object"))
    _connect(here, _pin(cast, "execute"))
    wc = _loose_pin(cast, "AsBPWeaponComponent", is_input=False)
    told = _at(ed.add_set_member_variable_node(SEARCHING_VAR, WEAPON_COMP_CLASS_PATH),
               x0 + 2100, y0)
    made.append(told)
    _connect(wc, _pin(told, "self"))
    _connect(is_open(x0 + 1820, y0 + 300), _pin(told, SEARCHING_VAR))
    _connect(BEL.find_then_pin(cast), _pin(told, "execute"))
    ed.add_comment_to_nodes(
        "The kneel: while the loot window is open the player's weapon component "
        "is Searching (its pose weights kneel the body) and the controller "
        "ignores move input, taken and given back on LootOpen's edges.", made)
    return [BEL.find_then_pin(told), no_pawn, _pin(cast, "CastFailed", is_input=False)]
