"""GA_ConsumeItem."""

import unreal

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
        # The success path and both failed casts; a path that never ends the
        # ability leaves the instance active and blocks the next use.
        check("every path ends the ability", len(links) == 3, str(len(links)))
    clamps = by_pins(nodes, "Value", "Min", "Max")
    check("hunger and thirst are clamped to their maxima", len(clamps) == 2)
