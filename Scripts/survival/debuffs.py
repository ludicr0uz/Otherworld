"""The debuff sync: one Tick fragment per row of survival.tuning.DEBUFFS that
applies the row's GameplayEffect when its bar reaches zero and removes it when
the bar comes back up.

Edge-triggered on the ability system's own answer, not on a bool of ours:

    want = Stat <= 0
    have = AbilitySystem.GetGameplayEffectCount(Effect) > 0
    if want != have:
        want -> MakeOutgoingSpec -> AddGrantedTag x N -> ApplySpecToSelf
        else -> RemoveActiveGameplayEffectBySourceEffect

Asking the ASC "is it on?" rather than keeping a flag means there is exactly
one record of whether the player is starving, and it is the one the rest of
the engine reads. A flag could disagree with it -- for instance after something
else removed the effect -- and would then never re-apply it.

The spec is made by a PURE node (MakeOutgoingSpec is a const
BlueprintCallable, promoted by UHT), so it is only evaluated once, where the
first AddGrantedTag executes; every later node reads the previous node's
returned handle, which points at the same spec. Wiring two AddGrantedTags to
the spec node directly would build two specs and apply the one with one tag.
"""

from uebp.graph import _connect, _node, _pin, _set, else_, out, then
from combat.nodes import (
    FN_ADD_GRANTED_TAG, FN_APPLY_SPEC_TO_SELF, FN_EFFECT_COUNT, FN_GREATER_II,
    FN_LE_FF, FN_MAKE_CONTEXT, FN_MAKE_SPEC, FN_NEQ_BB, FN_REMOVE_EFFECT,
)


def _author_debuff_sync(ed, asc, stat, effect_var, tags, exec_in):
    """One debuff. ``asc`` is the AbilitySystem getter's output pin, already
    known valid; returns the three exec pins every path ends on."""
    made = []

    def keep(n):
        made.append(n)
        return n

    value = keep(ed.add_get_member_variable_node(stat))
    empty = keep(_node(ed, FN_LE_FF))
    _connect(out(value, stat), _pin(empty, "A"))
    _set(empty, "B", 0.0)
    want = out(empty)

    effect = keep(ed.add_get_member_variable_node(effect_var))
    effect_out = out(effect, effect_var)
    count = keep(_node(ed, FN_EFFECT_COUNT))
    _connect(asc, _pin(count, "self"))
    _connect(effect_out, _pin(count, "SourceGameplayEffect"))
    _set(count, "bEnforceOnGoingCheck", "true")
    active = keep(_node(ed, FN_GREATER_II))
    _connect(out(count), _pin(active, "A"))
    _set(active, "B", 0)

    differ = keep(_node(ed, FN_NEQ_BB))
    _connect(want, _pin(differ, "A"))
    _connect(out(active), _pin(differ, "B"))
    changed = keep(ed.add_branch_node())
    _connect(out(differ), _pin(changed, "Condition"))
    for e in exec_in:
        _connect(e, _pin(changed, "execute"))

    which = keep(ed.add_branch_node())
    _connect(want, _pin(which, "Condition"))
    _connect(then(changed), _pin(which, "execute"))

    # --- apply: a spec, its tags, then onto the owner ------------------------
    context = keep(_node(ed, FN_MAKE_CONTEXT))
    _connect(asc, _pin(context, "self"))
    spec = keep(_node(ed, FN_MAKE_SPEC))
    _connect(asc, _pin(spec, "self"))
    _connect(effect_out, _pin(spec, "GameplayEffectClass"))
    _set(spec, "Level", 1.0)
    _connect(out(context), _pin(spec, "Context"))
    handle = out(spec)
    flow = then(which)
    for tag in tags:
        grant = keep(_node(ed, FN_ADD_GRANTED_TAG))
        _connect(handle, _pin(grant, "SpecHandle"))
        _set(grant, "NewGameplayTag", f'(TagName="{tag}")')
        _connect(flow, _pin(grant, "execute"))
        handle = out(grant)
        flow = then(grant)
    apply = keep(_node(ed, FN_APPLY_SPEC_TO_SELF))
    _connect(asc, _pin(apply, "self"))
    _connect(handle, _pin(apply, "SpecHandle"))
    _connect(flow, _pin(apply, "execute"))

    # --- remove: every stack of it, from any instigator ----------------------
    remove = keep(_node(ed, FN_REMOVE_EFFECT))
    _connect(asc, _pin(remove, "self"))
    _connect(effect_out, _pin(remove, "GameplayEffect"))
    _set(remove, "StacksToRemove", -1)
    _connect(else_(which), _pin(remove, "execute"))

    ed.add_comment_to_nodes(
        f"{stat} at zero <-> {effect_var} active. Only the frames where the two "
        f"disagree do anything: apply it with {', '.join(tags)} granted on the "
        "spec, or remove it.",
        made)
    return (then(apply), then(remove), else_(changed))
