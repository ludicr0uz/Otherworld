"""GA_ConsumeItem: the GameplayAbility that eating and drinking are.

Triggered, not called. Its AbilityTriggers row says "activate on the gameplay
event CONSUME_EVENT_TAG", which is what the weapon component sends when the
fire key is pressed with a Consumable in hand (combat/weapon_component/
consume.py). BP_SurvivalComponent grants it at BeginPlay. So neither side
names the other: the weapon component announces a use, and whatever ability an
actor has been granted for that tag decides what the use does.

    [ActivateAbilityFromEvent(EventData)]
        --> Cast EventData.OptionalObject to BP_ConsumableItem
        --> Cast GetAvatarActor().GetComponentByClass(Survival) to BP_SurvivalComponent
        --> Hunger = clamp(Hunger + HungerRestore, 0, MaxHunger)
        --> Thirst = clamp(Thirst + ThirstRestore, 0, MaxThirst)
        --> on EASY: Health = clamp(Health + HealthRestoreEasy, 0, MaxHealth)
                                    (easy_heal)
        --> EndAbility              (every failed cast ends it too)

Nothing here removes a debuff. Raising Hunger above zero is enough: the
survival component's own debuff sync sees "at zero" and "GE_Starving active"
disagree on its next Tick and removes the effect, so there is one place that
decides when a debuff is on, not two.

Instanced per actor: the ability is stateless, so one instance per owner is
the cheapest policy that still lets a Blueprint graph run (a non-instanced
ability cannot).
"""

import unreal

from combat.graph import (
    BEL, BGE, _assets, _at, _connect, _create_blueprint, _log, _loose_pin,
    _must_load, _node, _palette, _pin, _set,
)
from combat.nodes import (
    FN_ADD_FF, FN_AVATAR, FN_CLAMP, FN_END_ABILITY, FN_GET_COMP,
    NODE_ABILITY_FROM_EVENT, NODE_BREAK_EVENT_DATA,
)
from combat.tuning import CONSUME_EVENT_TAG
from survival.easy_heal import _author_easy_heal
from survival.paths import (
    CONSUMABLE_BP_PATH, CONSUMABLE_CLASS_PATH, CONSUME_ABILITY_PATH,
    NODE_CAST_CONSUMABLE, NODE_CAST_SURVIVAL, SURVIVAL_BP_PATH,
    SURVIVAL_CLASS_PATH,
)

RESTORES = (("Hunger", "HungerRestore"), ("Thirst", "ThirstRestore"))


def _author_graph(ed):
    event = _palette(ed, NODE_ABILITY_FROM_EVENT, 0, 0)
    data = _at(_palette(ed, NODE_BREAK_EVENT_DATA), 0, 300)
    _connect(_loose_pin(event, "EventData", is_input=False),
             BEL.list_input_pins(data)[0])

    as_item = _at(_palette(ed, NODE_CAST_CONSUMABLE), 320, 0)
    _connect(_loose_pin(data, "OptionalObject", is_input=False),
             _pin(as_item, "Object"))
    _connect(BEL.find_then_pin(event), _pin(as_item, "execute"))
    item = _loose_pin(as_item, "AsBPConsumableItem", is_input=False)

    avatar = _at(_node(ed, FN_AVATAR), 320, 300)
    avatar_out = _pin(avatar, "ReturnValue", is_input=False)
    comp = _at(_node(ed, FN_GET_COMP), 560, 300)
    _connect(avatar_out, _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(SURVIVAL_CLASS_PATH)
    as_survival = _at(_palette(ed, NODE_CAST_SURVIVAL), 800, 0)
    _connect(_pin(comp, "ReturnValue", is_input=False), _pin(as_survival, "Object"))
    _connect(BEL.find_then_pin(as_item), _pin(as_survival, "execute"))
    survival = _loose_pin(as_survival, "AsBPSurvivalComponent", is_input=False)

    flow = BEL.find_then_pin(as_survival)
    for i, (stat, restore) in enumerate(RESTORES):
        x = 1100 + i * 800
        now = _at(ed.add_get_member_variable_node(stat, SURVIVAL_CLASS_PATH), x, 300)
        _connect(survival, _pin(now, "self"))
        top = _at(ed.add_get_member_variable_node(f"Max{stat}", SURVIVAL_CLASS_PATH),
                  x, 420)
        _connect(survival, _pin(top, "self"))
        gain = _at(ed.add_get_member_variable_node(restore, CONSUMABLE_CLASS_PATH),
                   x, 540)
        _connect(item, _pin(gain, "self"))
        more = _at(_node(ed, FN_ADD_FF), x + 240, 360)
        _connect(_pin(now, stat, is_input=False), _pin(more, "A"))
        _connect(_pin(gain, restore, is_input=False), _pin(more, "B"))
        clamp = _at(_node(ed, FN_CLAMP), x + 480, 360)
        _connect(_pin(more, "ReturnValue", is_input=False), _pin(clamp, "Value"))
        _set(clamp, "Min", 0.0)
        _connect(_pin(top, f"Max{stat}", is_input=False), _pin(clamp, "Max"))
        write = _at(ed.add_set_member_variable_node(stat, SURVIVAL_CLASS_PATH), x + 480, 0)
        _connect(survival, _pin(write, "self"))
        _connect(_pin(clamp, "ReturnValue", is_input=False), _pin(write, stat))
        _connect(flow, _pin(write, "execute"))
        flow = BEL.find_then_pin(write)

    _heal_nodes, healed = _author_easy_heal(ed, flow, item, avatar_out, 2800, 0)

    # Every path ends the ability, including every failed cast and the heal's
    # not-easy arm: an ability left active would block the next activation of
    # this instance.
    end = _at(_node(ed, FN_END_ABILITY), 4900, 0)
    for e in (*healed, _pin(as_item, "CastFailed", is_input=False),
              _pin(as_survival, "CastFailed", is_input=False)):
        _connect(e, _pin(end, "execute"))

    ed.add_comment_to_nodes(
        f"Triggered by {CONSUME_EVENT_TAG}. The payload's OptionalObject is the "
        "item being used; its HungerRestore/ThirstRestore go onto the avatar's "
        "survival component, clamped to the bars' maxima, and on EASY its "
        "HealthRestoreEasy onto the avatar's health.",
        [event, data, as_item, avatar, comp, as_survival, end])


def _trigger():
    tag = unreal.GameplayTag()
    if not tag.import_text(f'(TagName="{CONSUME_EVENT_TAG}")'):
        raise RuntimeError(f"could not make the tag {CONSUME_EVENT_TAG}")
    row = unreal.AbilityTriggerData()
    row.set_editor_property("trigger_tag", tag)
    row.set_editor_property("trigger_source",
                            unreal.GameplayAbilityTriggerSource.GAMEPLAY_EVENT)
    return row


def build_consume_ability(rebuild=True):
    # Both casts need their classes loaded, or the palette has no entry.
    for path in (CONSUMABLE_BP_PATH, SURVIVAL_BP_PATH):
        _must_load(path)
    bp = _create_blueprint(CONSUME_ABILITY_PATH, unreal.GameplayAbility)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    if rebuild:
        # A fresh GameplayAbility Blueprint ships two placeholder events
        # (ActivateAbility, OnEndAbility). This one answers the event form only.
        nodes = ed.list_all_nodes()
        if nodes:
            ed.remove_nodes(nodes)
    _author_graph(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("GA_ConsumeItem failed to compile")

    cdo = unreal.get_default_object(BEL.generated_class(bp))
    cdo.set_editor_property("ability_triggers", [_trigger()])
    cdo.set_editor_property("instancing_policy",
                            unreal.GameplayAbilityInstancingPolicy.INSTANCED_PER_ACTOR)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("GA_ConsumeItem failed to recompile")
    _assets().save_loaded_asset(bp)

    # Read back as text: AbilityTriggerData exposes no fields to Python, so
    # to_tuple() is () and a field-wise compare would pass on anything.
    fresh = unreal.get_default_object(BEL.generated_class(bp))
    got = [t.export_text() for t in fresh.get_editor_property("ability_triggers")]
    want = [_trigger().export_text()]
    if got != want:
        raise RuntimeError(f"GA_ConsumeItem triggers did not stick: {got} != {want}")
    policy = fresh.get_editor_property("instancing_policy")
    if policy != unreal.GameplayAbilityInstancingPolicy.INSTANCED_PER_ACTOR:
        raise RuntimeError(f"GA_ConsumeItem instancing did not stick: {policy}")
    _log(f"built {CONSUME_ABILITY_PATH} (triggered by {CONSUME_EVENT_TAG})")
    return bp
