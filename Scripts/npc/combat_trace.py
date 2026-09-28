"""The combat trace line a wanderer writes when its swing lands.

    [COMBAT-TRACE] melee #7 BP_ForestWanderer_Zombie_C_3 (hp 60.0, dead false)
        at X=... Y=... Z=... -> target BP_ThirdPersonCharacter_C_0
        at X=... Y=... Z=... dist 183.2 cm, dmg 10.0, target hp 40.0

(one line in the log; wrapped here). Written only while the GameMode's
CombatTrace flag is on -- see combat/game_state.py for the switch. The number
is the attacker's NpcId, the same one [NPC-SPAWN] and the debug-mode health bar
show, so a hit can be traced back to where that wanderer was spawned. Its own
health and Dead flag are in the line because the bug this was written for was
a corpse still swinging.

Log only, never on screen: ten wanderers around the player write a line every
1.5 s each.
"""

from combat.game_state import COMBAT_TRACE_PREFIX, COMBAT_TRACE_VAR, NPC_ID_VAR
from combat.paths import GAME_MODE_CLASS_PATH
from forest_generator.npc_placement import NPC_MELEE_DAMAGE
from npc.graph import BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set
from npc.nodes import (
    FN_BOOL_TO_STR, FN_CONCAT, FN_DISPLAY_NAME, FN_FLOAT_TO_STR,
    FN_GET_COMP, FN_GET_GAME_MODE, FN_INT_TO_STR, FN_PRINT, FN_VEC_TO_STR,
    NODE_CAST_GAME_MODE, NODE_CAST_HEALTH,
)
from npc.paths import HEALTH_CLASS_PATH


def _author_concat(ed, keep, parts, x0, y0):
    """Concat_StrStr down a list of literals and string output pins."""
    acc = None
    for i, part in enumerate(parts):
        if acc is None and isinstance(part, str):
            acc = part
            continue
        join = keep(_at(_node(ed, FN_CONCAT), x0 + 180 * i, y0))
        if isinstance(acc, str):
            _set(join, "A", acc)
        else:
            _connect(acc, _pin(join, "A"))
        if isinstance(part, str):
            _set(join, "B", part)
        else:
            _connect(part, _pin(join, "B"))
        acc = _pin(join, "ReturnValue", is_input=False)
    return acc


def _author_melee_trace(ed, exec_in, self_pawn_out, self_loc_out, player_out,
                        player_loc_out, gap_out, target_health_out, x0, y0):
    """[CombatTrace on?] -> attacker's health component -> print the line.

    ``target_health_out`` is the player's BP_HealthComponent, already cast by
    the melee; its Health is read after the hit was written, so the line quotes
    what the player has left.

    Returns ``(nodes, tails)``: every exec that has finished with the trace,
    logged or not, for the caller to carry on from.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    def to_str(fn, in_pin, src, x, y):
        n = keep(_at(_node(ed, fn), x, y))
        _connect(src, _pin(n, in_pin))
        return _pin(n, "ReturnValue", is_input=False)

    mode = keep(_at(_node(ed, FN_GET_GAME_MODE), x0, y0 + 240))
    as_mode = keep(_at(_palette(ed, NODE_CAST_GAME_MODE), x0 + 240, y0))
    _connect(_pin(mode, "ReturnValue", is_input=False), _pin(as_mode, "Object"))
    _connect(exec_in, _pin(as_mode, "execute"))
    flag = keep(_at(ed.add_get_member_variable_node(COMBAT_TRACE_VAR,
                                                    GAME_MODE_CLASS_PATH),
                    x0 + 480, y0 + 240))
    _connect(_loose_pin(as_mode, "AsBPThirdPersonGameMode", is_input=False),
             _pin(flag, "self"))
    tracing = keep(_at(ed.add_branch_node(), x0 + 720, y0))
    _connect(_pin(flag, COMBAT_TRACE_VAR, is_input=False), _pin(tracing, "Condition"))
    _connect(BEL.find_then_pin(as_mode), _pin(tracing, "execute"))

    # The attacker's own health component: its number, health and Dead flag.
    comp = keep(_at(_node(ed, FN_GET_COMP), x0 + 720, y0 + 240))
    _connect(self_pawn_out, _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)
    mine = keep(_at(_palette(ed, NODE_CAST_HEALTH), x0 + 960, y0))
    _connect(_pin(comp, "ReturnValue", is_input=False), _pin(mine, "Object"))
    _connect(BEL.find_then_pin(tracing), _pin(mine, "execute"))
    mine_out = _loose_pin(mine, "AsBPHealthComponent", is_input=False)

    def field(owner_out, name, x, y):
        g = keep(_at(ed.add_get_member_variable_node(name, HEALTH_CLASS_PATH), x, y))
        _connect(owner_out, _pin(g, "self"))
        return _pin(g, name, is_input=False)

    yb = y0 + 480
    npc_id = to_str(FN_INT_TO_STR, "InInt", field(mine_out, NPC_ID_VAR, x0, yb),
                    x0 + 240, yb)
    npc_hp = to_str(FN_FLOAT_TO_STR, "InDouble", field(mine_out, "Health", x0, yb + 120),
                    x0 + 240, yb + 120)
    npc_dead = to_str(FN_BOOL_TO_STR, "InBool", field(mine_out, "Dead", x0, yb + 240),
                      x0 + 240, yb + 240)
    npc_name = to_str(FN_DISPLAY_NAME, "Object", self_pawn_out, x0 + 240, yb + 360)
    npc_at = to_str(FN_VEC_TO_STR, "InVec", self_loc_out, x0 + 240, yb + 480)
    target_name = to_str(FN_DISPLAY_NAME, "Object", player_out, x0 + 240, yb + 600)
    target_at = to_str(FN_VEC_TO_STR, "InVec", player_loc_out, x0 + 240, yb + 720)
    dist = to_str(FN_FLOAT_TO_STR, "InDouble", gap_out, x0 + 240, yb + 840)
    target_hp = to_str(FN_FLOAT_TO_STR, "InDouble",
                       field(target_health_out, "Health", x0, yb + 960),
                       x0 + 240, yb + 960)

    line = _author_concat(ed, keep, [
        f"{COMBAT_TRACE_PREFIX}melee #", npc_id, " ", npc_name,
        " (hp ", npc_hp, ", dead ", npc_dead, ") at ", npc_at,
        " -> target ", target_name, " at ", target_at,
        " dist ", dist, f" cm, dmg {NPC_MELEE_DAMAGE:.1f}, target hp ", target_hp,
    ], x0 + 480, yb + 1100)

    say = keep(_at(_node(ed, FN_PRINT), x0 + 1200, y0))
    _connect(line, _pin(say, "InString"))
    _set(say, "bPrintToScreen", "false")
    _set(say, "bPrintToLog", "true")
    _set(say, "Duration", 0.0)
    _connect(BEL.find_then_pin(mine), _pin(say, "execute"))

    ed.add_comment_to_nodes(
        f"Combat trace (off unless the GameMode's {COMBAT_TRACE_VAR} is on): log "
        f"who landed this swing -- its number, where it stood -- and where the "
        f"target stood.", made)
    tails = [BEL.find_then_pin(say),
             _pin(mine, "CastFailed", is_input=False),
             BEL.find_else_pin(tracing),
             _pin(as_mode, "CastFailed", is_input=False)]
    return made, tails
