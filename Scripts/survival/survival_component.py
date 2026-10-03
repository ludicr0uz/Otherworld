"""BP_SurvivalComponent: the player's hunger, thirst and temperature, how
they fall, and the debuffs at zero.

    [BeginPlay] --> AbilitySystem = GetAbilitySystemComponent(Owner)
                --> if valid: GiveAbility(ConsumeAbility)       eating works

    [Tick] --> Hunger = clamp(Hunger - HungerDecay * dt, 0, MaxHunger)
           --> Thirst = clamp(Thirst - ThirstDecay * dt, 0, MaxThirst)
           --> if AbilitySystem valid: one debuff sync per DEBUFFS row

The stats are Blueprint variables, not GAS attributes: an AttributeSet can only
be declared in C++, and this project has no C++ module on purpose (see
CLAUDE.md). Everything around them is GAS -- the debuffs are GameplayEffects,
eating is a GameplayAbility -- and the component is the seam: the ability
writes Hunger/Thirst here, and the debuff sync reads them.

Granting GA_ConsumeItem is this component's job rather than the character's
because BP_ThirdPersonCharacter's graph is the Enhanced Input template, which
the graph API cannot partially rebuild -- the same reason sprint lives on the
weapon component. It does mean an actor only answers the consume event if it
carries this component, which is exactly the set of actors that get hungry.
"""

import unreal

from combat.log import _log
from uebp.graph import (
    BEL, BGE, _apply_defaults, _connect, _create_blueprint, _declare, _events, _float_type,
    _node, _pin, _set, out, then)
from uebp.layout import arrange
from survival.debuffs import _author_debuff_sync
from survival.paths import SURVIVAL_BP_PATH
from survival.tuning import DEBUFFS, SURVIVAL
from uebp.nodes.actor import FN_GET_OWNER
from uebp.nodes.gas import FN_GET_ASC, FN_GIVE_ABILITY
from uebp.nodes.math import FN_AND, FN_CLAMP, FN_MUL_FF, FN_SUB_FF
from uebp.nodes.system import FN_IS_VALID, FN_IS_VALID_CLASS
from uebp.vars import declare, defaults
from survival.paths import ASC_COMPONENT
from survival import component_vars as UV

STATS = ("Hunger", "Thirst", "Temperature")


def _author_begin_play(ed, begin):
    owner = _node(ed, FN_GET_OWNER)
    lookup = _node(ed, FN_GET_ASC)
    _connect(out(owner), _pin(lookup, "Actor"))
    keep_asc = ed.add_set_member_variable_node(ASC_COMPONENT)
    _connect(out(lookup), _pin(keep_asc, ASC_COMPONENT))
    _connect(then(begin), _pin(keep_asc, "execute"))

    asc = out(ed.add_get_member_variable_node(ASC_COMPONENT), ASC_COMPONENT)
    ability = out(ed.add_get_member_variable_node(UV.ConsumeAbility), UV.ConsumeAbility)
    has_asc = _node(ed, FN_IS_VALID)
    _connect(asc, _pin(has_asc, "Object"))
    has_ability = _node(ed, FN_IS_VALID_CLASS)
    _connect(ability, _pin(has_ability, "Class"))
    both = _node(ed, FN_AND)
    _connect(out(has_asc), _pin(both, "A"))
    _connect(out(has_ability), _pin(both, "B"))
    can = ed.add_branch_node()
    _connect(out(both), _pin(can, "Condition"))
    _connect(then(keep_asc), _pin(can, "execute"))

    give = _node(ed, FN_GIVE_ABILITY)
    _connect(asc, _pin(give, "self"))
    _connect(ability, _pin(give, "AbilityClass"))
    _set(give, "Level", 1)
    _set(give, "InputID", -1)
    _connect(then(can), _pin(give, "execute"))

    ed.add_comment_to_nodes(
        "Find the owner's AbilitySystemComponent (installed next to this "
        "component) and grant it GA_ConsumeItem, the ability that answers the "
        "weapon component's consume event.",
        [owner, lookup, keep_asc, has_asc, has_ability, both, can, give])


def _author_decay(ed, tick, stat, rate_var, max_var, exec_in):
    """stat = clamp(stat - rate * DeltaSeconds, 0, max). Returns the set's then."""
    now = ed.add_get_member_variable_node(stat)
    rate = ed.add_get_member_variable_node(rate_var)
    top = ed.add_get_member_variable_node(max_var)
    step = _node(ed, FN_MUL_FF)
    _connect(out(rate, rate_var), _pin(step, "A"))
    _connect(out(tick, "DeltaSeconds"), _pin(step, "B"))
    less = _node(ed, FN_SUB_FF)
    _connect(out(now, stat), _pin(less, "A"))
    _connect(out(step), _pin(less, "B"))
    clamp = _node(ed, FN_CLAMP)
    _connect(out(less), _pin(clamp, "Value"))
    _set(clamp, "Min", 0.0)
    _connect(out(top, max_var), _pin(clamp, "Max"))
    write = ed.add_set_member_variable_node(stat)
    _connect(out(clamp), _pin(write, stat))
    _connect(exec_in, _pin(write, "execute"))
    return then(write)


def _author_tick(ed, tick):
    flow = then(tick)
    flow = _author_decay(ed, tick, UV.Hunger, "HungerDecay", "MaxHunger", flow)
    flow = _author_decay(ed, tick, UV.Thirst, "ThirstDecay", "MaxThirst", flow)

    # Nested, not folded into each sync's condition: every sync reads off
    # AbilitySystem, and a pure Get with a null self in a Branch condition is
    # an Accessed None on every frame (CLAUDE.md, the fire-gate gotcha).
    asc_get = ed.add_get_member_variable_node(ASC_COMPONENT)
    asc = out(asc_get, ASC_COMPONENT)
    valid = _node(ed, FN_IS_VALID)
    _connect(asc, _pin(valid, "Object"))
    gate = ed.add_branch_node()
    _connect(out(valid), _pin(gate, "Condition"))
    _connect(flow, _pin(gate, "execute"))

    exits = (then(gate),)
    for stat, effect_var, tags in DEBUFFS:
        exits = _author_debuff_sync(ed, asc, stat, effect_var, tags, exits)
    ed.add_comment_to_nodes(
        "Hunger and thirst fall every frame; at zero the matching debuff "
        "GameplayEffect goes on, and comes off when something is eaten.",
        [asc_get, valid, gate])


def build_survival_component(rebuild=True):
    """Declare, author, compile, and write the defaults that need no other asset.

    StarvingEffect / DehydratedEffect / ConsumeAbility are written afterwards by
    build_survival.py, once those assets exist -- GA_ConsumeItem casts to this
    component, so it has to be built after it.
    """
    bp = _create_blueprint(SURVIVAL_BP_PATH, unreal.ActorComponent)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    tick, begin = _events(ed, rebuild)

    for stat in STATS:
        _declare(ed, stat, _float_type())
        _declare(ed, f"Max{stat}", _float_type())
    declare(ed, UV.TABLE)
    _declare(ed, "AbilitySystem", BEL.get_object_reference_type(
        unreal.AbilitySystemComponent.static_class()))
    for _stat, effect_var, _tags in DEBUFFS:
        _declare(ed, effect_var, BEL.get_class_reference_type(
            unreal.GameplayEffect.static_class()))

    _author_begin_play(ed, begin)
    _author_tick(ed, tick)

    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_SurvivalComponent failed to compile")
    _apply_defaults(bp, {**defaults(UV.TABLE),
        UV.Hunger: SURVIVAL.max_hunger,
        UV.MaxHunger: SURVIVAL.max_hunger,
        UV.Thirst: SURVIVAL.max_thirst,
        UV.MaxThirst: SURVIVAL.max_thirst,
        UV.Temperature: SURVIVAL.start_temperature,
        UV.MaxTemperature: SURVIVAL.max_temperature,
    })
    _log(f"built {SURVIVAL_BP_PATH}")
    return bp
