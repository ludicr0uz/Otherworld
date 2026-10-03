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

from combat.graph import (
    BEL, BGE, _apply_defaults, _connect, _create_blueprint, _declare, _events, _float_type,
    _log, _node, _pin, _set)
from uebp.layout import arrange
from combat.nodes import (
    FN_AND, FN_CLAMP, FN_GET_ASC, FN_GET_OWNER, FN_GIVE_ABILITY, FN_IS_VALID,
    FN_IS_VALID_CLASS, FN_MUL_FF, FN_SUB_FF,
)
from survival.debuffs import _author_debuff_sync
from survival.paths import SURVIVAL_BP_PATH
from survival.tuning import DEBUFFS, SURVIVAL

STATS = ("Hunger", "Thirst", "Temperature")


def _author_begin_play(ed, begin):
    owner = _node(ed, FN_GET_OWNER)
    lookup = _node(ed, FN_GET_ASC)
    _connect(_pin(owner, "ReturnValue", is_input=False), _pin(lookup, "Actor"))
    keep_asc = ed.add_set_member_variable_node("AbilitySystem")
    _connect(_pin(lookup, "ReturnValue", is_input=False),
             _pin(keep_asc, "AbilitySystem"))
    _connect(BEL.find_then_pin(begin), _pin(keep_asc, "execute"))

    asc = _pin(ed.add_get_member_variable_node("AbilitySystem"), "AbilitySystem", is_input=False)
    ability = _pin(ed.add_get_member_variable_node("ConsumeAbility"),
                   "ConsumeAbility", is_input=False)
    has_asc = _node(ed, FN_IS_VALID)
    _connect(asc, _pin(has_asc, "Object"))
    has_ability = _node(ed, FN_IS_VALID_CLASS)
    _connect(ability, _pin(has_ability, "Class"))
    both = _node(ed, FN_AND)
    _connect(_pin(has_asc, "ReturnValue", is_input=False), _pin(both, "A"))
    _connect(_pin(has_ability, "ReturnValue", is_input=False), _pin(both, "B"))
    can = ed.add_branch_node()
    _connect(_pin(both, "ReturnValue", is_input=False), _pin(can, "Condition"))
    _connect(BEL.find_then_pin(keep_asc), _pin(can, "execute"))

    give = _node(ed, FN_GIVE_ABILITY)
    _connect(asc, _pin(give, "self"))
    _connect(ability, _pin(give, "AbilityClass"))
    _set(give, "Level", 1)
    _set(give, "InputID", -1)
    _connect(BEL.find_then_pin(can), _pin(give, "execute"))

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
    _connect(_pin(rate, rate_var, is_input=False), _pin(step, "A"))
    _connect(_pin(tick, "DeltaSeconds", is_input=False), _pin(step, "B"))
    less = _node(ed, FN_SUB_FF)
    _connect(_pin(now, stat, is_input=False), _pin(less, "A"))
    _connect(_pin(step, "ReturnValue", is_input=False), _pin(less, "B"))
    clamp = _node(ed, FN_CLAMP)
    _connect(_pin(less, "ReturnValue", is_input=False), _pin(clamp, "Value"))
    _set(clamp, "Min", 0.0)
    _connect(_pin(top, max_var, is_input=False), _pin(clamp, "Max"))
    write = ed.add_set_member_variable_node(stat)
    _connect(_pin(clamp, "ReturnValue", is_input=False), _pin(write, stat))
    _connect(exec_in, _pin(write, "execute"))
    return BEL.find_then_pin(write)


def _author_tick(ed, tick):
    flow = BEL.find_then_pin(tick)
    flow = _author_decay(ed, tick, "Hunger", "HungerDecay", "MaxHunger", flow)
    flow = _author_decay(ed, tick, "Thirst", "ThirstDecay", "MaxThirst", flow)

    # Nested, not folded into each sync's condition: every sync reads off
    # AbilitySystem, and a pure Get with a null self in a Branch condition is
    # an Accessed None on every frame (CLAUDE.md, the fire-gate gotcha).
    asc_get = ed.add_get_member_variable_node("AbilitySystem")
    asc = _pin(asc_get, "AbilitySystem", is_input=False)
    valid = _node(ed, FN_IS_VALID)
    _connect(asc, _pin(valid, "Object"))
    gate = ed.add_branch_node()
    _connect(_pin(valid, "ReturnValue", is_input=False), _pin(gate, "Condition"))
    _connect(flow, _pin(gate, "execute"))

    exits = (BEL.find_then_pin(gate),)
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
    for name in ("HungerDecay", "ThirstDecay"):
        _declare(ed, name, _float_type())
    _declare(ed, "AbilitySystem", BEL.get_object_reference_type(
        unreal.AbilitySystemComponent.static_class()))
    for _stat, effect_var, _tags in DEBUFFS:
        _declare(ed, effect_var, BEL.get_class_reference_type(
            unreal.GameplayEffect.static_class()))
    _declare(ed, "ConsumeAbility", BEL.get_class_reference_type(
        unreal.GameplayAbility.static_class()))

    _author_begin_play(ed, begin)
    _author_tick(ed, tick)

    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_SurvivalComponent failed to compile")
    _apply_defaults(bp, {
        "Hunger": SURVIVAL.max_hunger,
        "MaxHunger": SURVIVAL.max_hunger,
        "Thirst": SURVIVAL.max_thirst,
        "MaxThirst": SURVIVAL.max_thirst,
        "Temperature": SURVIVAL.start_temperature,
        "MaxTemperature": SURVIVAL.max_temperature,
        "HungerDecay": SURVIVAL.hunger_decay_per_s,
        "ThirstDecay": SURVIVAL.thirst_decay_per_s,
    })
    _log(f"built {SURVIVAL_BP_PATH}")
    return bp
