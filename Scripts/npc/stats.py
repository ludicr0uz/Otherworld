"""The health and hit-reaction copy (on possession, and again when the tuned
health changes), and the voice on a timer -- both hung off the controller's heartbeat.
"""

import unreal

from npc.paths import (
    APPLIED_HEALTH_VAR, HEALTH_CLASS_PATH, HIT_SOUNDS_VAR, NEXT_VOICE_VAR,
    REACTIONS_VAR, STATS_APPLIED_VAR, VOICES_VAR,
)
from npc.nodes import (
    FN_ACTOR_LOC, FN_ADD_FF, FN_GET_COMP, FN_GET_PAWN, FN_GE_FF, FN_NE_FF,
    FN_RANDOM_FLOAT, FN_TIME_SECONDS, NODE_CAST_HEALTH,
)
from npc.graph import (
    _at, BEL, _connect, _loose_pin, _node, _palette, _pin, _set,
)
from npc.sound import _author_random_sound
from npc.tuned import tuned


def _author_stats_and_voice(ed, exec_ins, x0, y0, voice_min, voice_max):
    """Apply this creature's health when it changes, then growl on a timer.

    Both hang off the chase loop's existing heartbeat rather than getting a
    Tick of their own, for the reason _author_melee gives: the loop is already
    the NPC's clock and a second one is only a way for the two to disagree.

        gate(possessed, alive) --> [TuneHealth != AppliedHealth?]
                              yes --> MaxHealth = Health = TuneHealth
                                  --> reactions, StatsApplied, AppliedHealth
                              no  ----------------------------.
                                                              v
                                            [time to make a noise?]
                                              yes --> play one of Voices
                                              no  ----------------------> on

    AppliedHealth starts at 0, so the first pass after possession applies it;
    after that only the MONSTER SETTINGS tab changing TuneHealth does, and a
    live wanderer then stands at its new maximum, full.

    Health is applied HERE, from this controller's TuneHealth, rather
    than set on the pawn Blueprint. It has to be: MaxHealth lives on an
    inherited BP_HealthComponent, and Unreal stores a child Blueprint's
    override of an inherited component's defaults in an InheritableComponentHandler
    that the Python API does not expose -- ``get_component_by_class`` on a CDO
    returns None (measured). The controller is already per creature for the
    attack clip, so it is the one place that both knows which creature this is
    and can reach the component at runtime.

    Applying it on the first heartbeat AFTER possession, rather than at
    BeginPlay, is what makes it reliable: a controller's BeginPlay runs before
    it possesses anything, so there is no pawn to find the component on.

    Returns the nodes it made and the exec to carry on with.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    for name, kind in ((STATS_APPLIED_VAR, "bool"), (NEXT_VOICE_VAR, "real"),
                       (APPLIED_HEALTH_VAR, "real")):
        ed.remove_member_variable(name)
        if not ed.add_member_variable(name, BEL.get_basic_type_by_name(kind)):
            raise RuntimeError(f"could not declare {name}")
    sound_array = BEL.get_array_type(
        BEL.get_object_reference_type(unreal.SoundBase.static_class()))
    for name in (VOICES_VAR, HIT_SOUNDS_VAR):
        ed.remove_member_variable(name)
        if not ed.add_member_variable(name, sound_array):
            raise RuntimeError(f"could not declare {name}")
    ed.remove_member_variable(REACTIONS_VAR)
    if not ed.add_member_variable(REACTIONS_VAR, BEL.get_array_type(
            BEL.get_object_reference_type(unreal.AnimSequenceBase.static_class()))):
        raise RuntimeError(f"could not declare {REACTIONS_VAR}")

    pawn = keep(_at(_node(ed, FN_GET_PAWN), x0, y0 + 620))
    pawn_out = _pin(pawn, "ReturnValue", is_input=False)
    where = keep(_at(_node(ed, FN_ACTOR_LOC), x0 + 240, y0 + 620))
    _connect(pawn_out, _pin(where, "self"))
    where_out = _pin(where, "ReturnValue", is_input=False)

    # --- when it changes: this creature's health ----------------------------
    want, want_out = tuned(ed, "health", x0, y0 + 160)
    keep(want)
    done = keep(_at(ed.add_get_member_variable_node(APPLIED_HEALTH_VAR), x0, y0 + 240))
    fresh = keep(_at(_node(ed, FN_NE_FF), x0 + 240, y0 + 240))
    _connect(want_out, _pin(fresh, "A"))
    _connect(_pin(done, APPLIED_HEALTH_VAR, is_input=False), _pin(fresh, "B"))
    first = keep(_at(ed.add_branch_node(), x0 + 480, y0))
    _connect(_pin(fresh, "ReturnValue", is_input=False), _pin(first, "Condition"))
    for pin in exec_ins:
        _connect(pin, _pin(first, "execute"))

    comp = keep(_at(_node(ed, FN_GET_COMP), x0 + 480, y0 + 380))
    _connect(pawn_out, _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)
    as_health = keep(_at(_palette(ed, NODE_CAST_HEALTH), x0 + 720, y0))
    _connect(_pin(comp, "ReturnValue", is_input=False), _pin(as_health, "Object"))
    _connect(BEL.find_then_pin(first), _pin(as_health, "execute"))
    health_out = _loose_pin(as_health, "AsBPHealthComponent", is_input=False)

    set_max = keep(_at(ed.add_set_member_variable_node("MaxHealth", HEALTH_CLASS_PATH),
                       x0 + 980, y0))
    _connect(health_out, _pin(set_max, "self"))
    _connect(want_out, _pin(set_max, "MaxHealth"))
    _connect(BEL.find_then_pin(as_health), _pin(set_max, "execute"))

    set_now = keep(_at(ed.add_set_member_variable_node("Health", HEALTH_CLASS_PATH),
                       x0 + 1240, y0))
    _connect(health_out, _pin(set_now, "self"))
    _connect(want_out, _pin(set_now, "Health"))
    _connect(BEL.find_then_pin(set_max), _pin(set_now, "execute"))

    # ...and this creature's own hit reactions, onto the same component, in the
    # same breath and for the same reason.  A plain array-to-array copy: the
    # health component's graph does the picking, all this has to do is put the
    # right skeleton's clips where it can see them.
    set_reacts = keep(_at(ed.add_set_member_variable_node(REACTIONS_VAR,
                                                          HEALTH_CLASS_PATH),
                          x0 + 1500, y0))
    _connect(health_out, _pin(set_reacts, "self"))
    mine = keep(_at(ed.add_get_member_variable_node(REACTIONS_VAR),
                    x0 + 1500, y0 + 380))
    _connect(_pin(mine, REACTIONS_VAR, is_input=False),
             _pin(set_reacts, REACTIONS_VAR))
    _connect(BEL.find_then_pin(set_now), _pin(set_reacts, "execute"))

    mark = keep(_at(ed.add_set_member_variable_node(STATS_APPLIED_VAR), x0 + 1760, y0))
    _set(mark, STATS_APPLIED_VAR, "true")
    _connect(BEL.find_then_pin(set_reacts), _pin(mark, "execute"))
    took = keep(_at(ed.add_set_member_variable_node(APPLIED_HEALTH_VAR), x0 + 1760, y0 - 200))
    _connect(want_out, _pin(took, APPLIED_HEALTH_VAR))
    _connect(BEL.find_then_pin(mark), _pin(took, "execute"))

    # --- every few seconds: a noise -----------------------------------------
    now = keep(_at(_node(ed, FN_TIME_SECONDS), x0 + 1760, y0 + 380))
    now_out = _pin(now, "ReturnValue", is_input=False)
    due_at = keep(_at(ed.add_get_member_variable_node(NEXT_VOICE_VAR), x0 + 1760, y0 + 500))
    due = keep(_at(_node(ed, FN_GE_FF), x0 + 2000, y0 + 380))
    _connect(now_out, _pin(due, "A"))
    _connect(_pin(due_at, NEXT_VOICE_VAR, is_input=False), _pin(due, "B"))
    speak = keep(_at(ed.add_branch_node(), x0 + 2240, y0))
    _connect(_pin(due, "ReturnValue", is_input=False), _pin(speak, "Condition"))
    # Every way into the voice check: stats just applied, stats already
    # current, or the component was not there to apply them to.
    for tail in (BEL.find_then_pin(took),
                 BEL.find_else_pin(first),
                 _pin(as_health, "CastFailed", is_input=False)):
        _connect(tail, _pin(speak, "execute"))

    voiced, after_voice = _author_random_sound(
        ed, VOICES_VAR, where_out, BEL.find_then_pin(speak), x0 + 2500, y0)
    made.extend(voiced)

    gap = keep(_at(_node(ed, FN_RANDOM_FLOAT), x0 + 4300, y0 + 380))
    _set(gap, "Min", voice_min)
    _set(gap, "Max", voice_max)
    again = keep(_at(_node(ed, FN_ADD_FF), x0 + 4540, y0 + 380))
    _connect(now_out, _pin(again, "A"))
    _connect(_pin(gap, "ReturnValue", is_input=False), _pin(again, "B"))
    rearm = keep(_at(ed.add_set_member_variable_node(NEXT_VOICE_VAR), x0 + 4800, y0))
    _connect(_pin(again, "ReturnValue", is_input=False), _pin(rearm, NEXT_VOICE_VAR))
    _connect(after_voice, _pin(rearm, "execute"))

    # One exec out, whether or not it spoke this pass.
    out = keep(_at(ed.add_branch_node(), x0 + 5060, y0))
    _set(out, "Condition", "true")
    _connect(BEL.find_then_pin(rearm), _pin(out, "execute"))
    _connect(BEL.find_else_pin(speak), _pin(out, "execute"))
    return made, BEL.find_then_pin(out)
