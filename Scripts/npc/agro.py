"""The patrol/agro steps the behaviour tree calls (npc/tree.py): is there a
player, one step per sense, and the stroll. The switch itself (Aggro set:
hunt) is the tree's Blackboard decorator, and the priority order of the
senses is the order of its Senses selector.

    BT_PlayerPresent: this pass's candidate among the living players
        (npc/target.py); someone: succeed / no one: fail
    BT_Hurt, BT_Sight, BT_Touch, BT_Sound                    (senses.py)
        yes -> AggroReason = <sense>
            -> Aggro = true
            -> [DebugMode?] log "[NPC-AGRO] <sense> -- <name>"
            -> Blackboard Aggro, AggroReason -> succeed (the hunt starts next pass)
        no  -> fail (the selector tries the next sense)
    BT_Stroll: the patrol step, then the walking speed        (patrol.py)

Nothing sets Aggro back to false: once a wanderer has found a player it
hunts for the rest of its life (that player while they live, then the nearest:
npc/target.py), which is the old behaviour. A "lose interest"
rule would be a new AgroSettings field and a branch at the top of the yes arm.

The per-creature numbers are the controller's Tune* variables (npc/tuned.py),
whose defaults are this creature's npc/monster_tuning.monster_specs(): the
AgroSettings in forest_generator/npc_agro.py under monster_tuning.csv. The
M panel's MONSTER SETTINGS tab writes them on a live wanderer.
"""

from uebp.vars import declare
from npc import controller_vars as NV

from combat.game_state import DEBUG_MODE_VAR
from net.state_consts import GAME_STATE_CLASS_PATH
from net.state_graph import game_state
from forest_generator.npc_agro import AGRO_LOG_PREFIX
from uebp.graph import _connect, _name_literal, _node, _pin, _set, else_, out, then
from npc.patrol import _author_patrol_step, _author_walk_speed
from npc.paths import (
    AGGRO_REASON_VAR, AGGRO_VAR, AGGRO_VOICES_VAR, BB_AGGRO_KEY, BB_REASON_KEY, SENSE_STEPS,
    STEP_PRESENT, STEP_STROLL,
)
from Sound.play import _author_random_sound
from npc.body_fx import heard_by_all
from npc.senses import _author_hearing, _author_hurt, _author_sight, _author_touch
from npc.target import _author_candidate
from uebp.nodes.actor import FN_ACTOR_LOC, FN_GET_PAWN
from uebp.nodes.ai import FN_BB_SET_BOOL, FN_BB_SET_STRING, FN_GET_BLACKBOARD
from uebp.nodes.system import (
    FN_CONCAT, FN_DISPLAY_NAME, FN_WARN)


def _declare_agro_vars(ed):
    """All zero/false by default, which is the right start: not aggro, not set
    up, and a patrol point due immediately (NextPatrolTime 0)."""
    declare(ed, NV.AGRO)


def _author_enter_agro(ed, reasons, chase_in):
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

    flip = keep(ed.add_set_member_variable_node(AGGRO_VAR))
    _set(flip, AGGRO_VAR, True)
    for sense, exec_pin in reasons:
        why = keep(ed.add_set_member_variable_node(AGGRO_REASON_VAR))
        _set(why, AGGRO_REASON_VAR, sense)
        _connect(exec_pin, _pin(why, "execute"))
        _connect(then(why), _pin(flip, "execute"))

    # Heard to notice: one of its AggroVoices, the once (the senses are not
    # asked again while Aggro stands). Empty on a creature with none -- the
    # wendigo, whose roar is a step of its own -- and then this is silence.
    pawn = keep(_node(ed, FN_GET_PAWN))
    here = keep(_node(ed, FN_ACTOR_LOC))
    _connect(out(pawn), _pin(here, "self"))
    cried, after_cry = _author_random_sound(ed, AGGRO_VOICES_VAR, out(here), then(flip),
                                            play=heard_by_all(ed))
    made.extend(cried)
    after = [after_cry]

    reason = keep(ed.add_get_member_variable_node(AGGRO_REASON_VAR))
    head = keep(_node(ed, FN_CONCAT))
    _set(head, "A", AGRO_LOG_PREFIX)
    _connect(out(reason, AGGRO_REASON_VAR), _pin(head, "B"))
    name = keep(_node(ed, FN_DISPLAY_NAME))
    _connect(out(pawn), _pin(name, "Object"))
    who = keep(_node(ed, FN_CONCAT))
    _set(who, "A", " -- ")
    _connect(out(name), _pin(who, "B"))
    line = keep(_node(ed, FN_CONCAT))
    _connect(out(head), _pin(line, "A"))
    _connect(out(who), _pin(line, "B"))
    # A developer line: PrintWarning puts it on screen as well as in the log,
    # so it is written only while the GameState's DebugMode is on. One line per
    # wanderer per life.
    state = game_state(ed, list(after))
    for n in state.nodes:
        keep(n)
    flag = keep(ed.add_get_member_variable_node(DEBUG_MODE_VAR, GAME_STATE_CLASS_PATH))
    _connect(state.pin, _pin(flag, "self"))
    debugging = keep(ed.add_branch_node())
    _connect(out(flag, DEBUG_MODE_VAR), _pin(debugging, "Condition"))
    _connect(state.then, _pin(debugging, "execute"))
    say = keep(_node(ed, FN_WARN))
    _connect(out(line), _pin(say, "InString"))
    _connect(then(debugging), _pin(say, "execute"))
    for tail in (then(say), else_(debugging), *state.fails):
        _connect(tail, chase_in)
    return made


def _author_tell_blackboard(ed, done_in):
    """Mirror Aggro and AggroReason into the Blackboard, where the tree's Hunt
    branch reads them (npc/tree.py). The controller's own variables stay the
    record every graph reads; the Blackboard is what the tree and its debugger
    see. Returns ``(nodes, exec_in)``."""
    made = []

    def keep(n):
        made.append(n)
        return n

    pawn = keep(_node(ed, FN_GET_PAWN))
    board = keep(_node(ed, FN_GET_BLACKBOARD))
    _connect(out(pawn), _pin(board, "Target"))
    board_out = out(board)
    flag = keep(_node(ed, FN_BB_SET_BOOL))
    _connect(board_out, _pin(flag, "self"))
    _connect(_name_literal(ed, BB_AGGRO_KEY), _pin(flag, "KeyName"))
    _set(flag, "BoolValue", True)
    reason = keep(ed.add_get_member_variable_node(AGGRO_REASON_VAR))
    why = keep(_node(ed, FN_BB_SET_STRING))
    _connect(board_out, _pin(why, "self"))
    _connect(_name_literal(ed, BB_REASON_KEY), _pin(why, "KeyName"))
    _connect(out(reason, AGGRO_REASON_VAR), _pin(why, "StringValue"))
    _connect(then(flag), _pin(why, "execute"))
    _connect(then(why), done_in)
    return made, _pin(flag, "execute")


def _author_agro_steps(ed, step, result, stock):
    """Author the tree's notice and patrol steps as controller events.

    ``step(name)`` makes the custom event BT_<name> and returns its exec
    output; ``result(value)`` makes a StepResult write and returns its
    exec input (npc/steps.py). Every sense is its own step, and the tree's
    Senses selector (npc/tree.py) holds the priority order: a sense's "yes"
    names itself, flips the switch, mirrors it into the Blackboard and
    succeeds; its "no" fails, so the selector tries the next.

    Returns ``(nodes, sense_steps)``: the nodes made, for the comment box, and
    the step names of the senses authored, in priority order.
    """
    made = []
    # No living player (before possession, between a death and a restart,
    # everyone dead): no sense can say anything, so the tree goes on to the
    # patrol. Otherwise the senses below are asked about this pass's
    # candidate, the controller's Target (npc/target.py).
    made += _author_candidate(ed, step(STEP_PRESENT), result(True), result(False))

    fragments = {"hurt": _author_hurt, "sight": _author_sight,
                 "touch": _author_touch, "sound": _author_hearing}
    reasons, senses = [], []
    for sense, name in SENSE_STEPS:
        nodes, yes, nothing = fragments[sense](ed, [step(name)])
        made.extend(nodes)
        missed = result(False)
        for pin in nothing:
            _connect(pin, missed)
        reasons.append((sense, yes))
        senses.append(name)

    told = result(True)
    tell, tell_in = _author_tell_blackboard(ed, told)
    made.extend(tell)
    made.extend(_author_enter_agro(ed, reasons, tell_in))
    # After the stroll order, the walking speed: every pass, so a tuned one
    # lands at once (patrol._author_walk_speed).
    walked, walk_tails, walk_in = _author_walk_speed(ed, [], True, stock)
    made.extend(walked)
    rested = result(True)
    for tail in walk_tails:
        _connect(tail, rested)
    made.extend(_author_patrol_step(ed, [step(STEP_STROLL)], walk_in))
    return made, senses
