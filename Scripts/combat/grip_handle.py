"""The grip an item is held by, as a component the editor can move: `Grip`, a
SceneComponent on every held item's Blueprint, which the game reads when it
puts the item in the hand (weapon_component/inventory.py).

WHAT IT MARKS
-------------
Where the hand's grip socket is, in the item's own frame. Equipping attaches
the item to the socket and moves it so that Grip lands on the socket: the
item's place in the hand is the inverse of Grip's relative transform. Moving
Grip 2 cm towards the muzzle therefore moves the gun 2 cm back in the fist.

WHO WRITES IT
-------------
The build solves a grip per item (grip.py) and writes it to GripLocation and
GripRotation, as it always did; those two variables are now the SEED, what
the solve says, and nothing in the game reads them. seed_grip() makes the
component from them when it is missing. When it exists:

  * still where the last build's seed put it: nobody moved it, so it follows
    the solve (a ready pose that changed moves the fist, and the grip with it);
  * anywhere else: somebody placed it by eye, and no build touches it again.

To give a placed grip back to the solve, delete the component in the Blueprint
editor and rebuild. docs/aiming.md has the steps for placing one.
"""

import unreal

from combat.log import _log
from uebp.graph import BEL, _add_component, _component_object, _find_handle

# The component's name, and the tag the weapon component finds it by: the
# items add it one by one, so their base class has no variable for it.
GRIP = "Grip"
# Under the actor's root, whose relative transform is the one the equip sets.
ROOT = "DefaultSceneRoot"
# A grip this near the seed (cm, degrees) was not moved by anyone: the
# round trip through two inversions is exact to 1e-4.
SEED_CM = 0.01
SEED_DEG = 0.01


def _inverse(location, rotation):
    return unreal.Transform(location=location, rotation=rotation,
                            scale=unreal.Vector(1.0, 1.0, 1.0)).inverse()


def apart(a, b):
    """(cm, degrees) between two (location, rotation) grips."""
    turn = a[1].quaternion().angular_distance(b[1].quaternion())
    return (a[0] - b[0]).length(), abs(unreal.MathLibrary.radians_to_degrees(turn))


def _template(bp):
    handle = _find_handle(bp, GRIP)
    return _component_object(handle) if handle else None


def _held_at(component):
    xf = _inverse(component.get_editor_property("relative_location"),
                  component.get_editor_property("relative_rotation"))
    return xf.translation, xf.rotation.rotator()


def saved_grip(bp):
    """(location, rotation) of the item in the grip socket's frame, as its
    Grip component has it: what the game seats it by. None with no Grip."""
    component = _template(bp)
    return _held_at(component) if component else None


def seed_of(bp):
    """(GripLocation, GripRotation) off the compiled class: the solved grip."""
    d = unreal.get_default_object(BEL.generated_class(bp))
    return d.get_editor_property("GripLocation"), d.get_editor_property("GripRotation")


def placed_by_hand(bp):
    """(cm, degrees) the saved grip is off its seed, or None where it is the
    seed (or there is no grip at all)."""
    saved = saved_grip(bp)
    if saved is None:
        return None
    off = apart(saved, seed_of(bp))
    return off if off[0] > SEED_CM or off[1] > SEED_DEG else None


def seed_grip(bp, location, rotation):
    """Give ``bp`` its Grip at the solved (location, rotation), unless
    somebody placed it. Call it on a compiled Blueprint, BEFORE the defaults
    that write the new seed: the old seed is how a moved grip is told from an
    untouched one. Returns True when it wrote the component."""
    name = bp.get_name()
    want = (location, rotation)
    component = _template(bp)
    if component is None:
        root = _find_handle(bp, ROOT)
        if not root:
            raise RuntimeError(f"{name} has no {ROOT} to hang its {GRIP} on")
        component = _component_object(
            _add_component(bp, root, unreal.SceneComponent, GRIP))
    else:
        moved = placed_by_hand(bp)
        if moved:
            off = apart(_held_at(component), want)
            _log(f"{name}: {GRIP} was placed by hand ({off[0]:.2f} cm, "
                 f"{off[1]:.1f} deg off the solve), left alone")
            _tag(component)
            return False
        if apart(_held_at(component), want) == (0.0, 0.0):
            _tag(component)
            return False
    at = _inverse(location, rotation)
    component.set_editor_property("relative_location", at.translation)
    component.set_editor_property("relative_rotation", at.rotation.rotator())
    _tag(component)
    back = apart(_held_at(component), want)
    if back[0] > SEED_CM or back[1] > SEED_DEG:
        raise RuntimeError(f"{name}: {GRIP} did not take the solved grip, "
                           f"{back[0]:.3f} cm and {back[1]:.3f} deg off")
    return True


def _tag(component):
    if not component.component_has_tag(GRIP):
        component.set_editor_property("component_tags", [unreal.Name(GRIP)])
