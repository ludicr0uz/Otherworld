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
from uebp.graph import _connect, _loose_pin, _node, _palette, _pin, _set, else_, out, then
from npc.paths import HEALTH_CLASS_PATH, HIT_DAMAGE_VAR
from uebp.nodes.actor import FN_GET_COMP
from uebp.nodes.palette import NODE_CAST_GAME_MODE, NODE_CAST_HEALTH
from uebp.nodes.system import (
    FN_BOOL_TO_STR, FN_CONCAT, FN_DISPLAY_NAME, FN_FLOAT_TO_STR, FN_GET_GAME_MODE,
    FN_INT_TO_STR, FN_PRINT, FN_VEC_TO_STR)
from combat import health_vars as HV


def _author_concat(ed, keep, parts):
    """Concat_StrStr down a list of literals and string output pins."""
    acc = None
    for part in parts:
        if acc is None and isinstance(part, str):
            acc = part
            continue
        join = keep(_node(ed, FN_CONCAT))
        if isinstance(acc, str):
            _set(join, "A", acc)
        else:
            _connect(acc, _pin(join, "A"))
        if isinstance(part, str):
            _set(join, "B", part)
        else:
            _connect(part, _pin(join, "B"))
        acc = out(join)
    return acc


def _author_melee_trace(ed, exec_in, self_pawn_out, self_loc_out, player_out,
                        player_loc_out, gap_out, target_health_out):
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

    def to_str(fn, in_pin, src):
        n = keep(_node(ed, fn))
        _connect(src, _pin(n, in_pin))
        return out(n)

    mode = keep(_node(ed, FN_GET_GAME_MODE))
    as_mode = keep(_palette(ed, NODE_CAST_GAME_MODE))
    _connect(out(mode), _pin(as_mode, "Object"))
    _connect(exec_in, _pin(as_mode, "execute"))
    flag = keep(ed.add_get_member_variable_node(COMBAT_TRACE_VAR, GAME_MODE_CLASS_PATH))
    _connect(_loose_pin(as_mode, "AsBPThirdPersonGameMode", is_input=False),
             _pin(flag, "self"))
    tracing = keep(ed.add_branch_node())
    _connect(out(flag, COMBAT_TRACE_VAR), _pin(tracing, "Condition"))
    _connect(then(as_mode), _pin(tracing, "execute"))

    # The attacker's own health component: its number, health and Dead flag.
    comp = keep(_node(ed, FN_GET_COMP))
    _connect(self_pawn_out, _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)
    mine = keep(_palette(ed, NODE_CAST_HEALTH))
    _connect(out(comp), _pin(mine, "Object"))
    _connect(then(tracing), _pin(mine, "execute"))
    mine_out = _loose_pin(mine, "AsBPHealthComponent", is_input=False)

    def field(owner_out, name):
        g = keep(ed.add_get_member_variable_node(name, HEALTH_CLASS_PATH))
        _connect(owner_out, _pin(g, "self"))
        return out(g, name)

    npc_id = to_str(FN_INT_TO_STR, "InInt", field(mine_out, NPC_ID_VAR))
    npc_hp = to_str(FN_FLOAT_TO_STR, "InDouble", field(mine_out, HV.Health))
    npc_dead = to_str(FN_BOOL_TO_STR, "InBool", field(mine_out, HV.Dead))
    npc_name = to_str(FN_DISPLAY_NAME, "Object", self_pawn_out)
    npc_at = to_str(FN_VEC_TO_STR, "InVec", self_loc_out)
    target_name = to_str(FN_DISPLAY_NAME, "Object", player_out)
    target_at = to_str(FN_VEC_TO_STR, "InVec", player_loc_out)
    dist = to_str(FN_FLOAT_TO_STR, "InDouble", gap_out)
    target_hp = to_str(FN_FLOAT_TO_STR, "InDouble", field(target_health_out, HV.Health))

    # What this swing dealt, after the player's guard (npc/block.py).
    dealt = to_str(FN_FLOAT_TO_STR, "InDouble",
                   out(keep(ed.add_get_member_variable_node(HIT_DAMAGE_VAR)), HIT_DAMAGE_VAR))

    line = _author_concat(ed, keep, [
        f"{COMBAT_TRACE_PREFIX}melee #", npc_id, " ", npc_name,
        " (hp ", npc_hp, ", dead ", npc_dead, ") at ", npc_at,
        " -> target ", target_name, " at ", target_at,
        " dist ", dist, " cm, dmg ", dealt, ", target hp ", target_hp,
    ])

    say = keep(_node(ed, FN_PRINT))
    _connect(line, _pin(say, "InString"))
    _set(say, "bPrintToScreen", "false")
    _set(say, "bPrintToLog", "true")
    _set(say, "Duration", 0.0)
    _connect(then(mine), _pin(say, "execute"))

    ed.add_comment_to_nodes(
        f"Combat trace (off unless the GameMode's {COMBAT_TRACE_VAR} is on): log "
        f"who landed this swing -- its number, where it stood -- and where the "
        f"target stood.", made)
    tails = [then(say), out(mine, "CastFailed"), else_(tracing), out(as_mode, "CastFailed")]
    return made, tails
