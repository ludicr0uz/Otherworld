"""Place the Horde Survival level's director into the open level, and verify it.

The director is the native AOtherworldHordeDirector (Source/Otherworld): the
level's difficulty, a level every three minutes of play, each holding more
zombies and, from level 4, wendigos (forest_generator/npc_horde.py has the
rule and its numbers, written onto the actor here). place_fort places it
with the fort, so a level in horde_layout.HORDE_LEVELS has one; verify_fort
holds it to npc_horde.py.
"""

import unreal

from combat import health_vars as HV
from forest_generator import npc_horde as H
from forest_generator.npc_placement import NPC_VARIANTS

DIRECTOR_CLASS_PATH = "/Script/Otherworld.OtherworldHordeDirector"
DIRECTOR_LABEL = "Horde_Director"
ZOMBIE_CLASS_PATH = next(f"{v.blueprint}.{v.blueprint.rsplit('/', 1)[1]}_C"
                         for v in NPC_VARIANTS if v.key == "Zombie")
WENDIGO_CLASS_PATH = next(f"{v.blueprint}.{v.blueprint.rsplit('/', 1)[1]}_C"
                          for v in NPC_VARIANTS if v.key == "Wendigo")

# The actor's numbers, from npc_horde.py: (property, value).
NUMBERS = (
    ("step_seconds", H.HORDE_STEP_S),
    ("first_count", H.HORDE_FIRST_COUNT),
    ("per_level", H.HORDE_PER_LEVEL),
    ("wendigo_every_levels", H.HORDE_WENDIGO_EVERY),
    ("max_level", H.HORDE_MAX_LEVEL),
    ("spawn_min", H.HORDE_SPAWN_MIN_CM),
    ("spawn_max", H.HORDE_SPAWN_MAX_CM),
    ("delay", H.HORDE_DELAY_S),
)


def _log(msg):
    unreal.log_warning(f"[GEN] {msg}")


def place_director(actor_sub, at):
    """The level's one director, at ``at`` (an unreal.Vector). Any earlier
    one goes first, so a re-run leaves one."""
    for actor in actor_sub.get_all_level_actors():
        if actor.get_actor_label() == DIRECTOR_LABEL:
            actor_sub.destroy_actor(actor)
    cls = unreal.load_class(None, DIRECTOR_CLASS_PATH)
    zombie = unreal.load_class(None, ZOMBIE_CLASS_PATH)
    wendigo = unreal.load_class(None, WENDIGO_CLASS_PATH)
    if not (cls and zombie and wendigo):
        unreal.log_error(f"[GEN] No horde director: class {cls}, zombie {zombie}, "
                         f"wendigo {wendigo} (compile the module, build the NPCs).")
        return None
    actor = actor_sub.spawn_actor_from_class(cls, at, unreal.Rotator(0.0, 0.0, 0.0))
    actor.set_actor_label(DIRECTOR_LABEL)
    actor.set_folder_path("Fort")
    actor.set_editor_property("zombie_class", zombie)
    actor.set_editor_property("wendigo_class", wendigo)
    actor.set_editor_property("replacement_var", str(HV.RespawnClass))
    for prop, value in NUMBERS:
        actor.set_editor_property(prop, value)
    _log(f"Placed the horde director (a level every {H.HORDE_STEP_S:g} s)")
    return actor


def check_director(check, actors):
    """The level holds one director, of the native class, with npc_horde.py's
    numbers and the two creatures."""
    found = [a for a in actors if a.get_actor_label() == DIRECTOR_LABEL]
    cls = found[0].get_class().get_path_name() if len(found) == 1 else None
    check("Horde Has One Director", len(found) == 1 and cls == DIRECTOR_CLASS_PATH,
          f"({len(found)} found, class {cls})")
    if len(found) != 1:
        return
    d = found[0]
    bad = [f"{p} {d.get_editor_property(p)}" for p, v in NUMBERS
           if abs(float(d.get_editor_property(p)) - float(v)) > 1e-3]
    check("Horde Director Numbers Are npc_horde.py's", not bad, f"{bad}")
    kinds = {p: (d.get_editor_property(p).get_path_name() if d.get_editor_property(p) else None)
             for p in ("zombie_class", "wendigo_class")}
    check("Horde Director Holds The Zombie And The Wendigo",
          kinds == {"zombie_class": ZOMBIE_CLASS_PATH, "wendigo_class": WENDIGO_CLASS_PATH},
          f"{kinds}")
    check("Horde Director Turns Off The Replacement Variable",
          str(d.get_editor_property("replacement_var")) == str(HV.RespawnClass),
          f"({d.get_editor_property('replacement_var')})")
