"""The on-hit roll: a fragment any graph that lands a hit can run, which gives
the target each of the attack's effects (survival/on_hit.py) with its chance.

    exec_in --> [target has an ability system?]
                  no  -----------------------------------------------> out
                  yes --> per effect, each on its own roll:
                          [RandomFloat(0, 1) < chance + OnHitChanceBonus?]
                            no  --> the next effect
                            yes --> remove every stack of it
                                --> MakeOutgoingSpec -> AddGrantedTag x N
                                --> ApplyGameplayEffectSpecToSelf --> next

The target is an actor pin: the effect goes onto ITS AbilitySystemComponent,
so the fragment does not care who swung or what was hit, and a target without
one (nothing can carry a debuff there) is simply passed over.

Removed before it is applied, so a second wound restarts the effect's time
rather than stacking a second copy: the health component drains per stack of
the tag, and two copies would bleed twice as fast.

The roll is a pure node read once, by its Branch. The spec is pure too: each
AddGrantedTag reads the previous one's returned handle (survival/debuffs.py).
"""

from combat.graph import BEL, _assets, _connect, _float_type, _log, _node, _pin, _set
from combat.nodes import (
    FN_ADD_FF, FN_ADD_GRANTED_TAG, FN_APPLY_SPEC_TO_SELF, FN_GET_ASC, FN_IS_VALID,
    FN_LESS_FF, FN_MAKE_CONTEXT, FN_MAKE_SPEC, FN_RANDOM_FLOAT, FN_REMOVE_EFFECT,
)
from survival.on_hit import ON_HIT_BONUS_VAR


def declare_on_hit_vars(ed):
    """Once per graph, before its first _author_on_hit."""
    ed.remove_member_variable(ON_HIT_BONUS_VAR)
    if not ed.add_member_variable(ON_HIT_BONUS_VAR, _float_type()):
        raise RuntimeError(f"could not declare {ON_HIT_BONUS_VAR}")


def _author_on_hit(ed, exec_in, target, effects):
    """Roll ``effects`` onto the actor at pin ``target`` once ``exec_in`` runs.

    Returns ``(nodes, tails)``: every exec pin the fragment ends on. An effect
    whose GameplayEffect has not been built is left out, with a note; with
    none left the fragment is nothing and ``tails`` is ``[exec_in]``.
    """
    eas = _assets()
    ready = []
    for effect in effects:
        if eas.does_asset_exist(effect.effect_path) and eas.load_asset(effect.effect_path):
            ready.append(effect)
        else:
            _log(f"note: {effect.effect_path} not found — a hit cannot cause "
                 f"{effect.name} (run build_survival.py first)")
    if not ready:
        return [], [exec_in]

    made = []

    def keep(n):
        made.append(n)
        return n

    lookup = keep(_node(ed, FN_GET_ASC))
    _connect(target, _pin(lookup, "Actor"))
    asc = _pin(lookup, "ReturnValue", is_input=False)
    valid = keep(_node(ed, FN_IS_VALID))
    _connect(asc, _pin(valid, "Object"))
    gate = keep(ed.add_branch_node())
    _connect(_pin(valid, "ReturnValue", is_input=False), _pin(gate, "Condition"))
    _connect(exec_in, _pin(gate, "execute"))

    flows = [BEL.find_then_pin(gate)]
    for effect in ready:
        roll = keep(_node(ed, FN_RANDOM_FLOAT))
        _set(roll, "Min", 0.0)
        _set(roll, "Max", 1.0)
        bonus = keep(ed.add_get_member_variable_node(ON_HIT_BONUS_VAR))
        odds = keep(_node(ed, FN_ADD_FF))
        _connect(_pin(bonus, ON_HIT_BONUS_VAR, is_input=False), _pin(odds, "A"))
        _set(odds, "B", effect.chance)
        under = keep(_node(ed, FN_LESS_FF))
        _connect(_pin(roll, "ReturnValue", is_input=False), _pin(under, "A"))
        _connect(_pin(odds, "ReturnValue", is_input=False), _pin(under, "B"))
        lands = keep(ed.add_branch_node())
        _connect(_pin(under, "ReturnValue", is_input=False), _pin(lands, "Condition"))
        for flow in flows:
            _connect(flow, _pin(lands, "execute"))

        remove = keep(_node(ed, FN_REMOVE_EFFECT))
        _connect(asc, _pin(remove, "self"))
        _set(remove, "GameplayEffect", effect.effect_class)
        _set(remove, "StacksToRemove", -1)
        _connect(BEL.find_then_pin(lands), _pin(remove, "execute"))

        context = keep(_node(ed, FN_MAKE_CONTEXT))
        _connect(asc, _pin(context, "self"))
        spec = keep(_node(ed, FN_MAKE_SPEC))
        _connect(asc, _pin(spec, "self"))
        _set(spec, "GameplayEffectClass", effect.effect_class)
        _set(spec, "Level", 1.0)
        _connect(_pin(context, "ReturnValue", is_input=False), _pin(spec, "Context"))
        handle = _pin(spec, "ReturnValue", is_input=False)
        flow = BEL.find_then_pin(remove)
        for tag in effect.tags:
            grant = keep(_node(ed, FN_ADD_GRANTED_TAG))
            _connect(handle, _pin(grant, "SpecHandle"))
            _set(grant, "NewGameplayTag", f'(TagName="{tag}")')
            _connect(flow, _pin(grant, "execute"))
            handle = _pin(grant, "ReturnValue", is_input=False)
            flow = BEL.find_then_pin(grant)
        apply = keep(_node(ed, FN_APPLY_SPEC_TO_SELF))
        _connect(asc, _pin(apply, "self"))
        _connect(handle, _pin(apply, "SpecHandle"))
        _connect(flow, _pin(apply, "execute"))
        flows = [BEL.find_then_pin(apply), BEL.find_else_pin(lands)]

    ed.add_comment_to_nodes(
        "On hit: " + "; ".join(
            f"{e.chance:.0%} of the time the target gets {e.name} "
            f"({', '.join(e.tags)}), any it already has replaced" for e in ready)
        + f". {ON_HIT_BONUS_VAR} (0 as built) is added to each chance.",
        made)
    return made, flows + [BEL.find_else_pin(gate)]
