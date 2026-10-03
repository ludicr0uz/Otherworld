"""The patrol/agro steps the behaviour tree calls (npc/tree.py): is there a
player, one step per sense, and the stroll. The switch itself (Aggro set:
hunt) is the tree's Blackboard decorator, and the priority order of the
senses is the order of its Senses selector.

    BT_PlayerPresent: [player exists?] yes: succeed / no: fail
    BT_Hurt, BT_Sight, BT_Touch, BT_Sound                    (senses.py)
        yes -> AggroReason = <sense>
            -> Aggro = true
            -> [DebugMode?] log "[NPC-AGRO] <sense> -- <name>"
            -> Blackboard Aggro, AggroReason -> succeed (the hunt starts next pass)
        no  -> fail (the selector tries the next sense)
    BT_Stroll: the patrol step, then the walking speed        (patrol.py)

Nothing sets Aggro back to false: once a wanderer has found the player it
hunts for the rest of its life, which is the old behaviour. A "lose interest"
rule would be a new AgroSettings field and a branch at the top of the yes arm.

The per-creature numbers are the controller's Tune* variables (npc/tuned.py),
whose defaults are this creature's npc/monster_tuning.monster_specs(): the
AgroSettings in forest_generator/npc_agro.py under monster_tuning.csv. The
M panel's MONSTER SETTINGS tab writes them on a live wanderer.
"""

import unreal

from combat.game_state import DEBUG_MODE_VAR, NOISE_TIME_VAR
from combat.paths import GAME_MODE_BP_PATH, GAME_MODE_CLASS_PATH
from forest_generator.npc_agro import AGRO_LOG_PREFIX
from npc.graph import (
    BEL, _asset_sub, _at, _connect, _log, _loose_pin, _name_literal, _node,
    _palette, _pin, _set,
)
from npc.nodes import (
    FN_BB_SET_BOOL, FN_BB_SET_STRING, FN_CONCAT, FN_DISPLAY_NAME,
    FN_GET_BLACKBOARD, FN_GET_GAME_MODE, FN_GET_PAWN, FN_GET_PLAYER_PAWN,
    FN_IS_VALID, FN_WARN, NODE_CAST_GAME_MODE,
)
from npc.patrol import _author_patrol_step, _author_walk_speed
from npc.paths import (
    AGGRO_REASON_VAR, AGGRO_VAR, BB_AGGRO_KEY, BB_REASON_KEY, NEXT_PATROL_VAR,
    PATROL_HOME_VAR, PATROL_READY_VAR, PATROL_TARGET_VAR, RUN_SPEED_VAR,
    SENSE_STEPS, STEP_PRESENT, STEP_STROLL,
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
    """Every sense's "yes" lands here: name the sense, flip the switch.
    ``chase_in`` is what runs after (the Blackboard write).

    ``reasons`` is [(sense name, exec pin)]. Each writes its own name into
    AggroReason and they join on one Set Aggro, so the log line and the
    switch are written once rather than once per sense. The run speed is the
    Chase step's (npc/steps.py).
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

    after = [BEL.find_then_pin(flip)]

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


def _author_tell_blackboard(ed, done_in, x0, y0):
    """Mirror Aggro and AggroReason into the Blackboard, where the tree's Hunt
    branch reads them (npc/tree.py). The controller's own variables stay the
    record every graph reads; the Blackboard is what the tree and its debugger
    see. Returns ``(nodes, exec_in)``."""
    made = []

    def keep(n):
        made.append(n)
        return n

    pawn = keep(_at(_node(ed, FN_GET_PAWN), x0, y0 + 300))
    board = keep(_at(_node(ed, FN_GET_BLACKBOARD), x0 + 240, y0 + 300))
    _connect(_pin(pawn, "ReturnValue", is_input=False), _pin(board, "Target"))
    board_out = _pin(board, "ReturnValue", is_input=False)
    flag = keep(_at(_node(ed, FN_BB_SET_BOOL), x0 + 480, y0))
    _connect(board_out, _pin(flag, "self"))
    _connect(_name_literal(ed, BB_AGGRO_KEY, x0 + 240, y0 + 440), _pin(flag, "KeyName"))
    _set(flag, "BoolValue", "true")
    reason = keep(_at(ed.add_get_member_variable_node(AGGRO_REASON_VAR),
                      x0 + 480, y0 + 300))
    why = keep(_at(_node(ed, FN_BB_SET_STRING), x0 + 760, y0))
    _connect(board_out, _pin(why, "self"))
    _connect(_name_literal(ed, BB_REASON_KEY, x0 + 480, y0 + 440), _pin(why, "KeyName"))
    _connect(_pin(reason, AGGRO_REASON_VAR, is_input=False), _pin(why, "StringValue"))
    _connect(BEL.find_then_pin(flag), _pin(why, "execute"))
    _connect(BEL.find_then_pin(why), done_in)
    return made, _pin(flag, "execute")


def _author_player_present(ed, exec_in, yes_in, no_in, x0, y0):
    """No player pawn (before possession, between a death and a restart): no
    sense can say anything, so the tree goes on to the patrol."""
    player = _at(_node(ed, FN_GET_PLAYER_PAWN), x0, y0 + 300)
    _set(player, "PlayerIndex", 0)
    there = _at(_node(ed, FN_IS_VALID), x0 + 240, y0 + 300)
    _connect(_pin(player, "ReturnValue", is_input=False), _pin(there, "Object"))
    present = _at(ed.add_branch_node(), x0 + 480, y0)
    _connect(_pin(there, "ReturnValue", is_input=False), _pin(present, "Condition"))
    _connect(exec_in, _pin(present, "execute"))
    _connect(BEL.find_then_pin(present), yes_in)
    _connect(BEL.find_else_pin(present), no_in)
    return [player, there, present]


def _author_agro_steps(ed, step, result, stock, x0, y0):
    """Author the tree's notice and patrol steps as controller events.

    ``step(name, x, y)`` makes the custom event BT_<name> and returns its exec
    output; ``result(value, x, y)`` makes a StepResult write and returns its
    exec input (npc/steps.py). Every sense is its own step, and the tree's
    Senses selector (npc/tree.py) holds the priority order: a sense's "yes"
    names itself, flips the switch, mirrors it into the Blackboard and
    succeeds; its "no" fails, so the selector tries the next.

    Returns ``(nodes, sense_steps)``: the nodes made, for the comment box, and
    the step names of the senses authored, in priority order.
    """
    made = []
    made += _author_player_present(
        ed, step(STEP_PRESENT, x0 + 3000, y0), result(True, x0 + 3800, y0),
        result(False, x0 + 3800, y0 + 160), x0 + 3240, y0)

    noise = _noise_record_exists()
    if not noise:
        _log(f"note: {GAME_MODE_BP_PATH} has no noise record -- the wanderers "
             f"will not hear (run build_weapons_and_combat.py first)")
    fragments = {"hurt": lambda e, x, y: _author_hurt(ed, e, x, y),
                 "sight": lambda e, x, y: _author_sight(ed, e, x, y),
                 "touch": lambda e, x, y: _author_touch(ed, e, x, y),
                 "sound": lambda e, x, y: _author_hearing(ed, e, x, y)}
    reasons, senses = [], []
    y = y0 + 1400
    for sense, name in SENSE_STEPS:
        if sense == "sound" and not noise:
            continue
        nodes, yes, nothing = fragments[sense](
            [step(name, x0 + 3700, y)], x0 + 4000, y)
        made.extend(nodes)
        missed = result(False, x0 + 7000, y + 600)
        for pin in nothing:
            _connect(pin, missed)
        reasons.append((sense, yes))
        senses.append(name)
        y += 1200

    told = result(True, x0 + 16000, y0)
    tell, tell_in = _author_tell_blackboard(ed, told, x0 + 15000, y0)
    made.extend(tell)
    made.extend(_author_enter_agro(ed, reasons, tell_in, x0 + 11600, y0))
    # After the stroll order, the walking speed: every pass, so a tuned one
    # lands at once (patrol._author_walk_speed).
    walked, walk_tails, walk_in = _author_walk_speed(ed, [], True, stock,
                                                      x0 + 14200, y0 + 2800)
    made.extend(walked)
    rested = result(True, x0 + 15600, y0 + 2800)
    for tail in walk_tails:
        _connect(tail, rested)
    made.extend(_author_patrol_step(
        ed, [step(STEP_STROLL, x0 + 11300, y0 + 2800)], walk_in,
        x0 + 11600, y0 + 2800))
    return made, senses
