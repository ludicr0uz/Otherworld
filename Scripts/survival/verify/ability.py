"""GA_ConsumeItem."""

import unreal

from combat.difficulty import DIFFICULTY_VAR, EASY
from combat.tuning import CONSUME_EVENT_TAG
from combat.verify.common import BEL, by_pins, cdo, check, graph, load
from survival.paths import CONSUME_ABILITY_PATH


def run():
    bp = load(CONSUME_ABILITY_PATH)
    check("GA_ConsumeItem exists", bp is not None)
    if not bp:
        return
    d = cdo(bp)
    triggers = [t.export_text() for t in d.get_editor_property("ability_triggers")]
    want = f'(TriggerTag=(TagName="{CONSUME_EVENT_TAG}"),TriggerSource=GameplayEvent)'
    check(f"it is triggered by the gameplay event {CONSUME_EVENT_TAG}",
          triggers == [want], str(triggers))
    check("it is instanced per actor",
          d.get_editor_property("instancing_policy")
          == unreal.GameplayAbilityInstancingPolicy.INSTANCED_PER_ACTOR)
    nodes = graph(bp).list_all_nodes()
    events = [n for n in nodes
              if "EventData" in {str(unreal.BlueprintGraphPinLibrary.get_pin_name(p))
                                 for p in BEL.list_output_pins(n)}]
    check("it answers ActivateAbilityFromEvent (it needs the payload)", len(events) == 1)
    ends = [n for n in nodes if str(BEL.get_node_title(n)).startswith("End Ability")]
    check("one EndAbility", len(ends) == 1, str(len(ends)))
    if ends:
        links = BEL.find_input_pin(ends[0], "execute").list_connected_pins()
        # The heal, its two failed casts and its not-easy arm, plus the item
        # and survival casts failing; a path that never ends the ability
        # leaves the instance active and blocks the next use.
        check("every path ends the ability", len(links) == 6, str(len(links)))
    clamps = by_pins(nodes, "Value", "Min", "Max")
    check("hunger, thirst and health are clamped to their maxima",
          len(clamps) == 3, str(len(clamps)))
    check_easy_heal(nodes)


def check_easy_heal(nodes):
    """The heal happens on EASY only, from the GameState's Difficulty."""
    easy = [n for n in by_pins(nodes, "A", "B")
            if any("Get " + DIFFICULTY_VAR == str(BEL.get_node_title(
                       unreal.BlueprintGraphPinLibrary.get_owning_node(q)))
                   for q in BEL.find_input_pin(n, "A").list_connected_pins())]
    # A literal 0 reads back as "" once the asset is reloaded from disk (an
    # int pin at its default is not stored); an empty int pin compiles as 0.
    check(f"the heal is gated on the GameState's {DIFFICULTY_VAR} == EASY",
          len(easy) == 1
          and int(BEL.find_input_pin(easy[0], "B").get_pin_value() or 0) == EASY,
          str([BEL.find_input_pin(n, "B").get_pin_value() for n in easy]))
    titles = {str(BEL.get_node_title(n)) for n in nodes}
    check("...and adds the item's HealthRestoreEasy to Health",
          {"Get HealthRestoreEasy", "Get MaxHealth"} <= titles
          # Health is a RepNotify (combat/damage.py), and its Set is titled so.
          and titles & {"Set with Notify Health", "Set Health"},
          str(sorted(t for t in titles if "Health" in t)))
