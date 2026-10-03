"""Checks for who growls on patrol (npc/stats.py's voice on a timer, the list
in forest_generator/npc_voice.py), read back off the saved controllers. Run
through Scripts/verify_npc_blueprints.py.

What it proves: every controller's Pulse plays one of its Voices, behind the
timer; a creature of NPC_QUIET_ON_PATROL (the wendigo) reaches that timer only
through a Branch on its own Aggro, and while that is false pushes the next
growl NPC_VOICE_MIN_S off instead, without a sound; any other creature has no
such Branch and growls on patrol as before. That a patrolling wendigo's timer
never comes due in the game, and a hunting one's does, is
probes/probe_wendigo_quiet.py.
"""

import unreal

from forest_generator.npc_placement import NPC_VARIANTS, NPC_VOICE_MIN_S
from forest_generator.npc_voice import NPC_QUIET_ON_PATROL, quiet_on_patrol
from npc.paths import AGGRO_VAR, AI_BP_PATH, NEXT_VOICE_VAR, STEP_PULSE, VOICES_VAR
from npc.verify import (
    _close, _drivers, _exec_reach, _feeders, _ins, _num, _sources, _title, check,
    step_nodes,
)
from npc.verify_ward import _after, _titles
from uebp.graph import else_, then


def _upstream(node):
    """Every node an exec path into ``node`` passes through."""
    seen, todo = {}, list(_drivers(node))
    while todo:
        n = todo.pop()
        if n.get_path_name() in seen:
            continue
        seen[n.get_path_name()] = n
        todo += _drivers(n)
    return list(seen.values())


def _on_aggro(nodes):
    return [n for n in nodes if _title(n) == "Branch"
            and _titles(_feeders(n, "Condition")) == {f"Get {AGGRO_VAR}"}]


def check_settings():
    keys = {v.key for v in NPC_VARIANTS}
    check("voice: every creature that is quiet on patrol is a creature, and the "
          "wendigo is one",
          set(NPC_QUIET_ON_PATROL) <= keys and "Wendigo" in NPC_QUIET_ON_PATROL,
          f"{NPC_QUIET_ON_PATROL}")


def check_voice(path, key):
    tag = path.rsplit("/", 1)[-1]
    bp = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem).load_asset(path)
    if not bp:
        check(f"{tag}: exists, for its voice", False)
        return
    ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, "EventGraph")
    own = step_nodes(ed.list_all_nodes(), STEP_PULSE)
    plays = [n for n in own if {"Sound", "Location"} <= _ins(n)
             and f"Get {VOICES_VAR}" in _titles(_sources(n, "Sound"))]
    check(f"{tag}: its Pulse plays one of its {VOICES_VAR}", len(plays) == 1,
          f"{len(plays)}")
    if len(plays) != 1:
        return
    before = _upstream(plays[0])
    timers = [n for n in before if _title(n) == "Branch"
              and f"Get {NEXT_VOICE_VAR}" in _titles(_sources(n, "Condition"))]
    check(f"{tag}: ...only when {NEXT_VOICE_VAR} has come", len(timers) == 1)
    gates = _on_aggro(before)
    if not quiet_on_patrol(key):
        check(f"{tag}: it growls on patrol too: no Branch on {AGGRO_VAR} ahead of "
              f"its voice", not gates, f"{len(gates)}")
        return
    check(f"{tag}: quiet on patrol: one Branch on its own {AGGRO_VAR} ahead of "
          f"its voice", len(gates) == 1, f"{len(gates)}")
    if len(gates) != 1 or len(timers) != 1:
        return
    gate, timer = gates[0], timers[0]
    check(f"{tag}: ...the timer is read only while it is {AGGRO_VAR}: every way "
          f"into it is that Branch's true side",
          _drivers(timer) == [gate] and _after(then(gate)) == [timer],
          f"{sorted(_titles(_drivers(timer)))}")
    hush = _after(else_(gate))
    later = [f for h in hush for f in _feeders(h, NEXT_VOICE_VAR)]
    check(f"{tag}: ...on patrol the next growl is pushed {NPC_VOICE_MIN_S:g} s "
          f"off instead: {NEXT_VOICE_VAR} = now + {NPC_VOICE_MIN_S:g}",
          len(hush) == 1 and _title(hush[0]) == f"Set {NEXT_VOICE_VAR}"
          and len(later) == 1 and {"A", "B"} <= _ins(later[0])
          and _close(_num(later[0], "B"), NPC_VOICE_MIN_S)
          and len(_feeders(later[0], "A")) == 1,
          f"{sorted(_titles(hush))}")
    check(f"{tag}: ...and nothing is played on that side",
          len(hush) == 1 and plays[0] not in _exec_reach(hush[0])
          and not [n for n in _exec_reach(hush[0]) if {"Sound", "Location"} <= _ins(n)])


def run():
    check_settings()
    check_voice(AI_BP_PATH, NPC_VARIANTS[0].key)
    for variant in NPC_VARIANTS:
        check_voice(variant.ai_blueprint, variant.key)
