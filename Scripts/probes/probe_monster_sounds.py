"""The monsters' sounds, on live wanderers (Sound/sound_monsters.py).

A sound can't be heard in a headless game; this reads what would play it:

  - a zombie's controller holds its three sets of growls (patrol on the timer,
    aggro, attack) and a wendigo's has no aggro or attack takes (silence);
  - a spawned wanderer's footstep component holds the monsters' takes and the
    player's its own: the variant Blueprints inherit BP_ForestWanderer's copy
    of the component, which is where the takes are bound;
  - a zombie shown the player is Aggro, and from then its timed growl never
    comes due (its patrol growls are its patrol's: npc/stats.py).
"""

import math

import unreal

from forest_generator.npc_placement import NPC_VOICE_MAX_S, NPC_VOICE_MIN_S
from npc.paths import AGGRO_VAR, AGGRO_VOICES_VAR, ATTACK_VOICES_VAR, VOICES_VAR
from probes.probe_wendigo_quiet import BEAT_S, SAMPLE_S, _furthest, _lead, _zombies
from probes.probe_wendigo_stalk import _on_navmesh, _wendigos
from Sound.sound_monsters import (
    FOOTSTEP_SOUNDS_VAR, MONSTER_FOOTSTEPS, ZOMBIE_AGGRO, ZOMBIE_ATTACK, ZOMBIE_GROWL)
from Sound.sound_world import FOOTSTEPS

WATCH_S = NPC_VOICE_MAX_S + 1.0   # longer than any gap between two growls
START_CM = 1000.0                 # well inside a zombie's 20 m of sight


def _stand_in_sight(p, ctrl, npc, player):
    """Put the zombie START_CM from the player, facing them, on the first
    bearing where it stands on the navmesh and nothing hides the player."""
    home = player.get_actor_location()
    for yaw in range(0, 360, 30):
        at = home + unreal.Vector(START_CM * math.cos(math.radians(yaw)),
                                  START_CM * math.sin(math.radians(yaw)), 0.0)
        ground = _on_navmesh(p, at)
        if ground is None:
            continue
        npc.set_actor_location_and_rotation(
            ground + unreal.Vector(0.0, 0.0, 95.0),
            unreal.Rotator(pitch=0.0, yaw=yaw + 180.0, roll=0.0), False, True)
        if ctrl.line_of_sight_to(player):
            return yaw
    return None


def _names(p, obj, var):
    return [s.get_name() for s in p.get(obj, var) if s]


def _steps(p, pawn):
    feet = [c for c in pawn.get_components_by_class(unreal.ActorComponent)
            if c.get_class().get_name().startswith("BP_FootstepComponent")]
    return _names(p, feet[0], FOOTSTEP_SOUNDS_VAR) if feet else None


def probe(p):
    yield lambda: _wendigos(p) and _zombies(p)
    yield 1.0
    player = p.pawn()
    zombie, wendigo = _furthest(_zombies(p), player), _furthest(_wendigos(p), player)
    p.check("a zombie and a wendigo are on patrol", zombie is not None and wendigo is not None)
    if zombie is None or wendigo is None:
        return

    got = {v: _names(p, zombie, v) for v in (VOICES_VAR, AGGRO_VOICES_VAR, ATTACK_VOICES_VAR)}
    p.check("the zombie's controller holds its patrol, aggro and attack growls",
            got == {VOICES_VAR: list(ZOMBIE_GROWL.names),
                    AGGRO_VOICES_VAR: list(ZOMBIE_AGGRO.names),
                    ATTACK_VOICES_VAR: list(ZOMBIE_ATTACK.names)}, str(got))
    p.check("the wendigo's has a voice, and no aggro or attack takes: silence there",
            bool(_names(p, wendigo, VOICES_VAR))
            and not _names(p, wendigo, AGGRO_VOICES_VAR)
            and not _names(p, wendigo, ATTACK_VOICES_VAR))
    for who, pawn in (("zombie", zombie.get_controlled_pawn()),
                      ("wendigo", wendigo.get_controlled_pawn())):
        p.check(f"the {who}'s footsteps are the monsters' takes",
                _steps(p, pawn) == list(MONSTER_FOOTSTEPS.names), str(_steps(p, pawn)))
    p.check("the player's are their own", _steps(p, player) == list(FOOTSTEPS.names),
            str(_steps(p, player)))

    # --- shown the player: aggro, and the timer hushed -----------------------
    npc = zombie.get_controlled_pawn()
    if _on_navmesh(p, player.get_actor_location()) is None:
        unreal.SystemLibrary.execute_console_command(
            p.world(), "RebuildNavigation", p.controller())
        p.note("no navmesh under the player: sent RebuildNavigation")
    yield lambda: _on_navmesh(p, player.get_actor_location()) is not None
    yaw = _stand_in_sight(p, zombie, npc, player)
    p.check("the zombie is stood where it can see the player", yaw is not None,
            f"bearing {yaw}")
    if yaw is None:
        return
    limit = p.time() + 10.0
    yield lambda: bool(p.get(zombie, AGGRO_VAR)) or p.time() > limit
    p.check("it is Aggro", bool(p.get(zombie, AGGRO_VAR)))
    yield BEAT_S
    leads, start = [], p.time()
    while p.time() < start + WATCH_S and zombie.get_controlled_pawn() is not None:
        leads.append(_lead(p, zombie))
        yield SAMPLE_S
    p.check(f"hunting, its timed growl is never less than about {NPC_VOICE_MIN_S:g} s "
            f"off for {WATCH_S:g} s: the patrol's growls are not played",
            len(leads) > 10 and min(leads) >= NPC_VOICE_MIN_S - BEAT_S
            and max(leads) <= NPC_VOICE_MIN_S + SAMPLE_S,
            f"{min(leads, default=0):.2f}-{max(leads, default=0):.2f} s off, "
            f"{len(leads)} samples")
