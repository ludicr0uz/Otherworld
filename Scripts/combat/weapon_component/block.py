"""The guard, authored into the weapon component's Tick: whether the player is
blocking this frame.

Only the stance lives here. What a block DOES to a swing -- the reduced damage
and the stamina it costs -- is resolved by the wanderer that swings
(npc/block.py), because the swing's damage and its bearing exist nowhere else.
That graph reads Blocking on this component and spends the movement's stamina.

This is the owning machine's Blocking, off its own key. The server's copy of
a client's character decides its own from what the client reports (holds.py),
and that is the one a wanderer's swing reads.
"""

from uebp.graph import _connect, _node, _pin, _set, out, then
from combat.tuning import BLOCK_KEY, COMBAT
from uebp.nodes.actor import FN_IS_KEY_DOWN
from uebp.nodes.math import FN_AND, FN_GREATER_FF, FN_NOT, FN_OR
from combat.strike_vars import BlockForced
from combat.weapon_component import vars as WV


def _author_block(ed, pc_out, key_pin, exec_ins):
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

    down = keep(_node(ed, FN_IS_KEY_DOWN))
    _connect(pc_out, _pin(down, "self"))
    _connect(key_pin, _pin(down, "Key"))

    # ...or a probe holding it: no key can be injected into a headless game.
    forced = keep(ed.add_get_member_variable_node(BlockForced))
    held_down = keep(_node(ed, FN_OR))
    _connect(out(down), _pin(held_down, "A"))
    _connect(out(forced, BlockForced), _pin(held_down, "B"))
    down = held_down

    stamina = keep(ed.add_get_member_variable_node(WV.Stamina))
    left = keep(_node(ed, FN_GREATER_FF))
    _connect(out(stamina, WV.Stamina), _pin(left, "A"))
    _set(left, "B", 0.0)

    running = keep(ed.add_get_member_variable_node(WV.Sprinting))
    still = keep(_node(ed, FN_NOT))
    _connect(out(running, WV.Sprinting), _pin(still, "A"))

    able = keep(_node(ed, FN_AND))
    _connect(out(left), _pin(able, "A"))
    _connect(out(still), _pin(able, "B"))
    guard = keep(_node(ed, FN_AND))
    _connect(out(down), _pin(guard, "A"))
    _connect(out(able), _pin(guard, "B"))

    mark = keep(ed.add_set_member_variable_node(WV.Blocking))
    _connect(out(guard), _pin(mark, WV.Blocking))
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
    return then(mark)
