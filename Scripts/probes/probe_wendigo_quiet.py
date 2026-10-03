"""A wendigo on patrol makes no sound; once it hunts it growls again
(npc/stats.py's voice on a timer, forest_generator/npc_voice.py).

npc/verify_voice.py reads the graph; this watches the timer in a game. A
growl is played on the pass that finds NextVoiceTime come, and that pass
re-arms it 4-9 s on. So:

  - a patrolling wendigo's NextVoiceTime is never less than about 4 s off,
    for longer than the longest gap between two growls: it never comes due;
  - a patrolling zombie's, over the same seconds, runs down as before;
  - the wendigo, shown the player, is Aggro: its timer runs down from 4 s
    and is re-armed 4-9 s on, which is the growl.
"""

import unreal

from forest_generator.npc_placement import NPC_VOICE_MAX_S, NPC_VOICE_MIN_S
from npc.paths import AGGRO_VAR, NEXT_VOICE_VAR
from probes.probe_wendigo_stalk import _on_navmesh, _stand_in_sight, _wendigos

SAMPLE_S = 0.1
BEAT_S = 0.7                      # the tree's 0.5 s beat, and a sample or two
WATCH_S = NPC_VOICE_MAX_S + 1.0   # longer than any gap between two growls


def _zombies(p):
    ctrls = unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.AIController)
    return [c for c in ctrls
            if c.get_class().get_name().startswith("BP_ForestWandererAI_Zombie")
            and c.get_controlled_pawn() is not None]


def _lead(p, ctrl):
    return float(p.get(ctrl, NEXT_VOICE_VAR)) - p.time()


def _furthest(ctrls, player):
    home = player.get_actor_location()
    quiet = [c for c in ctrls if not c.get_editor_property(AGGRO_VAR)]
    return max(quiet, key=lambda c: (c.get_controlled_pawn().get_actor_location()
                                     - home).length(), default=None)


def probe(p):
    yield lambda: _wendigos(p) and _zombies(p)
    yield 1.0
    player = p.pawn()
    ctrl, zombie = _furthest(_wendigos(p), player), _furthest(_zombies(p), player)
    p.check("a wendigo and a zombie are on patrol", ctrl is not None and zombie is not None)
    if ctrl is None or zombie is None:
        return

    # --- on patrol ------------------------------------------------------------
    leads, theirs, start = [], [], p.time()
    while p.time() < start + WATCH_S:
        if p.get(ctrl, AGGRO_VAR) or p.get(zombie, AGGRO_VAR):
            break
        leads.append(_lead(p, ctrl))
        theirs.append(_lead(p, zombie))
        yield SAMPLE_S
    watched = p.time() - start
    p.check(f"both patrol for the {WATCH_S:g} s watched",
            watched >= WATCH_S and len(leads) > 10, f"{watched:.1f} s, {len(leads)} samples")
    p.check(f"the patrolling wendigo's next growl is never less than about "
            f"{NPC_VOICE_MIN_S:g} s off: it never comes due",
            bool(leads) and min(leads) >= NPC_VOICE_MIN_S - BEAT_S
            and max(leads) <= NPC_VOICE_MIN_S + SAMPLE_S,
            f"{min(leads, default=0):.2f}-{max(leads, default=0):.2f} s off")
    p.check("the patrolling zombie's runs down as before: it growls",
            bool(theirs) and min(theirs) < NPC_VOICE_MIN_S - BEAT_S,
            f"{min(theirs, default=0):.2f}-{max(theirs, default=0):.2f} s off")

    # --- hunting --------------------------------------------------------------
    npc = ctrl.get_controlled_pawn()
    if _on_navmesh(p, player.get_actor_location()) is None:
        unreal.SystemLibrary.execute_console_command(
            p.world(), "RebuildNavigation", p.controller())
        p.note("no navmesh under the player: sent RebuildNavigation")
    yield lambda: _on_navmesh(p, player.get_actor_location()) is not None
    yaw = _stand_in_sight(p, ctrl, npc, player)
    p.check("the wendigo is stood where it can see the player", yaw is not None,
            f"bearing {yaw}")
    if yaw is None:
        return
    limit = p.time() + 10.0
    yield lambda: bool(p.get(ctrl, AGGRO_VAR)) or p.time() > limit
    armed, since = float(p.get(ctrl, NEXT_VOICE_VAR)), p.time()
    p.check(f"it is Aggro, its first growl still about {NPC_VOICE_MIN_S:g} s off "
            f"(not on top of its roar)",
            bool(p.get(ctrl, AGGRO_VAR))
            and NPC_VOICE_MIN_S - BEAT_S <= armed - since <= NPC_VOICE_MIN_S + SAMPLE_S,
            f"{armed - since:.2f} s off")
    low, limit = armed - since, since + NPC_VOICE_MIN_S + 4.0
    while float(p.get(ctrl, NEXT_VOICE_VAR)) == armed and p.time() < limit:
        low = min(low, _lead(p, ctrl))
        yield SAMPLE_S
    after = _lead(p, ctrl)
    p.check("hunting, its timer runs down and comes due: it growls",
            float(p.get(ctrl, NEXT_VOICE_VAR)) != armed and low < BEAT_S,
            f"down to {low:.2f} s, {p.time() - since:.1f} s after it noticed")
    p.check(f"...and the growl after that is {NPC_VOICE_MIN_S:g}-{NPC_VOICE_MAX_S:g} s on",
            NPC_VOICE_MIN_S - BEAT_S <= after <= NPC_VOICE_MAX_S + SAMPLE_S, f"{after:.2f} s")
