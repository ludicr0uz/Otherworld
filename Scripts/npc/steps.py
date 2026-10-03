"""The controller's steps: one custom event per behaviour-tree step, BT_<Step>.

The tree (npc/tree.py) decides what runs and in which order; these events
are the work. The step task (npc/step_task.py) calls the event its node
names and finishes with StepResult, which every exit of every step writes:

    BT_Pulse   [possessed?] no: fail
                 yes -> corpse gate (Dead: corpse, StopLogic, fail)   corpse.py
                     -> stats and voice                               stats.py
                     -> patrol setup, once per life -> succeed        patrol.py
    every other step begins: [pawn gone, dead or at 0 HP?] fail      corpse.py
    BT_Ward    (a creature afraid of fire only) held off by the      ward.py
               player's fire: circle them, or run away -> succeed;
               no fire between them: fail, and the tree goes on to attack
    BT_Stalk   (a stalker only) roar, then tree to tree round the     stalk.py
               player -> succeed; close enough: fail, for good, and
               the tree goes on to Chase
    BT_Chase   between two swings: step back and round -> succeed    strafe.py
               else move order at the player -> run speed -> succeed  chase.py
    BT_Swing   in range and off cooldown? swing -> succeed            melee.py
    BT_PlayerPresent, BT_<Sense>...                                   agro.py
    BT_Drawn   (a creature a fire draws only) a campfire burns in     drawn.py
               reach: walk to it, slowly, or stand by it -> succeed;
               none: fail, and the tree goes on to the stroll
    BT_Stroll                                                         agro.py

Each event runs to its end in one call: no Delay and no latent node, so the
task reads StepResult straight after calling it.
"""

from forest_generator.npc_drawn import NPC_DRAWN_ARRIVE_CM, NPC_DRAWN_RANGE_CM
from forest_generator.npc_placement import NPC_VOICE_MAX_S, NPC_VOICE_MIN_S
from forest_generator.npc_stalk import (
    NPC_STALK_ARC_DEG, NPC_STALK_BEHIND_CM, NPC_STALK_CHARGE_CM,
    NPC_STALK_HIDE_MAX_S, NPC_STALK_HIDE_MIN_S, NPC_STALK_ROAR, NPC_STALK_ROAR_S,
    NPC_STALK_RUN_SCALE, NPC_STALK_TURN_MAX_S, NPC_STALK_TURN_MIN_S,
)
from forest_generator.npc_ward import (
    NPC_WARD_ARC_DEG, NPC_WARD_FLEE_S, NPC_WARD_HALF_ANGLE_DEG, NPC_WARD_HOLD_S,
    NPC_WARD_RANGE_CM, NPC_WARD_RING_CM, NPC_WARD_ROAR_AT_S, NPC_WARD_ROAR_VARY_S,
)
from forest_generator.npc_strafe import (
    NPC_STRAFE_ENGAGE_CM, NPC_STRAFE_MAX_ANGLE_DEG, NPC_STRAFE_MAX_DISTANCE_CM,
    NPC_STRAFE_MIN_ANGLE_DEG, NPC_STRAFE_MIN_DISTANCE_CM, NPC_STRAFE_SHARE,
    NPC_STRAFE_SPEED_SCALE,
)
from npc.agro import _author_agro_steps, _declare_agro_vars
from npc.chase import _author_chase
from npc.corpse import _author_alive_gate, _author_corpse_gate
from npc.drawn import _author_drawn, declare_drawn_vars, draws
from npc.graph import BEL, _connect, _log, _node, _pin, _set
from npc.melee import _author_melee
from npc.nodes import FN_GET_PAWN, FN_IS_VALID
from npc.monster_tuning import monster_specs, stock_run_speed
from npc.patrol import _author_patrol_setup, _author_walk_speed
from npc.paths import (
    STEP_CHASE, STEP_DRAWN, STEP_EVENT_PREFIX, STEP_PULSE, STEP_RESULT_VAR,
    STEP_STALK, STEP_SWING, STEP_WARD, WARD_SINCE_VAR,
)
from npc.roar import roar_object
from npc.stalk import _author_stalk, declare_stalk_vars
from npc.stats import _author_stats_and_voice
from npc.strafe import _author_strafe, declare_strafe_vars
from npc.tuned import declare_tuned_vars
from npc.ward import _author_ward, declare_ward_vars, wards
from survival.on_hit import melee_attack, on_hit_effects
from survival.on_hit_graph import declare_on_hit_vars


class _Steps:
    """Makes the step events and the StepResult writes they end on."""

    def __init__(self, ed):
        self.ed = ed

    def event(self, name, gated=True):
        """A new BT_<name> custom event; returns the exec output its work
        hangs off. That is behind the alive gate (corpse.py), drawn to the
        event's left, unless ``gated`` is False: Pulse, whose own corpse gate
        is what a dead pawn has to reach."""
        full = f"{STEP_EVENT_PREFIX}{name}"
        node = self.ed.add_custom_event_node(full)
        title = str(BEL.get_node_title(node)).replace(" ", "")
        # A name still held by the skeleton class comes back suffixed, and the
        # task's call by name would then miss it.
        if full.replace(" ", "") not in title or f"{full}_" in title:
            raise RuntimeError(f"custom event {full!r} came back as {title!r}")
        if not gated:
            return BEL.find_then_pin(node)
        return _author_alive_gate(self.ed, BEL.find_then_pin(node))

    def result_node(self, value):
        node = self.ed.add_set_member_variable_node(STEP_RESULT_VAR)
        _set(node, STEP_RESULT_VAR, "true" if value else "false")
        return node

    def result(self, value):
        """A StepResult write; returns its exec input."""
        return _pin(self.result_node(value), "execute")


def _author_pulse(ed, steps):
    """BT_Pulse: the part of every pass that runs before the tree chooses
    between hunting, noticing and patrolling. Returns the nodes by concern,
    for the comment boxes."""
    # The gate is not defensive padding: the tree starts at possession, but a
    # pawn can be gone (destroyed, unpossessed) while the controller lives.
    own_pawn = _node(ed, FN_GET_PAWN)
    possessed = _node(ed, FN_IS_VALID)
    _connect(_pin(own_pawn, "ReturnValue", is_input=False),
             _pin(possessed, "Object"))
    gate = ed.add_branch_node()
    _connect(_pin(possessed, "ReturnValue", is_input=False),
             _pin(gate, "Condition"))
    _connect(steps.event(STEP_PULSE, gated=False), _pin(gate, "execute"))
    _connect(BEL.find_else_pin(gate), steps.result(False))

    # First thing with a pawn: is it a corpse? A dead wanderer's tree stops
    # there, so nothing below -- stats, voice, patrol, chase, melee -- can run
    # for it. See npc/corpse.py.
    _, alive, ended = _author_corpse_gate(ed, BEL.find_then_pin(gate))
    _connect(ended, steps.result(False))
    # This creature's health, applied when it changes, and its voice on a timer. Both
    # need the pawn, which is why they sit after the gate.
    extras, after_extras = _author_stats_and_voice(ed, alive, NPC_VOICE_MIN_S, NPC_VOICE_MAX_S)
    setup, ready = _author_patrol_setup(ed, after_extras)
    _connect(ready, steps.result(True))
    return [own_pawn, possessed, gate], extras, setup


def _author_stalk_step(ed, steps, key):
    """BT_Stalk, for a creature of NPC_STALK_ROAR: the hunt before the chase."""
    declare_stalk_vars(ed)
    hunt, cover = _author_stalk(
        ed, steps.event(STEP_STALK), steps.result,
        roar_object(NPC_STALK_ROAR[key]), stock_run_speed(key))
    ed.add_comment_to_nodes(
        f"BT_Stalk, tried before BT_Chase. Hurt by the player it is Enraged, "
        f"for good: the step fails at once and BT_Chase charges. Otherwise: "
        f"on the first pass roar "
        f"({NPC_STALK_ROAR_S:g} s, standing, facing the player). Then a leg at "
        f"a time: run to the next tree at {NPC_STALK_RUN_SCALE:.0%} of its run "
        f"speed, wait behind it "
        f"{NPC_STALK_HIDE_MIN_S:g}-{NPC_STALK_HIDE_MAX_S:g} s watching the "
        f"player, pick the next. Within {NPC_STALK_CHARGE_CM:.0f} cm the step "
        f"fails for good and BT_Chase charges.", hunt)
    ed.add_comment_to_nodes(
        f"The next tree: a sphere swept at the player along a line "
        f"{' / '.join(f'{a:.0f}' for a in NPC_STALK_ARC_DEG)} deg round them "
        f"(the way of StalkSide, turned about every {NPC_STALK_TURN_MIN_S:g}-"
        f"{NPC_STALK_TURN_MAX_S:g} s), ignoring the ground and this pawn. The first "
        f"instanced mesh it strikes is a tree; the spot is "
        f"{NPC_STALK_BEHIND_CM:.0f} cm past its trunk, seen from the player, "
        f"snapped onto the navmesh. No tree on any line: on round, in the "
        f"open.", cover)


def _author_ward_step(ed, steps, key):
    """BT_Ward, for a creature of NPC_WARD_FEARS: held off by the player's
    fire. After the Stalk step's variables are declared: a flight resets them."""
    declare_ward_vars(ed)
    made = _author_ward(ed, steps.event(STEP_WARD), steps.result,
                        roar_object(NPC_STALK_ROAR.get(key)),
                        stock_run_speed(key), key in NPC_STALK_ROAR)
    ed.add_comment_to_nodes(
        f"BT_Ward, tried before the attack: while the player holds fire out "
        f"(FireWard), within {NPC_WARD_RANGE_CM:.0f} cm and "
        f"{NPC_WARD_HALF_ANGLE_DEG:.0f} deg of where they face, it does not "
        f"attack. It circles them {NPC_WARD_RING_CM:.0f} cm off, "
        f"{NPC_WARD_ARC_DEG:.0f} deg further round a pass, facing them; past "
        f"the fire the step fails and the attack runs. Held off "
        f"{NPC_WARD_HOLD_S:.0f} s, it roars and runs away for "
        f"{NPC_WARD_FLEE_S:.0f} s; it roars once before that too, "
        f"{NPC_WARD_ROAR_AT_S - NPC_WARD_ROAR_VARY_S:.0f}-"
        f"{NPC_WARD_ROAR_AT_S + NPC_WARD_ROAR_VARY_S:.0f} s in. A blow it "
        f"lands on the player (BT_Swing) starts the hold over.",
        made)


def _author_drawn_step(ed, steps, key):
    """BT_Drawn, for a creature of NPC_DRAWN_BY_FIRE: a fire draws it."""
    declare_drawn_vars(ed)
    made = _author_drawn(ed, steps.event(STEP_DRAWN), steps.result, stock_run_speed(key))
    ed.add_comment_to_nodes(
        f"BT_Drawn, tried after the senses and before BT_Stroll: with a "
        f"campfire burning within {NPC_DRAWN_RANGE_CM / 100:.0f} m (the "
        f"nearest, DrawnTo) it is Drawn: it walks to the fire at its patrol "
        f"walk and stands {NPC_DRAWN_ARRIVE_CM:.0f} cm off. With none the "
        f"step fails and it strolls.", made)


def _author_steps(ed, key, melee_anim):
    """Author every step event into creature ``key``'s controller graph.
    Its numbers are read off the Tune* variables (npc/tuned.py); ``spec``
    here only words the comments.

    Returns the sense step names authored, in priority order (sound is
    dropped when the GameMode has no noise record)."""
    ed.remove_member_variable(STEP_RESULT_VAR)
    if not ed.add_member_variable(STEP_RESULT_VAR, BEL.get_basic_type_by_name("bool")):
        raise RuntimeError(f"could not declare {STEP_RESULT_VAR}")
    _declare_agro_vars(ed)
    declare_tuned_vars(ed)
    declare_strafe_vars(ed)
    declare_on_hit_vars(ed)
    spec = monster_specs(key)
    steps = _Steps(ed)

    gate, extras, setup = _author_pulse(ed, steps)
    ed.add_comment_to_nodes(
        "BT_Pulse: the tree's first step on every pass. No pawn: fail. A "
        "corpse: stop the tree. Otherwise this creature's stats and voice, "
        "and the patrol set up once per life.", gate + setup)
    ed.add_comment_to_nodes(
        f"This creature's own health (TuneHealth, built {spec['health']:.0f}), "
        f"applied on the first pass after possession and whenever it is tuned, "
        f"and its voice every "
        f"{NPC_VOICE_MIN_S:.0f}-{NPC_VOICE_MAX_S:.0f} s. Health is set from "
        f"here rather than on the pawn because MaxHealth lives on an INHERITED "
        f"component, and Unreal keeps a child Blueprint's override of one in an "
        f"InheritableComponentHandler that Python cannot reach.",
        extras)

    if key in NPC_STALK_ROAR:
        _author_stalk_step(ed, steps, key)
    warded = wards(key)
    if warded:
        _author_ward_step(ed, steps, key)
    if draws(key):
        _author_drawn_step(ed, steps, key)

    stock = stock_run_speed(key)
    strafe, to_chase, strafed = _author_strafe(ed, steps.event(STEP_CHASE), stock)
    for tail in strafed:
        _connect(tail, steps.result(True))
    ed.add_comment_to_nodes(
        f"BT_Chase, between two swings: for the first {NPC_STRAFE_SHARE:.0%} of the "
        f"cooldown, with the player within {NPC_STRAFE_ENGAGE_CM:.0f} cm, step "
        f"{NPC_STRAFE_MIN_DISTANCE_CM:.0f}-{NPC_STRAFE_MAX_DISTANCE_CM:.0f} cm off "
        f"them and {NPC_STRAFE_MIN_ANGLE_DEG:.0f}-{NPC_STRAFE_MAX_ANGLE_DEG:.0f} deg "
        f"round, left or right (one pick per swing), facing them, at "
        f"{NPC_STRAFE_SPEED_SCALE:.0%} of the run. Otherwise face the way it "
        f"runs and chase.", strafe)
    chase, after_move = _author_chase(ed, to_chase)
    ran, ran_tails, _entry = _author_walk_speed(ed, after_move, False, stock)
    chase += ran
    for tail in ran_tails:
        _connect(tail, steps.result(True))
    ed.add_comment_to_nodes(
        "BT_Chase: a move order at the player, pathfinding when both ends are "
        "on the navmesh -- which is what runs the NPC around trees -- and a "
        "straight-line move order when either end is not. Then the run speed, "
        "from TuneRunSpeed, every pass.", chase)

    rest = steps.result_node(True)
    swing_in = steps.event(STEP_SWING)
    melee = _author_melee(ed, [swing_in], rest, melee_anim=melee_anim,
                          on_hit=on_hit_effects(melee_attack(key)),
                          # A blow that lands ends the hold the fire had it in.
                          clears=(WARD_SINCE_VAR,) if warded else ())
    if melee is None:
        _connect(swing_in, _pin(rest, "execute"))
    else:
        ed.add_comment_to_nodes(
            f"BT_Swing: within TuneMeleeRange ({spec['melee_range_cm']:.0f} cm) and "
            f"off cooldown, swing for TuneMeleeDamage ({spec['melee_damage']:.0f}), "
            f"then arm the next swing TuneMeleeInterval "
            f"({spec['melee_interval_s']:g} s) out. The cooldown is per controller, so "
            f"a pack does not hit in lockstep.", melee)

    agro_nodes, senses = _author_agro_steps(ed, steps.event, steps.result, stock_run_speed(key))
    ed.add_comment_to_nodes(
        f"Patrol until noticed: stroll a {spec['patrol_radius_cm'] / 100:.0f} m "
        f"circle about the spawn point at {spec['patrol_speed_scale']:.0%} of run "
        f"speed; go aggro, for good, when hurt, when the player is seen "
        f"({spec['vision_range_cm'] / 100:.0f} m, "
        f"{spec['vision_half_angle_deg']:.0f} deg either side, line of sight), "
        f"touched ({spec['touch_range_cm']:.0f} cm) or heard (the noise's own "
        f"reach x {spec['hearing_scale']:g}). The tree tries the senses in that "
        f"order. Every number is a Tune* variable, as built.",
        agro_nodes)
    _log(f"steps authored; the senses, in priority order: {senses}")
    return senses
