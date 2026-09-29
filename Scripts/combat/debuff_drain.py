"""BP_HealthComponent's debuff drain: while the owner's AbilitySystemComponent
carries HEALTH_DRAIN_TAG, health runs down.

    stacks = AbilitySystem.GetGameplayTagCount(Debuff.HealthDrain)
    loss   = stacks * DEBUFF_DRAIN_HP_PER_S * DeltaSeconds
    Health     -= loss
    PrevHealth -= loss        <- not a hit

The component counts a TAG rather than naming any debuff, so it knows nothing
about hunger: GE_Starving and GE_Dehydrated (Scripts/survival) each grant the
tag once, which is what makes both together drain twice as fast, and a future
poison or bleed only has to grant it too. Any actor with a health component and
an ability system -- the wanderers included -- is drained the same way.

PrevHealth is lowered by the same amount because the hit-reaction block reads
"Health < PrevHealth" as "something hurt us this frame" and flinches. Without
the second write a starving player would flinch every time the reaction's
cooldown lapsed, for as long as they starved. A real hit taken on a draining
frame still shows, because it lowers Health alone.

Runs before the death check in the same Tick, so a drain that crosses zero
kills on the frame it happens, through the ordinary death path.
"""

from combat.graph import BEL, _at, _connect, _node, _pin, _set
from combat.hit_reaction import PREV_HEALTH_VAR
from combat.nodes import (
    FN_AND, FN_GET_ASC, FN_GET_OWNER, FN_GREATER_II, FN_IS_VALID, FN_MUL_FF,
    FN_NOT, FN_SUB_FF, FN_TAG_COUNT,
)
from combat.tuning import DEBUFF_DRAIN_HP_PER_S, HEALTH_DRAIN_TAG

FN_INT_TO_FLOAT = "/Script/Engine.KismetMathLibrary.Conv_IntToDouble"


def _author_debuff_drain(ed, tick, exec_ins, x0, y0):
    """Returns the exec pins every path through the drain ends on."""
    made = []

    def keep(n):
        made.append(n)
        return n

    owner = keep(_at(_node(ed, FN_GET_OWNER), x0, y0 + 300))
    lookup = keep(_at(_node(ed, FN_GET_ASC), x0 + 240, y0 + 300))
    _connect(_pin(owner, "ReturnValue", is_input=False), _pin(lookup, "Actor"))
    asc = _pin(lookup, "ReturnValue", is_input=False)

    # Two safe reads folded together: IsValid takes null as an answer, and Dead
    # is this component's own bool. The tag count is NOT folded in -- it reads
    # off the ability system, so it waits behind this gate.
    has = keep(_at(_node(ed, FN_IS_VALID), x0 + 480, y0 + 300))
    _connect(asc, _pin(has, "Object"))
    dead = keep(_at(ed.add_get_member_variable_node("Dead"), x0 + 480, y0 + 420))
    alive = keep(_at(_node(ed, FN_NOT), x0 + 720, y0 + 420))
    _connect(_pin(dead, "Dead", is_input=False), _pin(alive, "A"))
    both = keep(_at(_node(ed, FN_AND), x0 + 960, y0 + 360))
    _connect(_pin(has, "ReturnValue", is_input=False), _pin(both, "A"))
    _connect(_pin(alive, "ReturnValue", is_input=False), _pin(both, "B"))
    gate = keep(_at(ed.add_branch_node(), x0 + 1200, y0))
    _connect(_pin(both, "ReturnValue", is_input=False), _pin(gate, "Condition"))
    for e in exec_ins:
        _connect(e, _pin(gate, "execute"))

    stacks = keep(_at(_node(ed, FN_TAG_COUNT), x0 + 1200, y0 + 300))
    _connect(asc, _pin(stacks, "self"))
    _set(stacks, "GameplayTag", f'(TagName="{HEALTH_DRAIN_TAG}")')
    stacks_out = _pin(stacks, "ReturnValue", is_input=False)
    any_ = keep(_at(_node(ed, FN_GREATER_II), x0 + 1440, y0 + 300))
    _connect(stacks_out, _pin(any_, "A"))
    _set(any_, "B", 0)
    draining = keep(_at(ed.add_branch_node(), x0 + 1680, y0))
    _connect(_pin(any_, "ReturnValue", is_input=False), _pin(draining, "Condition"))
    _connect(BEL.find_then_pin(gate), _pin(draining, "execute"))

    as_float = keep(_at(_node(ed, FN_INT_TO_FLOAT), x0 + 1440, y0 + 440))
    _connect(stacks_out, _pin(as_float, "InInt"))
    per_s = keep(_at(_node(ed, FN_MUL_FF), x0 + 1680, y0 + 440))
    _connect(_pin(as_float, "ReturnValue", is_input=False), _pin(per_s, "A"))
    _set(per_s, "B", DEBUFF_DRAIN_HP_PER_S)
    loss = keep(_at(_node(ed, FN_MUL_FF), x0 + 1920, y0 + 440))
    _connect(_pin(per_s, "ReturnValue", is_input=False), _pin(loss, "A"))
    _connect(_pin(tick, "DeltaSeconds", is_input=False), _pin(loss, "B"))
    loss_out = _pin(loss, "ReturnValue", is_input=False)

    prev = BEL.find_then_pin(draining)
    for i, var in enumerate(("Health", PREV_HEALTH_VAR)):
        now = keep(_at(ed.add_get_member_variable_node(var), x0 + 1920, y0 + 600 + i * 120))
        less = keep(_at(_node(ed, FN_SUB_FF), x0 + 2160, y0 + 600 + i * 120))
        _connect(_pin(now, var, is_input=False), _pin(less, "A"))
        _connect(loss_out, _pin(less, "B"))
        write = keep(_at(ed.add_set_member_variable_node(var), x0 + 2160 + i * 260, y0))
        _connect(_pin(less, "ReturnValue", is_input=False), _pin(write, var))
        _connect(prev, _pin(write, "execute"))
        prev = BEL.find_then_pin(write)

    ed.add_comment_to_nodes(
        f"Debuffs: {DEBUFF_DRAIN_HP_PER_S} HP/s for every stack of "
        f"{HEALTH_DRAIN_TAG} on the owner's AbilitySystemComponent. PrevHealth "
        "falls with Health so the hit reaction does not read the drain as a hit.",
        made)
    return (prev, BEL.find_else_pin(draining), BEL.find_else_pin(gate))
