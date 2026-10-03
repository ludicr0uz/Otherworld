"""BP_HealthComponent's debuff drain: while the owner's AbilitySystemComponent
carries a tag of combat.tuning.HEALTH_DRAINS, health runs down.

    rate   = sum over (tag, hp_per_s) of
             AbilitySystem.GetGameplayTagCount(tag) * hp_per_s
    loss   = rate * DeltaSeconds
    Health     -= loss
    PrevHealth -= loss        <- not a hit

The component counts TAGS rather than naming any debuff, so it knows nothing
about hunger: GE_Starving and GE_Dehydrated (Scripts/survival) each grant
Debuff.HealthDrain once, which is what makes both together drain twice as
fast. A debuff with a rate of its own has a row of its own: GE_Bleeding grants
Debuff.Bleeding. Any actor with a health component and an ability system --
the wanderers included -- is drained the same way.

PrevHealth is lowered by the same amount because the hit-reaction block reads
"Health < PrevHealth" as "something hurt us this frame" and flinches. Without
the second write a starving player would flinch every time the reaction's
cooldown lapsed, for as long as they starved. A real hit taken on a draining
frame still shows, because it lowers Health alone.

Runs before the death check in the same Tick, so a drain that crosses zero
kills on the frame it happens, through the ordinary death path.
"""

from uebp.graph import _connect, _node, _pin, _set, else_, out, then
from combat.hit_reaction import PREV_HEALTH_VAR
from combat.nodes import (
    FN_ADD_FF, FN_ADD_II, FN_AND, FN_GET_ASC, FN_GET_OWNER, FN_GREATER_II,
    FN_IS_VALID, FN_MUL_FF, FN_NOT, FN_SUB_FF, FN_TAG_COUNT,
)
from combat.tuning import HEALTH_DRAINS

FN_INT_TO_FLOAT = "/Script/Engine.KismetMathLibrary.Conv_IntToDouble"


def _author_debuff_drain(ed, tick, exec_ins):
    """Returns the exec pins every path through the drain ends on."""
    made = []

    def keep(n):
        made.append(n)
        return n

    owner = keep(_node(ed, FN_GET_OWNER))
    lookup = keep(_node(ed, FN_GET_ASC))
    _connect(out(owner), _pin(lookup, "Actor"))
    asc = out(lookup)

    # Two safe reads folded together: IsValid takes null as an answer, and Dead
    # is this component's own bool. The tag count is NOT folded in -- it reads
    # off the ability system, so it waits behind this gate.
    has = keep(_node(ed, FN_IS_VALID))
    _connect(asc, _pin(has, "Object"))
    dead = keep(ed.add_get_member_variable_node("Dead"))
    alive = keep(_node(ed, FN_NOT))
    _connect(out(dead, "Dead"), _pin(alive, "A"))
    both = keep(_node(ed, FN_AND))
    _connect(out(has), _pin(both, "A"))
    _connect(out(alive), _pin(both, "B"))
    gate = keep(ed.add_branch_node())
    _connect(out(both), _pin(gate, "Condition"))
    for e in exec_ins:
        _connect(e, _pin(gate, "execute"))

    # One row per drained tag: its stack count, and that count times its rate.
    # The counts add up to "is anything draining?", the products to the rate.
    stacks_out = rate_out = None
    for tag, hp_per_s in HEALTH_DRAINS:
        stacks = keep(_node(ed, FN_TAG_COUNT))
        _connect(asc, _pin(stacks, "self"))
        _set(stacks, "GameplayTag", f'(TagName="{tag}")')
        count_out = out(stacks)
        as_float = keep(_node(ed, FN_INT_TO_FLOAT))
        _connect(count_out, _pin(as_float, "InInt"))
        per_s = keep(_node(ed, FN_MUL_FF))
        _connect(out(as_float), _pin(per_s, "A"))
        _set(per_s, "B", hp_per_s)
        per_s_out = out(per_s)
        if stacks_out is None:
            stacks_out, rate_out = count_out, per_s_out
            continue
        more = keep(_node(ed, FN_ADD_II))
        _connect(stacks_out, _pin(more, "A"))
        _connect(count_out, _pin(more, "B"))
        stacks_out = out(more)
        faster = keep(_node(ed, FN_ADD_FF))
        _connect(rate_out, _pin(faster, "A"))
        _connect(per_s_out, _pin(faster, "B"))
        rate_out = out(faster)

    any_ = keep(_node(ed, FN_GREATER_II))
    _connect(stacks_out, _pin(any_, "A"))
    _set(any_, "B", 0)
    draining = keep(ed.add_branch_node())
    _connect(out(any_), _pin(draining, "Condition"))
    _connect(then(gate), _pin(draining, "execute"))

    loss = keep(_node(ed, FN_MUL_FF))
    _connect(rate_out, _pin(loss, "A"))
    _connect(out(tick, "DeltaSeconds"), _pin(loss, "B"))
    loss_out = out(loss)

    prev = then(draining)
    for var in ("Health", PREV_HEALTH_VAR):
        now = keep(ed.add_get_member_variable_node(var))
        less = keep(_node(ed, FN_SUB_FF))
        _connect(out(now, var), _pin(less, "A"))
        _connect(loss_out, _pin(less, "B"))
        write = keep(ed.add_set_member_variable_node(var))
        _connect(out(less), _pin(write, var))
        _connect(prev, _pin(write, "execute"))
        prev = then(write)

    ed.add_comment_to_nodes(
        "Debuffs: "
        + ", ".join(f"{rate:g} HP/s for every stack of {tag}"
                    for tag, rate in HEALTH_DRAINS)
        + " on the owner's AbilitySystemComponent. PrevHealth falls with "
        "Health so the hit reaction does not read the drain as a hit.",
        made)
    return (prev, else_(draining), else_(gate))
