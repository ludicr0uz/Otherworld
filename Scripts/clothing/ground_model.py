"""The ground model of a garment that has a mesh to be worn as: that mesh.

The jacket, the pants and the boots lie on the ground as the MetaHuman's
hoodie, jeans and shoes rather than as cubes: one skeletal mesh component,
`Model`, under the item's Body, with no animation, so it holds its reference
pose (a model gun's way: combat/weapon_items.build_model). It is turned by
the row's `lay` to lie flat, then moved so the middle of its bounds is over
the item's origin and its lowest point on it: the origin is where a pick-up
is measured from and where the glimmer hangs, and neither moves.

The mesh asset's own post-process anim Blueprint (the hoodie's, the shoes')
copies the pose of a body the component is attached under. There is none
here, so the component is told not to run it.
"""

import unreal

from combat.weapon_items import KEEP, build_model
from uebp.graph import (
    _component_object, _drop_components, _find_handle, _handles, _must_load, _rot,
)

MODEL = "Model"
_ONE = (1.0, 1.0, 1.0)


def _turned(rotation, vector):
    return unreal.MathLibrary.greater_greater_vector_rotator(vector, rotation)


def lying_box(mesh, rotation, location=None):
    """(centre, half extents) of the mesh's bounds in the item's frame, turned
    by `rotation` and moved by `location`. The turns are quarter turns, so the
    box stays a box."""
    bounds = mesh.get_bounds()
    centre = _turned(rotation, bounds.origin) + (location or unreal.Vector())
    half = _turned(rotation, bounds.box_extent)
    return centre, unreal.Vector(abs(half.x), abs(half.y), abs(half.z))


def model_of(garment):
    """The garment's ground model as build_model takes it: its worn mesh,
    lying flat, centred on the origin and resting on it."""
    rotation = _rot(*garment.lay)
    centre, half = lying_box(_must_load(garment.worn[1]), rotation)
    return ((MODEL, garment.worn[1], (-centre.x, -centre.y, half.z - centre.z),
             rotation, _ONE),)


def build_ground_model(bp, garment):
    """Hang the garment's worn mesh off Body in place of its stand-in parts."""
    _drop_components(bp, {n for _h, n in _handles(bp)} - {MODEL} - KEEP)
    build_model(bp, model_of(garment))
    obj = _component_object(_find_handle(bp, MODEL))
    obj.set_editor_property("disable_post_process_blueprint", True)
