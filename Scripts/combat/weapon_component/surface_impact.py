"""A pellet that hit something with no health: chips and dust off the surface
(BP_BulletImpact, combat/bullet_impact.py). impact.py calls in here from the
health cast's failed arm.
"""

from uebp.graph import _connect, _palette, _pin, _set, out
from combat.nodes import NODE_SPAWN

IMPACT_CLASS_VAR = "ImpactClass"   # BP_BulletImpact, a default set by build.py


def _author_surface_impact(ed, where, exec_in):
    """Spawn ImpactClass at ``where``, the transform the blood is spawned at.

    The one transform serves both bursts, because both want the same three
    things: the pellet's impact point, +X turned onto the surface normal (each
    throws its cone along its own forward) and the scale off the round's
    damage. Which burst a pellet gets is the cast alone: a thing with a
    BP_HealthComponent bleeds and anything else chips, so a pellet never
    spawns both. Returns the nodes made.
    """
    cls = ed.add_get_member_variable_node(IMPACT_CLASS_VAR)
    chipped = _palette(ed, NODE_SPAWN)
    _connect(out(cls, IMPACT_CLASS_VAR), _pin(chipped, "Class"))
    _connect(out(where), _pin(chipped, "SpawnTransform"))
    _set(chipped, "CollisionHandlingOverride", "AlwaysSpawn")
    _connect(exec_in, _pin(chipped, "execute"))
    return [cls, chipped]
