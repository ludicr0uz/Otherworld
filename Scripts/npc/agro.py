"""The patrol/agro switch on the controller's heartbeat: set up the patrol
once, then either chase (aggro) or check the senses and stroll (patrolling).

    heartbeat (possessed, stats applied)
      -> patrol setup, once per life                        (patrol.py)
      -> [Aggro?] yes ----------------------------------------> chase + swing
            no -> [player exists?] no -----------------------> patrol step
                    yes -> hurt? sight? touch? sound?        (senses.py)
                            any yes -> AggroReason = <sense>
                                    -> Aggro = true
                                    -> MaxWalkSpeed = RunSpeed
                                    -> [DebugMode?] log "[NPC-AGRO] <sense> -- <name>"
                                    -> chase + swing (this very heartbeat)
                            all no -> patrol step -> Delay

Nothing sets Aggro back to false: once a wanderer has found the player it
hunts for the rest of its life, which is the old behaviour. A "lose interest"
rule would be a new AgroSettings field and a branch at the top of the yes arm.

The per-creature numbers are an AgroSettings (forest_generator/npc_agro.py)
baked into pin literals, like every other NPC number: each creature already
has its own controller (see controller.py), so it gets its own senses too.
"""

import unreal

from combat.game_state import DEBUG_MODE_VAR, NOISE_TIME_VAR
from combat.paths import GAME_MODE_BP_PATH, GAME_MODE_CLASS_PATH
from forest_generator.npc_agro import AGRO_LOG_PREFIX
from npc.graph import (
    BEL, _asset_sub, _at, _connect, _log, _loose_pin, _node, _palette, _pin, _set,
)
from npc.nodes import (
    FN_CONCAT, FN_DISPLAY_NAME, FN_GET_GAME_MODE, FN_GET_PAWN, FN_GET_PLAYER_PAWN,
    FN_IS_VALID, FN_WARN, NODE_CAST_GAME_MODE,
)
from npc.patrol import _author_patrol_setup, _author_patrol_step, _author_walk_speed
from npc.paths import (
    AGGRO_REASON_VAR, AGGRO_VAR, NEXT_PATROL_VAR, PATROL_HOME_VAR,
    PATROL_READY_VAR, PATROL_TARGET_VAR, RUN_SPEED_VAR,
)
from npc.senses import _author_hearing, _author_hurt, _author_sight, _author_touch


def _declare(ed, name, pin_type):
    ed.remove_member_variable(name)
    if not ed.add_member_variable(name, pin_type):
        raise RuntimeError(f"could not declare {name}")


def _declare_agro_vars(ed):
    """All zero/false by default, which is the right start: not aggro, not set
    up, and a patrol point due immediately (NextPatrolTime 0)."""
    real = BEL.get_basic_type_by_name("real")
    vector = BEL.get_struct_type(unreal.Vector.static_struct())
    for name in (AGGRO_VAR, PATROL_READY_VAR):
        _declare(ed, name, BEL.get_basic_type_by_name("bool"))
    _declare(ed, AGGRO_REASON_VAR, BEL.get_basic_type_by_name("string"))
    for name in (RUN_SPEED_VAR, NEXT_PATROL_VAR):
        _declare(ed, name, real)
    for name in (PATROL_HOME_VAR, PATROL_TARGET_VAR):
        _declare(ed, name, vector)


def _noise_record_exists():
    """Is the GameMode's noise record there to be heard? build_weapons_and_combat
    declares it; a project that has not run that builder gets deaf wanderers
    (sight, touch and hurt still work) rather than a graph that will not
    compile. Loading it is also what puts its cast node in the palette."""
    bp = _asset_sub().load_asset(GAME_MODE_BP_PATH)
    return bool(bp) and NOISE_TIME_VAR in {
        str(v) for v in BEL.list_member_variable_names(bp, False)}


def _author_enter_agro(ed, reasons, chase_in, x0, y0):
    """Every sense's "yes" lands here: name the sense, flip the switch, run.

    ``reasons`` is [(sense name, exec pin)]. Each writes its own name into
    AggroReason and they join on one Set Aggro, so the log line, the speed
    and the switch are written once rather than once per sense.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    flip = keep(_at(ed.add_set_member_variable_node(AGGRO_VAR), x0 + 300, y0))
    _set(flip, AGGRO_VAR, "true")
    for i, (sense, exec_pin) in enumerate(reasons):
        why = keep(_at(ed.add_set_member_variable_node(AGGRO_REASON_VAR),
                       x0, y0 + 160 * i))
        _set(why, AGGRO_REASON_VAR, sense)
        _connect(exec_pin, _pin(why, "execute"))
        _connect(BEL.find_then_pin(why), _pin(flip, "execute"))

    ran, after = _author_walk_speed(ed, [BEL.find_then_pin(flip)], 1.0, x0 + 560, y0)
    made.extend(ran)

    reason = keep(_at(ed.add_get_member_variable_node(AGGRO_REASON_VAR),
                      x0 + 1800, y0 + 300))
    head = keep(_at(_node(ed, FN_CONCAT), x0 + 2040, y0 + 300))
    _set(head, "A", AGRO_LOG_PREFIX)
    _connect(_pin(reason, AGGRO_REASON_VAR, is_input=False), _pin(head, "B"))
    pawn = keep(_at(_node(ed, FN_GET_PAWN), x0 + 1800, y0 + 440))
    name = keep(_at(_node(ed, FN_DISPLAY_NAME), x0 + 2040, y0 + 440))
    _connect(_pin(pawn, "ReturnValue", is_input=False), _pin(name, "Object"))
    who = keep(_at(_node(ed, FN_CONCAT), x0 + 2280, y0 + 440))
    _set(who, "A", " -- ")
    _connect(_pin(name, "ReturnValue", is_input=False), _pin(who, "B"))
    line = keep(_at(_node(ed, FN_CONCAT), x0 + 2520, y0 + 300))
    _connect(_pin(head, "ReturnValue", is_input=False), _pin(line, "A"))
    _connect(_pin(who, "ReturnValue", is_input=False), _pin(line, "B"))
    # A developer line: PrintWarning puts it on screen as well as in the log,
    # so it is written only while the GameMode's DebugMode is on. One line per
    # wanderer per life.
    mode = keep(_at(_node(ed, FN_GET_GAME_MODE), x0 + 2280, y0 + 160))
    as_mode = keep(_at(_palette(ed, NODE_CAST_GAME_MODE), x0 + 2520, y0 - 160))
    _connect(_pin(mode, "ReturnValue", is_input=False), _pin(as_mode, "Object"))
    for pin in after:
        _connect(pin, _pin(as_mode, "execute"))
    flag = keep(_at(ed.add_get_member_variable_node(DEBUG_MODE_VAR,
                                                    GAME_MODE_CLASS_PATH),
                    x0 + 2760, y0 + 160))
    _connect(_loose_pin(as_mode, "AsBPThirdPersonGameMode", is_input=False),
             _pin(flag, "self"))
    debugging = keep(_at(ed.add_branch_node(), x0 + 3000, y0 - 160))
    _connect(_pin(flag, DEBUG_MODE_VAR, is_input=False), _pin(debugging, "Condition"))
    _connect(BEL.find_then_pin(as_mode), _pin(debugging, "execute"))
    say = keep(_at(_node(ed, FN_WARN), x0 + 3240, y0))
    _connect(_pin(line, "ReturnValue", is_input=False), _pin(say, "InString"))
    _connect(BEL.find_then_pin(debugging), _pin(say, "execute"))
    for tail in (BEL.find_then_pin(say), BEL.find_else_pin(debugging),
                 _pin(as_mode, "CastFailed", is_input=False)):
        _connect(tail, chase_in)
    return made


def _author_agro(ed, exec_in, chase_in, rest_in, agro, x0, y0):
    """Splice the patrol/agro switch between the heartbeat and the chase.

    ``exec_in`` is the heartbeat after this creature's stats; ``chase_in`` is
    the chase's first exec input (the pathfinding branch); ``rest_in`` is the
    heartbeat's Delay. Returns the nodes made, for the comment boxes.
    """
    _declare_agro_vars(ed)
    made = []

    setup, ready = _author_patrol_setup(ed, exec_in, agro, x0, y0)
    made.extend(setup)

    aggro = _at(ed.add_get_member_variable_node(AGGRO_VAR), x0 + 3000, y0 + 300)
    hunting = _at(ed.add_branch_node(), x0 + 3240, y0)
    _connect(_pin(aggro, AGGRO_VAR, is_input=False), _pin(hunting, "Condition"))
    _connect(ready, _pin(hunting, "execute"))
    _connect(BEL.find_then_pin(hunting), chase_in)

    # No player pawn (before possession, between a death and a restart): no
    # sense can say anything, so just keep strolling.
    player = _at(_node(ed, FN_GET_PLAYER_PAWN), x0 + 3240, y0 + 300)
    _set(player, "PlayerIndex", 0)
    there = _at(_node(ed, FN_IS_VALID), x0 + 3480, y0 + 300)
    _connect(_pin(player, "ReturnValue", is_input=False), _pin(there, "Object"))
    present = _at(ed.add_branch_node(), x0 + 3720, y0)
    _connect(_pin(there, "ReturnValue", is_input=False), _pin(present, "Condition"))
    _connect(BEL.find_else_pin(hunting), _pin(present, "execute"))
    made += [aggro, hunting, player, there, present]

    y = y0 + 1400
    reasons, nothing = [], [BEL.find_then_pin(present)]
    hurt, yes, nothing = _author_hurt(ed, nothing, x0 + 4000, y)
    made.extend(hurt)
    reasons.append(("hurt", yes))
    sight, yes, nothing = _author_sight(ed, nothing, agro, x0 + 5200, y)
    made.extend(sight)
    reasons.append(("sight", yes))
    touch, yes, nothing = _author_touch(ed, nothing, agro, x0 + 7400, y)
    made.extend(touch)
    reasons.append(("touch", yes))
    if _noise_record_exists():
        heard, yes, nothing = _author_hearing(ed, nothing, agro, x0 + 8600, y)
        made.extend(heard)
        reasons.append(("sound", yes))
    else:
        _log(f"note: {GAME_MODE_BP_PATH} has no noise record -- the wanderers "
             f"will not hear (run build_weapons_and_combat.py first)")

    made.extend(_author_enter_agro(ed, reasons, chase_in, x0 + 11600, y0))
    made.extend(_author_patrol_step(
        ed, nothing + [BEL.find_else_pin(present)], rest_in, agro,
        x0 + 11600, y0 + 2800))
    return made
