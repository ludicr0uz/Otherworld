"""BP_ThrowArc: the dotted arc drawn while a throw is aimed.

One actor with one InstancedStaticMeshComponent ("Dots") of small emissive
spheres. It never moves and has no graph: the weapon component spawns it the
first time a throw is aimed, then every aimed frame clears it and adds one
world-space instance per predicted point (weapon_component/throw.py). One
component and one draw call, however long the arc is, and no Blueprint loop
over pooled components to keep in step with the prediction's point count.
Emissive for the reason the shells are: a grey dot on the forest floor at
night is not an aim aid.
"""

import unreal

from combat.log import _log
from uebp.graph import (
    BEL, _add_component, _assets, _component_object, _create_blueprint, _drop_components,
    _root_handle)
from combat.materials import build_flat_material
from combat.paths import MAT_THROW_ARC, SPHERE, THROW_ARC_BP_PATH

ARC_COMPONENT = "Dots"
ARC_COLOUR = (0.85, 0.82, 0.70)
ARC_EMISSIVE = (0.90, 0.85, 0.60)


def build_throw_arc():
    build_flat_material(MAT_THROW_ARC, ARC_COLOUR, 0.0, 0.8, ARC_EMISSIVE)
    eas = _assets()
    bp = _create_blueprint(THROW_ARC_BP_PATH, unreal.Actor)
    _drop_components(bp, {ARC_COMPONENT})
    handle = _add_component(bp, _root_handle(bp),
                            unreal.InstancedStaticMeshComponent, ARC_COMPONENT)
    obj = _component_object(handle)
    obj.set_editor_property("static_mesh", eas.load_asset(SPHERE))
    obj.set_editor_property("override_materials", [eas.load_asset(MAT_THROW_ARC)])
    obj.set_editor_property("cast_shadow", False)
    obj.set_collision_profile_name("NoCollision")
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_ThrowArc failed to compile")
    eas.save_loaded_asset(bp)
    _log(f"built {THROW_ARC_BP_PATH}")
    return bp
