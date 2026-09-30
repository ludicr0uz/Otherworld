"""The controller's steps: one custom event per behaviour-tree step, BT_<Step>.

The tree (npc/tree.py) decides what runs and in which order; these events
are the work. The step task (npc/step_task.py) calls the event its node
names and finishes with StepResult, which every exit of every step writes:

    BT_Pulse   [possessed?] no: fail
                 yes -> corpse gate (Dead: corpse, StopLogic, fail)   corpse.py
                     -> stats and voice                               stats.py
                     -> patrol setup, once per life -> succeed        patrol.py
    BT_Chase   move order at the player -> succeed                    chase.py
    BT_Swing   in range and off cooldown? swing -> succeed            melee.py
    BT_PlayerPresent, BT_<Sense>..., BT_Stroll                        agro.py

Each event runs to its end in one call: no Delay and no latent node, so the
task reads StepResult straight after calling it.
"""

from forest_generator.npc_placement import (
    NPC_MELEE_DAMAGE, NPC_MELEE_INTERVAL_S, NPC_MELEE_RANGE_CM,
    NPC_VOICE_MAX_S, NPC_VOICE_MIN_S,
)
from npc.agro import _author_agro_steps, _declare_agro_vars
from npc.chase import _author_chase
from npc.corpse import _author_corpse_gate
from npc.graph import BEL, _at, _connect, _log, _node, _pin, _set
from npc.melee import _author_melee
from npc.nodes import FN_GET_PAWN, FN_IS_VALID
from npc.patrol import _author_patrol_setup
from npc.paths import (
    STEP_CHASE, STEP_EVENT_PREFIX, STEP_PULSE, STEP_RESULT_VAR, STEP_SWING,
)
from npc.stats import _author_stats_and_voice


class _Steps:
    """Makes the step events and the StepResult writes they end on."""

    def __init__(self, ed):
        self.ed = ed

    def event(self, name, x, y):
        """A new BT_<name> custom event; returns its exec output."""
        full = f"{STEP_EVENT_PREFIX}{name}"
        node = _at(self.ed.add_custom_event_node(full), x, y)
        title = str(BEL.get_node_title(node)).replace(" ", "")
        # A name still held by the skeleton class comes back suffixed, and the
        # task's call by name would then miss it.
        if full.replace(" ", "") not in title or f"{full}_" in title:
            raise RuntimeError(f"custom event {full!r} came back as {title!r}")
        return BEL.find_then_pin(node)

    def result_node(self, value, x, y):
        node = _at(self.ed.add_set_member_variable_node(STEP_RESULT_VAR), x, y)
        _set(node, STEP_RESULT_VAR, "true" if value else "false")
        return node

    def result(self, value, x, y):
        """A StepResult write; returns its exec input."""
        return _pin(self.result_node(value, x, y), "execute")


def _author_pulse(ed, steps, agro, health, x0, y0):
    """BT_Pulse: the part of every pass that runs before the tree chooses
    between hunting, noticing and patrolling. Returns the nodes by concern,
    for the comment boxes."""
    # The gate is not defensive padding: the tree starts at possession, but a
    # pawn can be gone (destroyed, unpossessed) while the controller lives.
    own_pawn = _at(_node(ed, FN_GET_PAWN), x0 - 220, y0 - 320)
    possessed = _at(_node(ed, FN_IS_VALID), x0 + 40, y0 - 320)
    _connect(_pin(own_pawn, "ReturnValue", is_input=False),
             _pin(possessed, "Object"))
    gate = _at(ed.add_branch_node(), x0 + 300, y0 - 200)
    _connect(_pin(possessed, "ReturnValue", is_input=False),
             _pin(gate, "Condition"))
    _connect(steps.event(STEP_PULSE, x0, y0 - 200), _pin(gate, "execute"))
    _connect(BEL.find_else_pin(gate), steps.result(False, x0 + 600, y0 - 60))

    # First thing with a pawn: is it a corpse? A dead wanderer's tree stops
    # there, so nothing below -- stats, voice, patrol, chase, melee -- can run
    # for it. See npc/corpse.py.
    _, alive, ended = _author_corpse_gate(ed, BEL.find_then_pin(gate),
                                          x0 - 200, y0 - 1400)
    _connect(ended, steps.result(False, x0 + 2200, y0 - 1400))
    # This creature's health, applied once, and its voice on a timer. Both
    # need the pawn, which is why they sit after the gate.
    extras, after_extras = _author_stats_and_voice(
        ed, alive, x0 - 200, y0 + 1400, health, NPC_VOICE_MIN_S, NPC_VOICE_MAX_S)
    setup, ready = _author_patrol_setup(ed, after_extras, agro, x0 - 200, y0 + 3000)
    _connect(ready, steps.result(True, x0 + 2000, y0 + 3000))
    return [own_pawn, possessed, gate], extras, setup


def _author_steps(ed, agro, health, melee_anim, x0, y0):
    """Author every step event into the controller's event graph.

    Returns the sense step names authored, in priority order (sound is
    dropped when the GameMode has no noise record)."""
    ed.remove_member_variable(STEP_RESULT_VAR)
    if not ed.add_member_variable(STEP_RESULT_VAR, BEL.get_basic_type_by_name("bool")):
        raise RuntimeError(f"could not declare {STEP_RESULT_VAR}")
    _declare_agro_vars(ed)
    steps = _Steps(ed)

    gate, extras, setup = _author_pulse(ed, steps, agro, health, x0, y0)
    ed.add_comment_to_nodes(
        "BT_Pulse: the tree's first step on every pass. No pawn: fail. A "
        "corpse: stop the tree. Otherwise this creature's stats and voice, "
        "and the patrol set up once per life.", gate + setup)
    ed.add_comment_to_nodes(
        f"This creature's own health ({health:.0f}), applied once on the first "
        f"pass after possession, and its voice every "
        f"{NPC_VOICE_MIN_S:.0f}-{NPC_VOICE_MAX_S:.0f} s. Health is set from "
        f"here rather than on the pawn because MaxHealth lives on an INHERITED "
        f"component, and Unreal keeps a child Blueprint's override of one in an "
        f"InheritableComponentHandler that Python cannot reach.",
        extras)

    cx, cy = x0 + 3000, y0 - 3000
    chase, after_move = _author_chase(ed, steps.event(STEP_CHASE, cx - 300, cy + 200),
                                      cx, cy)
    for tail in after_move:
        _connect(tail, steps.result(True, cx + 1300, cy))
    ed.add_comment_to_nodes(
        "BT_Chase: a move order at the player, pathfinding when both ends are "
        "on the navmesh -- which is what runs the NPC around trees -- and a "
        "straight-line move order when either end is not.", chase)

    sx, sy = x0 + 5000, y0 - 3000
    rest = steps.result_node(True, sx + 5200, sy + 600)
    swing_in = steps.event(STEP_SWING, sx - 300, sy)
    melee = _author_melee(ed, [swing_in], rest, sx, sy, melee_anim=melee_anim)
    if melee is None:
        _connect(swing_in, _pin(rest, "execute"))
    else:
        ed.add_comment_to_nodes(
            f"BT_Swing: within {NPC_MELEE_RANGE_CM:.0f} cm and off cooldown, "
            f"swing for {NPC_MELEE_DAMAGE:.0f} damage, then arm the next swing "
            f"{NPC_MELEE_INTERVAL_S} s out. The cooldown is per controller, so "
            f"a pack does not hit in lockstep.", melee)

    agro_nodes, senses = _author_agro_steps(ed, steps.event, steps.result, agro,
                                            x0 - 200, y0 + 5000)
    ed.add_comment_to_nodes(
        f"Patrol until noticed: stroll a {agro.patrol_radius_cm / 100:.0f} m "
        f"circle about the spawn point at {agro.patrol_speed_scale:.0%} of run "
        f"speed; go aggro, for good, when hurt, when the player is seen "
        f"({agro.vision_range_cm / 100:.0f} m, "
        f"{agro.vision_half_angle_deg:.0f} deg either side, line of sight), "
        f"touched ({agro.touch_range_cm:.0f} cm) or heard (the noise's own "
        f"reach x {agro.hearing_scale}). The tree tries the senses in that order.",
        agro_nodes)
    _log(f"steps authored; the senses, in priority order: {senses}")
    return senses
