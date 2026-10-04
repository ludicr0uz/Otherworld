"""Checks for who growls on patrol (npc/stats.py's voice on a timer, the list
in forest_generator/npc_voice.py), read back off the saved controllers. Run
through Scripts/verify_npc_blueprints.py.

What it proves: every controller's Pulse plays one of its Voices, behind the
timer; a creature of NPC_QUIET_ON_PATROL (the wendigo) reaches that timer only
through a Branch on its own Aggro, and while that is false pushes the next
growl NPC_VOICE_MIN_S off instead, without a sound; one of NPC_QUIET_ON_HUNT
(the zombie) has the same Branch the other way round; any other creature has
no such Branch. And the two voices that are not on the timer: one of its
AggroVoices right behind the one write of Aggro, one of its AttackVoices as a
swing starts, and which takes each creature's arrays hold
(Sound/sound_monsters.py). That a patrolling wendigo's timer
never comes due in the game, and a hunting one's does, is
probes/probe_wendigo_quiet.py.
"""

import unreal

from forest_generator.npc_placement import NPC_VARIANTS, NPC_VOICE_MIN_S
from forest_generator.npc_voice import (
    NPC_QUIET_ON_HUNT, NPC_QUIET_ON_PATROL, quiet_on_hunt, quiet_on_patrol)
from npc.paths import (
    AGGRO_VAR, AGGRO_VOICES_VAR, AI_BP_PATH, ATTACK_VOICES_VAR, NEXT_VOICE_VAR, STEP_PULSE,
    STEP_SWING, VOICES_VAR)
from npc.verify import (
    _close, _drivers, _exec_reach, _feeders, _ins, _num, _sources, _title, check,
    step_nodes,
)
from npc.verify_ward import _after, _titles
from Sound.bind import takes_of
from Sound.sound_monsters import (
    BINDINGS, ZOMBIE_AGGRO, ZOMBIE_AGGRO_TAKES, ZOMBIE_ATTACK, ZOMBIE_ATTACK_TAKES,
    ZOMBIE_GROWL)
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
    check("voice: the zombie's timed growls are its patrol's, and no creature is "
          "quiet both ways",
          set(NPC_QUIET_ON_HUNT) <= keys and "Zombie" in NPC_QUIET_ON_HUNT
          and not set(NPC_QUIET_ON_HUNT) & set(NPC_QUIET_ON_PATROL), f"{NPC_QUIET_ON_HUNT}")
    numbered = [int(n.rsplit("_", 1)[1]) for n in ZOMBIE_GROWL.names]
    check("voice: zombie growls 1, 2 and 4 are its attack's, 10 its aggro's, and "
          "every other one its patrol's",
          ZOMBIE_ATTACK_TAKES == (1, 2, 4) and ZOMBIE_AGGRO_TAKES == (10,)
          and [n.rsplit("_", 1)[1] for n in ZOMBIE_ATTACK.names] == ["01", "02", "04"]
          and [n.rsplit("_", 1)[1] for n in ZOMBIE_AGGRO.names] == ["10"]
          and numbered == [3, 5, 6, 7, 8, 9, 11], f"patrol {numbered}")


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
    patrol_quiet, hunt_quiet = quiet_on_patrol(key), quiet_on_hunt(key)
    if not (patrol_quiet or hunt_quiet):
        check(f"{tag}: it growls on patrol and on the hunt: no Branch on {AGGRO_VAR} "
              f"ahead of its voice", not gates, f"{len(gates)}")
        return
    quiet = "on patrol" if patrol_quiet else "on the hunt"
    check(f"{tag}: quiet {quiet}: one Branch on its own {AGGRO_VAR} ahead of "
          f"its voice", len(gates) == 1, f"{len(gates)}")
    if len(gates) != 1 or len(timers) != 1:
        return
    gate, timer = gates[0], timers[0]
    loud, hushed = (then, else_) if patrol_quiet else (else_, then)
    check(f"{tag}: ...the timer is read only while it is "
          f"{'' if patrol_quiet else 'not '}{AGGRO_VAR}: every way "
          f"into it is that Branch's {'true' if patrol_quiet else 'false'} side",
          _drivers(timer) == [gate] and _after(loud(gate)) == [timer],
          f"{sorted(_titles(_drivers(timer)))}")
    hush = _after(hushed(gate))
    later = [f for h in hush for f in _feeders(h, NEXT_VOICE_VAR)]
    check(f"{tag}: ...{quiet} the next growl is pushed {NPC_VOICE_MIN_S:g} s "
          f"off instead: {NEXT_VOICE_VAR} = now + {NPC_VOICE_MIN_S:g}",
          len(hush) == 1 and _title(hush[0]) == f"Set {NEXT_VOICE_VAR}"
          and len(later) == 1 and {"A", "B"} <= _ins(later[0])
          and _close(_num(later[0], "B"), NPC_VOICE_MIN_S)
          and len(_feeders(later[0], "A")) == 1,
          f"{sorted(_titles(hush))}")
    check(f"{tag}: ...and nothing is played on that side",
          len(hush) == 1 and plays[0] not in _exec_reach(hush[0])
          and not [n for n in _exec_reach(hush[0]) if {"Sound", "Location"} <= _ins(n)])


def _plays(nodes, var):
    """The play nodes among ``nodes`` that draw their sound from ``var``."""
    return [n for n in nodes if {"Sound", "Location"} <= _ins(n)
            and f"Get {var}" in _titles(_sources(n, "Sound"))]


def check_untimed(path, key):
    """The voices that are not on the timer: going aggro, and a swing."""
    tag = path.rsplit("/", 1)[-1]
    bp = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem).load_asset(path)
    if not bp:
        return
    ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, "EventGraph")
    nodes = ed.list_all_nodes()
    flips = [n for n in nodes if _title(n) == f"Set {AGGRO_VAR}"]
    cries = _plays(nodes, AGGRO_VOICES_VAR)
    check(f"{tag}: going aggro, it plays one of its {AGGRO_VOICES_VAR}, the once: "
          f"behind its one write of {AGGRO_VAR} and nowhere else",
          len(cries) == 1 and len(flips) == 1 and cries[0] in _exec_reach(flips[0])
          and flips[0] not in _exec_reach(cries[0]),
          f"{len(cries)} play(s), {len(flips)} write(s)")
    snarls = _plays(nodes, ATTACK_VOICES_VAR)
    swing = step_nodes(nodes, STEP_SWING)
    montages = [n for n in swing if {"Asset", "SlotNodeName"} <= _ins(n)]
    check(f"{tag}: a swing plays one of its {ATTACK_VOICES_VAR} as it starts: in "
          f"its Swing step, ahead of the clip",
          len(snarls) == 1 and snarls[0] in swing and len(montages) == 1
          and montages[0] in _exec_reach(snarls[0]),
          f"{len(snarls)} play(s), {len(montages)} clip(s)")
    cdo = unreal.get_default_object(unreal.BlueprintEditorLibrary.generated_class(bp))
    for var, names in sorted(takes_of(path, BINDINGS).items()):
        got = [s.get_name() for s in cdo.get_editor_property(var) if s]
        check(f"{tag}.{var} holds its {len(names)} take(s)", got == list(names), str(got))
    if key is not None:
        bound = set(takes_of(path, BINDINGS))
        empty = [v for v in (AGGRO_VOICES_VAR, ATTACK_VOICES_VAR)
                 if v not in bound and len(cdo.get_editor_property(v))]
        check(f"{tag}: a voice it has no takes for is empty (silence)", not empty,
              str(empty))


def run():
    check_settings()
    check_voice(AI_BP_PATH, NPC_VARIANTS[0].key)
    check_untimed(AI_BP_PATH, None)
    for variant in NPC_VARIANTS:
        check_voice(variant.ai_blueprint, variant.key)
        check_untimed(variant.ai_blueprint, variant.key)
