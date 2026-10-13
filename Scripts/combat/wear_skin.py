"""Putting the player in its body (wear_skin): the Character's own mesh
component takes the skin's mesh and anim Blueprint, and the MetaHuman is hung
under it or taken away. Moved out of skin.py, which holds what a skin is and
which one the player wears; the build calls this before the weapon specs.
"""

import unreal

from combat import metahuman_body
from combat.log import _log
from combat.paths import CHARACTER_BP_PATH
from combat.skin import player_skin
from uebp.graph import BEL, _assets, _component_object, _handles, _rot

MANNEQUIN_COMPONENT = "Mesh"


def mannequin_component(bp):
    """(template, handle) of the Character's own mesh: the mannequin that is
    animated, whatever is drawn."""
    for handle, name in _handles(bp):
        if name == MANNEQUIN_COMPONENT:
            obj = _component_object(handle)
            if not isinstance(obj, unreal.SkeletalMeshComponent):
                raise RuntimeError(f"{bp.get_name()}.{name} is a {obj.get_class().get_name()}")
            return obj, handle
    raise RuntimeError(f"{bp.get_name()} has no {MANNEQUIN_COMPONENT} component")


def wear_skin(skin=None):
    """Put the player in a body, and run that body's animation.

    Separate from install_on_character, and called before it, because the
    weapon specs are built in between: _grip_rotation() samples the ready pose
    through whatever mesh the player is wearing at the time, so a skin applied
    afterwards would leave five weapons oriented for the previous rig.

    Idempotent, and quiet when there is nothing to do -- the template already
    ships wearing SKM_Quinn_Simple, so a checkout without the asset pipeline
    passes through here writing the values that are already there.
    """
    skin = skin or player_skin()
    eas = _assets()
    bp = eas.load_asset(CHARACTER_BP_PATH)
    if not bp:
        raise RuntimeError(f"could not load {CHARACTER_BP_PATH}")
    mesh_asset = eas.load_asset(skin.mesh)
    if not mesh_asset:
        raise RuntimeError(f"{skin.mesh} is missing — the player would have no body")
    # An anim BP is bound to one skeleton, so a mismatch here is not a cosmetic
    # error: the component silently falls back to the reference pose and the
    # player slides around the map in a T-pose with nothing in the log.
    worn = skin.worn_anim_bp
    anim_class = unreal.load_class(None, f"{worn}.{worn.rsplit('/', 1)[1]}_C")
    if not anim_class:
        raise RuntimeError(f"{worn} has no generated class — it did not compile")

    # By name, not "the first SkeletalMeshComponent": with a MetaHuman worn
    # there are five, and the subobject list is not in tree order.
    comp, mesh_handle = mannequin_component(bp)

    comp.set_editor_property("skeletal_mesh_asset", mesh_asset)
    comp.set_editor_property("anim_class", anim_class)
    comp.set_editor_property("relative_location", unreal.Vector(0.0, 0.0, skin.mesh_z))
    comp.set_editor_property("relative_rotation", _rot(yaw=skin.mesh_yaw))
    # The pose is refreshed whether or not the body is drawn. By default an
    # unrendered mesh keeps its last bones, and behind the sniper's scope the
    # body is hidden from its own camera (weapon_component/sights.py): the
    # gun would freeze in the hand, and the view, which looks down the gun's
    # sight line, could not follow the mouse up or down.
    always = unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES
    comp.set_editor_property("visibility_based_anim_tick_option", always)
    if comp.get_editor_property("visibility_based_anim_tick_option") != always:
        raise RuntimeError("the body would still freeze its pose when not drawn")
    got = comp.get_editor_property("skeletal_mesh_asset")
    if got != mesh_asset or comp.get_editor_property("anim_class") != anim_class:
        raise RuntimeError(f"the skin did not stick: mesh={got}, "
                           f"anim={comp.get_editor_property('anim_class')}")
    # A MetaHuman skin draws the MetaHuman and not the mannequin it hangs
    # under. Hidden, not invisible: the mannequin's children draw on their
    # own, and its pose still updates (the tick option above) for them to
    # follow and for the weapon in its hand.
    comp.set_editor_property("visible", not skin.metahuman)
    if skin.metahuman:
        metahuman_body.install(bp, mesh_handle, skin.retarget)
    else:
        metahuman_body.remove(bp)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_ThirdPersonCharacter failed to compile after the skin")
    eas.save_loaded_asset(bp)
    _log(f"player: wearing {mesh_asset.get_name()} animated by "
         f"{anim_class.get_name()}, weapon on {skin.grip}"
         + (" -- drawn as the MetaHuman" if skin.metahuman else ""))
    return skin
