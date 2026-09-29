"""The guard, authored into the weapon component's Tick: whether the player is
blocking this frame.

Only the stance lives here. What a block DOES to a swing -- the reduced damage
and the stamina it costs -- is resolved by the wanderer that swings
(npc/block.py), because the swing's damage and its bearing exist nowhere else.
That graph reads Blocking and writes Stamina on this component.
"""

from combat.graph import BEL, _at, _connect, _node, _pin, _set
from combat.nodes import FN_AND, FN_GREATER_FF, FN_IS_KEY_DOWN, FN_NOT
from combat.tuning import BLOCK_KEY, COMBAT


def _author_block(ed, pc_out, key_pin, exec_ins, x0, y0):
    """Blocking = BlockKeyDown AND Stamina > 0 AND NOT Sprinting.

    Nothing reads Held, so the guard works with empty hands, a gun or a
    mushroom alike -- and the condition never touches a null object on the
    frames nothing is equipped. After the sprint block, which writes
    Sprinting: running and guarding are exclusive, and sprint wins because it
    is the escape. Stored, not recomputed, for the usual pure-node reason: the
    fire gate and every wanderer's swing read the same answer.

    Returns the exec pin to carry on from.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    down = keep(_at(_node(ed, FN_IS_KEY_DOWN), x0, y0 + 240))
    _connect(pc_out, _pin(down, "self"))
    _connect(key_pin, _pin(down, "Key"))

    stamina = keep(_at(ed.add_get_member_variable_node("Stamina"), x0, y0 + 380))
    left = keep(_at(_node(ed, FN_GREATER_FF), x0 + 240, y0 + 380))
    _connect(_pin(stamina, "Stamina", is_input=False), _pin(left, "A"))
    _set(left, "B", 0.0)

    running = keep(_at(ed.add_get_member_variable_node("Sprinting"), x0, y0 + 500))
    still = keep(_at(_node(ed, FN_NOT), x0 + 240, y0 + 500))
    _connect(_pin(running, "Sprinting", is_input=False), _pin(still, "A"))

    able = keep(_at(_node(ed, FN_AND), x0 + 480, y0 + 440))
    _connect(_pin(left, "ReturnValue", is_input=False), _pin(able, "A"))
    _connect(_pin(still, "ReturnValue", is_input=False), _pin(able, "B"))
    guard = keep(_at(_node(ed, FN_AND), x0 + 720, y0 + 300))
    _connect(_pin(down, "ReturnValue", is_input=False), _pin(guard, "A"))
    _connect(_pin(able, "ReturnValue", is_input=False), _pin(guard, "B"))

    mark = keep(_at(ed.add_set_member_variable_node("Blocking"), x0 + 960, y0))
    _connect(_pin(guard, "ReturnValue", is_input=False), _pin(mark, "Blocking"))
    for e in exec_ins:
        _connect(e, _pin(mark, "execute"))

    ed.add_comment_to_nodes(
        f"{BLOCK_KEY}: guard while held, with or without a weapon, while there "
        f"is stamina and the player is not sprinting. A wanderer's swing from "
        f"within {COMBAT.block_half_angle_deg:.0f} deg of the facing does "
        f"{COMBAT.block_damage_scale:.0%} damage and costs "
        f"{COMBAT.block_stamina_per_hit:.0f} stamina (resolved in the NPC's "
        f"melee). The fire gate refuses while Blocking.",
        made)
    return BEL.find_then_pin(mark)
