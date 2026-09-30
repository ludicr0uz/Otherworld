"""What the player wears: the PlayerSkin table (Quinn fallback, generated
adventurer) and wear_skin(), which puts it on BP_ThirdPersonCharacter.
"""

import dataclasses

import unreal

from combat.graph import BEL, _assets, _component_object, _handles, _log, _rot
from combat.paths import CHARACTER_BP_PATH


# ─── What the player is wearing ──────────────────────────────────────────────
#
# The player used to be SKM_Quinn_Simple and nothing else could be said about
# it: the mesh, the ready poses, the grip socket and the bone the aim pose is
# blended from were four literals scattered through this file that all happened
# to describe the Epic mannequin. They are one record now, because changing the
# player's body means changing all four together or not at all.
#
# ── Why the adventurer is on its own skeleton, and not on SK_Mannequin ──
#
# The obvious integration -- generate a new mesh and bind it to the skeleton
# everything here already depends on -- is not reachable from this toolchain,
# and it was probed before a credit was spent rather than after:
#
#   * Meshy's rigging endpoint takes an input mesh and a height and nothing
#     else. There is no skeleton-convention parameter, so what comes back is
#     always its own 24-bone Mixamo-named rig (measured: Hips, Spine02..Spine,
#     LeftArm..LeftHand, neck, Head -- no fingers, no twist bones; the
#     fingers are added afterwards, see below).
#   * Re-binding that mesh at import time is not a matter of asking: the FBX
#     importer merges the incoming bone tree into the supplied skeleton, and
#     24 differently-named bones do not merge into SK_Mannequin's 161.
#   * And UE 5.8 exposes no skin transfer to Python. IKRetargetBatchOperation
#     retargets *animation* assets only; IKRetargeterController has no mesh
#     export, so the editor's "retarget skeletal mesh" button has no scripted
#     equivalent. A project with no C++ module cannot reach the C++ that does it.
#
# So the animation moves to the mesh instead of the mesh to the skeleton --
# exactly what the monsters already do, through build_retarget.py -- and the
# three things that made that sound dangerous turn out to be rig-agnostic
# already: hit_zones() derives its tables from whatever mesh the character is
# wearing, the ragdoll is SetAllBodiesSimulatePhysics on whatever physics asset
# that mesh carries, and the locomotion is a retargeted copy of ABP_Unarmed
# that fix_retargeted_abp() has already re-pointed at the new spine.
#
# Finger articulation was the one thing lost, and it is back: a 24-bone rig
# cannot close a fist, so asset_pipeline/finger_rig.py adds 15 finger bones per
# hand after import and skins them, and the retargeted ready poses curl them
# round the grip the way the mannequin's do.
@dataclasses.dataclass(frozen=True)
class PlayerSkin:
    """The player's body: mesh, animation, and where a weapon sits in it."""

    mesh: str
    anim_bp: str
    # Attachment point for the held weapon. A socket where the rig has one; a
    # BONE name otherwise -- AttachToComponent resolves either out of the same
    # namespace, and Python cannot mint a socket (SkeletalMeshSocket's
    # SocketName and BoneName are both read-only, checked).
    grip: str
    aim_rifle: str
    aim_pistol: str
    # The grip hand's four closing fingers, index first, each as its three
    # joints from the knuckle out. grip.fist_in_socket() finds where they curl
    # round, and the weapon's handle is put there. The thumb wraps the other
    # way and is not in; the index's outer joints rest on the trigger.
    grip_fingers: tuple
    # The two spine joints that pitch the upper body onto the aim down the
    # sights, lower first; each takes half (aim_pitch.py). Everything above
    # them -- chest, arms, head and the weapon in the hand -- turns rigidly.
    aim_bones: tuple
    # The bones the procedural stance and guard poses turn (body_pose.py), by
    # role: hips, spine (the lowest spine joint), neck, and per side
    # clavicle / upperarm / forearm / hand / thigh / calf / foot as "<role>_l|_r".
    # The chest is aim_bones[-1].
    pose_bones: dict
    # The empty-handed punch (weapon_component/punch.py): MM_Attack_01 on this
    # rig, played into the upper-body slot.
    punch: str
    # Mesh component transform inside the actor. The template's own numbers;
    # they are a property of a 1.8 m humanoid standing in an 88 cm capsule
    # facing +X, not of the mannequin, which is why the Meshy skin reuses them.
    mesh_z: float = -89.0
    mesh_yaw: float = 270.0


SKIN_QUINN = PlayerSkin(
    mesh="/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple",
    anim_bp="/Game/Characters/Mannequins/Anims/Unarmed/ABP_Unarmed",
    grip="HandGrip_R",
    aim_rifle="/Game/Characters/Mannequins/Anims/Rifle/MF_Rifle_Idle_ADS",
    aim_pistol="/Game/Characters/Mannequins/Anims/Pistol/MF_Pistol_Idle_ADS",
    grip_fingers=tuple(tuple(f"{f}_{j:02d}_r" for j in (1, 2, 3))
                       for f in ("index", "middle", "ring", "pinky")),
    aim_bones=("spine_03", "spine_05"),
    pose_bones=dict(
        hips="pelvis", spine="spine_01", neck="neck_01",
        **{f"{role}_{s}": f"{bone}_{s}" for s in "lr" for role, bone in (
            ("clavicle", "clavicle"), ("upperarm", "upperarm"),
            ("forearm", "lowerarm"), ("hand", "hand"), ("thigh", "thigh"),
            ("calf", "calf"), ("foot", "foot"))}),
    punch="/Game/Characters/Mannequins/Anims/Unarmed/Attack/MM_Attack_01",
)

# Built by Scripts/asset_pipeline: fetch_monsters.py -> import_characters.py ->
# build_retarget.py. Every path here is under /Game/Sourced, which is
# git-ignored, so a checkout that has never run the pipeline has none of it and
# falls back to the mannequin above -- the same bargain build_npc_blueprints.py
# strikes, and for the same reason: a player who looks wrong is a far better
# failure than a build that stops.
ADVENTURER = "Adventurer01"
SKIN_ADVENTURER = PlayerSkin(
    mesh=f"/Game/Sourced/Characters/SKM_{ADVENTURER}/SKM_{ADVENTURER}",
    anim_bp=f"/Game/Sourced/Characters/Anims/{ADVENTURER}/A_{ADVENTURER}_ABP_Unarmed",
    grip="RightHand",
    aim_rifle=f"/Game/Sourced/Characters/Anims/{ADVENTURER}/"
              f"A_{ADVENTURER}_MF_Rifle_Idle_ADS",
    aim_pistol=f"/Game/Sourced/Characters/Anims/{ADVENTURER}/"
               f"A_{ADVENTURER}_MF_Pistol_Idle_ADS",
    # asset_pipeline/finger_rig.py adds these, named the Mixamo way.
    grip_fingers=tuple(tuple(f"RightHand{f}{j}" for j in (1, 2, 3))
                       for f in ("Index", "Middle", "Ring", "Pinky")),
    # Meshy numbers its spine backwards: Hips -> Spine02 -> Spine01 -> Spine.
    aim_bones=("Spine01", "Spine"),
    pose_bones=dict(
        hips="Hips", spine="Spine02", neck="neck",
        **{f"{role}_{s}": f"{side}{bone}" for s, side in (("l", "Left"), ("r", "Right"))
           for role, bone in (("clavicle", "Shoulder"), ("upperarm", "Arm"),
                              ("forearm", "ForeArm"), ("hand", "Hand"),
                              ("thigh", "UpLeg"), ("calf", "Leg"), ("foot", "Foot"))}),
    # build_retarget.py makes it for every creature (MELEE_SOURCE).
    punch=f"/Game/Sourced/Characters/Anims/{ADVENTURER}/A_{ADVENTURER}_MM_Attack_01",
)


def player_skin():
    """The adventurer if the pipeline has produced all of it, else the mannequin.

    All of its assets or none: a skin resolved piecemeal is the failure that
    cannot be read off a log -- the adventurer's mesh wearing the mannequin's
    anim BP compiles, runs, and stands in the reference pose forever.
    """
    eas = _assets()
    want = (SKIN_ADVENTURER.mesh, SKIN_ADVENTURER.anim_bp,
            SKIN_ADVENTURER.aim_rifle, SKIN_ADVENTURER.aim_pistol,
            SKIN_ADVENTURER.punch)
    missing = [p for p in want if not eas.does_asset_exist(p)]
    if not missing:
        return SKIN_ADVENTURER
    if len(missing) < len(want):
        _log(f"note: the adventurer skin is incomplete ({len(missing)} of "
             f"{len(want)} assets missing, first {missing[0]}) — wearing the "
             "mannequin. Run Scripts/asset_pipeline to build it.")
    return SKIN_QUINN


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
    anim_class = unreal.load_class(None, f"{skin.anim_bp}.{skin.anim_bp.rsplit('/', 1)[1]}_C")
    if not anim_class:
        raise RuntimeError(f"{skin.anim_bp} has no generated class — it did not compile")

    comp = None
    for handle, _name in _handles(bp):
        obj = _component_object(handle)
        if isinstance(obj, unreal.SkeletalMeshComponent):
            comp = obj
            break
    if comp is None:
        raise RuntimeError(f"{CHARACTER_BP_PATH} has no SkeletalMeshComponent")

    comp.set_editor_property("skeletal_mesh_asset", mesh_asset)
    comp.set_editor_property("anim_class", anim_class)
    comp.set_editor_property("relative_location", unreal.Vector(0.0, 0.0, skin.mesh_z))
    comp.set_editor_property("relative_rotation", _rot(yaw=skin.mesh_yaw))
    got = comp.get_editor_property("skeletal_mesh_asset")
    if got != mesh_asset or comp.get_editor_property("anim_class") != anim_class:
        raise RuntimeError(f"the skin did not stick: mesh={got}, "
                           f"anim={comp.get_editor_property('anim_class')}")
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_ThirdPersonCharacter failed to compile after the skin")
    eas.save_loaded_asset(bp)
    _log(f"player: wearing {mesh_asset.get_name()} animated by "
         f"{anim_class.get_name()}, weapon on {skin.grip}")
    return skin
