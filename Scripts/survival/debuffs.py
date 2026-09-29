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

from combat.graph import BEL, _at, _connect, _node, _pin, _set
from combat.nodes import (
    FN_ADD_GRANTED_TAG, FN_APPLY_SPEC_TO_SELF, FN_EFFECT_COUNT, FN_GREATER_II,
    FN_LE_FF, FN_MAKE_CONTEXT, FN_MAKE_SPEC, FN_NEQ_BB, FN_REMOVE_EFFECT,
)


def _author_debuff_sync(ed, asc, stat, effect_var, tags, exec_in, x0, y0):
    """One debuff. ``asc`` is the AbilitySystem getter's output pin, already
    known valid; returns the three exec pins every path ends on."""
    made = []

    def keep(n):
        made.append(n)
        return n

    value = keep(_at(ed.add_get_member_variable_node(stat), x0, y0 + 300))
    empty = keep(_at(_node(ed, FN_LE_FF), x0 + 240, y0 + 300))
    _connect(_pin(value, stat, is_input=False), _pin(empty, "A"))
    _set(empty, "B", 0.0)
    want = _pin(empty, "ReturnValue", is_input=False)

    effect = keep(_at(ed.add_get_member_variable_node(effect_var), x0, y0 + 440))
    effect_out = _pin(effect, effect_var, is_input=False)
    count = keep(_at(_node(ed, FN_EFFECT_COUNT), x0 + 240, y0 + 440))
    _connect(asc, _pin(count, "self"))
    _connect(effect_out, _pin(count, "SourceGameplayEffect"))
    _set(count, "bEnforceOnGoingCheck", "true")
    active = keep(_at(_node(ed, FN_GREATER_II), x0 + 480, y0 + 440))
    _connect(_pin(count, "ReturnValue", is_input=False), _pin(active, "A"))
    _set(active, "B", 0)

    differ = keep(_at(_node(ed, FN_NEQ_BB), x0 + 720, y0 + 360))
    _connect(want, _pin(differ, "A"))
    _connect(_pin(active, "ReturnValue", is_input=False), _pin(differ, "B"))
    changed = keep(_at(ed.add_branch_node(), x0 + 960, y0))
    _connect(_pin(differ, "ReturnValue", is_input=False), _pin(changed, "Condition"))
    for e in exec_in:
        _connect(e, _pin(changed, "execute"))

    which = keep(_at(ed.add_branch_node(), x0 + 1200, y0))
    _connect(want, _pin(which, "Condition"))
    _connect(BEL.find_then_pin(changed), _pin(which, "execute"))

    # --- apply: a spec, its tags, then onto the owner ------------------------
    context = keep(_at(_node(ed, FN_MAKE_CONTEXT), x0 + 1200, y0 + 300))
    _connect(asc, _pin(context, "self"))
    spec = keep(_at(_node(ed, FN_MAKE_SPEC), x0 + 1440, y0 + 300))
    _connect(asc, _pin(spec, "self"))
    _connect(effect_out, _pin(spec, "GameplayEffectClass"))
    _set(spec, "Level", 1.0)
    _connect(_pin(context, "ReturnValue", is_input=False), _pin(spec, "Context"))
    handle = _pin(spec, "ReturnValue", is_input=False)
    flow = BEL.find_then_pin(which)
    for i, tag in enumerate(tags):
        grant = keep(_at(_node(ed, FN_ADD_GRANTED_TAG), x0 + 1700 + i * 280, y0))
        _connect(handle, _pin(grant, "SpecHandle"))
        _set(grant, "NewGameplayTag", f'(TagName="{tag}")')
        _connect(flow, _pin(grant, "execute"))
        handle = _pin(grant, "ReturnValue", is_input=False)
        flow = BEL.find_then_pin(grant)
    apply = keep(_at(_node(ed, FN_APPLY_SPEC_TO_SELF),
                     x0 + 1700 + len(tags) * 280, y0))
    _connect(asc, _pin(apply, "self"))
    _connect(handle, _pin(apply, "SpecHandle"))
    _connect(flow, _pin(apply, "execute"))

    # --- remove: every stack of it, from any instigator ----------------------
    remove = keep(_at(_node(ed, FN_REMOVE_EFFECT), x0 + 1440, y0 + 600))
    _connect(asc, _pin(remove, "self"))
    _connect(effect_out, _pin(remove, "GameplayEffect"))
    _set(remove, "StacksToRemove", -1)
    _connect(BEL.find_else_pin(which), _pin(remove, "execute"))

    ed.add_comment_to_nodes(
        f"{stat} at zero <-> {effect_var} active. Only the frames where the two "
        f"disagree do anything: apply it with {', '.join(tags)} granted on the "
        "spec, or remove it.",
        made)
    return (BEL.find_then_pin(apply), BEL.find_then_pin(remove),
            BEL.find_else_pin(changed))
