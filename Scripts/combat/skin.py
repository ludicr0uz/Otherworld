"""What the player wears: the PlayerSkin table (Quinn fallback, generated
adventurer) and wear_skin(), which puts it on BP_ThirdPersonCharacter.
"""

import dataclasses

import unreal

from asset_pipeline.mannequin_bind.paths import bound_asset_dir, bound_asset_name
from asset_pipeline.metahuman_paths import ABP_RETARGET, BODY_MESH, FACE_MESH
from asset_pipeline.player_body import PLAYER_NAME, PLAYER_RIG
from combat import metahuman_body
from combat.log import _log
from uebp.graph import BEL, _assets, _component_object, _handles, _rot
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
# (2026-10-03: no longer the whole story.  The three obstacles below are all
# about doing it IN THE EDITOR or AT THE RIGGER.  asset_pipeline/mannequin_bind
# does it before the import instead, host-side, on the cached GLB: the body is
# posed like the mannequin, its weights re-addressed to the mannequin's bones,
# and the file written on the mannequin's skeleton, so the importer has 89
# same-named bones to merge and nothing to transfer.  SKIN_BOUND below wears
# the result when player_body.PLAYER_RIG says "mannequin".  What follows is
# why the per-body skeleton was the answer until then, and it still describes
# SKIN_ADVENTURER.)
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
    # Standing idle, arms hanging: the body the hold poses (hold_pose.py) are
    # keyed on, since a carried item is not aimed.
    idle: str
    # The grip hand's four closing fingers, index first, each as its three
    # joints from the knuckle out. grip.fist_in_socket() finds where they curl
    # round, and the weapon's handle is put there. The thumb wraps the other
    # way and is not in; the index's outer joints rest on the trigger.
    grip_fingers: tuple
    # The grip hand's thumb, its three joints from the palm out. The rifle
    # ready pose lays it forward along a pistol grip's side; shotgun_pose.py
    # turns it over a straight stock's wrist...
    grip_thumb: tuple
    # ...and the other hand's, the one under the fore-end, which the rifle
    # pose stands up beside the barrel.
    support_thumb: tuple
    # That hand's four closing fingers, index first, as grip_fingers: the
    # rifle pose cups a deep handguard with them, and shotgun_pose.py closes
    # them on a pump.
    support_fingers: tuple
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
    # The head bone: hidden from the player's own view while the camera is on
    # a gun's sights, where the eye point is inside or beside the head
    # (weapon_component/head_hide.py). Its children go with it.
    head: str
    # Mesh component transform inside the actor. The template's own numbers;
    # they are a property of a 1.8 m humanoid standing in an 88 cm capsule
    # facing +X, not of the mannequin, which is why the Meshy skin reuses them.
    mesh_z: float = -89.0
    mesh_yaw: float = 270.0
    # The low stances' clips (stance_clips.py), retargeted from the Quaternius
    # Universal Animation Library: crouched still and walking, the crawl, and
    # the kneel over a body being searched. None where the rig has none, and
    # the stance is then posed procedurally (body_pose.py) and a search is made
    # standing: the mannequin, or an adventurer before import_quaternius.
    crouch_idle: str = None
    crouch_walk: str = None
    prone_crawl: str = None
    search_kneel: str = None
    # The overhand throw (weapon_component/throw_windup.py), from the same
    # library, played into the upper-body slot. None where the rig has none:
    # the item then leaves the hand on the click, with no clip.
    throw: str = None
    # True when what is DRAWN is a MetaHuman hung under this mesh, which is
    # then hidden (combat/metahuman_body.py). Everything above still names
    # the mannequin: it is the mannequin that is animated, gripped, hit and
    # ragdolled; the MetaHuman follows its pose through an IK retargeter.
    metahuman: bool = False

    @property
    def stance_clips(self):
        return self.crouch_idle is not None


SKIN_QUINN = PlayerSkin(
    mesh="/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple",
    anim_bp="/Game/Characters/Mannequins/Anims/Unarmed/ABP_Unarmed",
    grip="HandGrip_R",
    aim_rifle="/Game/Characters/Mannequins/Anims/Rifle/MF_Rifle_Idle_ADS",
    aim_pistol="/Game/Characters/Mannequins/Anims/Pistol/MF_Pistol_Idle_ADS",
    idle="/Game/Characters/Mannequins/Anims/Unarmed/MM_Idle",
    grip_fingers=tuple(tuple(f"{f}_{j:02d}_r" for j in (1, 2, 3))
                       for f in ("index", "middle", "ring", "pinky")),
    grip_thumb=tuple(f"thumb_{j:02d}_r" for j in (1, 2, 3)),
    support_thumb=tuple(f"thumb_{j:02d}_l" for j in (1, 2, 3)),
    support_fingers=tuple(tuple(f"{f}_{j:02d}_l" for j in (1, 2, 3))
                          for f in ("index", "middle", "ring", "pinky")),
    aim_bones=("spine_03", "spine_05"),
    pose_bones=dict(
        hips="pelvis", spine="spine_01", neck="neck_01",
        **{f"{role}_{s}": f"{bone}_{s}" for s in "lr" for role, bone in (
            ("clavicle", "clavicle"), ("upperarm", "upperarm"),
            ("forearm", "lowerarm"), ("hand", "hand"), ("thigh", "thigh"),
            ("calf", "calf"), ("foot", "foot"))}),
    punch="/Game/Characters/Mannequins/Anims/Unarmed/Attack/MM_Attack_01",
    head="head",
)

# Built by Scripts/asset_pipeline: fetch_monsters.py -> import_characters.py ->
# build_retarget.py. Every path here is under /Game/Sourced, which is
# git-ignored, so a checkout that has never run the pipeline has none of it and
# falls back to the mannequin above -- the same bargain build_npc_blueprints.py
# strikes, and for the same reason: a player who looks wrong is a far better
# failure than a build that stops.
#
# Which generated body it is, is asset_pipeline/player_body.py's PLAYER_BODY,
# the one setting: every path below follows it.
ADVENTURER = PLAYER_NAME
UAL_ANIMS = f"/Game/Sourced/Quaternius/UAL/{ADVENTURER}"
SKIN_ADVENTURER = PlayerSkin(
    mesh=f"/Game/Sourced/Characters/SKM_{ADVENTURER}/SKM_{ADVENTURER}",
    anim_bp=f"/Game/Sourced/Characters/Anims/{ADVENTURER}/A_{ADVENTURER}_ABP_Unarmed",
    grip="RightHand",
    aim_rifle=f"/Game/Sourced/Characters/Anims/{ADVENTURER}/"
              f"A_{ADVENTURER}_MF_Rifle_Idle_ADS",
    aim_pistol=f"/Game/Sourced/Characters/Anims/{ADVENTURER}/"
               f"A_{ADVENTURER}_MF_Pistol_Idle_ADS",
    idle=f"/Game/Sourced/Characters/Anims/{ADVENTURER}/A_{ADVENTURER}_MM_Idle",
    # asset_pipeline/finger_rig.py adds these, named the Mixamo way.
    grip_fingers=tuple(tuple(f"RightHand{f}{j}" for j in (1, 2, 3))
                       for f in ("Index", "Middle", "Ring", "Pinky")),
    grip_thumb=tuple(f"RightHandThumb{j}" for j in (1, 2, 3)),
    support_thumb=tuple(f"LeftHandThumb{j}" for j in (1, 2, 3)),
    support_fingers=tuple(tuple(f"LeftHand{f}{j}" for j in (1, 2, 3))
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
    head="Head",
    # asset_pipeline/import_quaternius.py (quaternius_paths.CROUCH_IDLE, ...):
    # the UAL pack has no crawl, and its face-down swim is what crawls.
    crouch_idle=f"{UAL_ANIMS}/A_{ADVENTURER}_UAL1_Crouch_Idle_Loop",
    crouch_walk=f"{UAL_ANIMS}/A_{ADVENTURER}_UAL1_Crouch_Fwd_Loop",
    prone_crawl=f"{UAL_ANIMS}/A_{ADVENTURER}_UAL1_Swim_Fwd_Loop",
    search_kneel=f"{UAL_ANIMS}/A_{ADVENTURER}_UAL1_Fixing_Kneeling",
    throw=f"{UAL_ANIMS}/A_{ADVENTURER}_UAL2_OverhandThrow",
)


# The same generated body bound to the mannequin's skeleton
# (asset_pipeline/bind_to_mannequin.py, import_bound.py).  Everything but the
# mesh is Quinn's, because on this skeleton everything but the mesh IS the
# mannequin's: its anim blueprint, its ready poses, its grip socket, its bone
# names.  The stance and throw clips are the Quaternius library retargeted
# once onto the mannequin (asset_pipeline/retarget_ual_to_mannequin.py), which
# serve every bound body; without them this skin crouches procedurally and
# throws without a clip, as the mannequin does.
BOUND_UAL_ANIMS = "/Game/Sourced/Quaternius/UAL/Mannequin"
SKIN_BOUND = dataclasses.replace(
    SKIN_QUINN,
    mesh=f"{bound_asset_dir(PLAYER_NAME)}/{bound_asset_name(PLAYER_NAME)}",
    crouch_idle=f"{BOUND_UAL_ANIMS}/A_Mannequin_UAL1_Crouch_Idle_Loop",
    crouch_walk=f"{BOUND_UAL_ANIMS}/A_Mannequin_UAL1_Crouch_Fwd_Loop",
    prone_crawl=f"{BOUND_UAL_ANIMS}/A_Mannequin_UAL1_Swim_Fwd_Loop",
    search_kneel=f"{BOUND_UAL_ANIMS}/A_Mannequin_UAL1_Fixing_Kneeling",
    throw=f"{BOUND_UAL_ANIMS}/A_Mannequin_UAL2_OverhandThrow")

# Epic's sample MetaHuman (asset_pipeline/import_metahuman.py), drawn under
# a hidden mannequin that runs everything (combat/metahuman_body.py). The
# mannequin is Manny, not Quinn: the retargeter reads the source pose off
# whatever mesh the mannequin component wears, and a male MetaHuman body
# retargets better from the male mannequin's proportions. Same skeleton, same
# socket, same clips as SKIN_BOUND.
SKIN_METAHUMAN = dataclasses.replace(
    SKIN_BOUND,
    mesh="/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple",
    metahuman=True)


# Every skin there is, most specific first: what a running game, which has no
# asset subsystem to resolve player_skin() with, matches the worn mesh against.
SKINS = (SKIN_METAHUMAN, SKIN_BOUND, SKIN_ADVENTURER, SKIN_QUINN)


def skin_of_mesh(worn):
    """The skin whose mesh is ``worn`` (a /Game path without the .Name), or
    None. For probes: the mesh on the Character's own component."""
    worn = str(worn).split(".")[0]
    return next((s for s in SKINS if s.mesh == worn), None)


def _without_missing_clips(skin, eas, who, builder):
    """``skin`` less the optional clips that are not built: the throw, and
    the four stance clips (all of them or none)."""
    if not eas.does_asset_exist(skin.throw):
        _log(f"note: no Quaternius throw clip yet — {who} throws without one. "
             f"Run asset_pipeline/{builder}.")
        skin = dataclasses.replace(skin, throw=None)
    stances = (skin.crouch_idle, skin.crouch_walk, skin.prone_crawl, skin.search_kneel)
    if all(eas.does_asset_exist(p) for p in stances):
        return skin
    _log(f"note: no Quaternius stance clips yet — {who} crouches and lies down "
         f"procedurally. Run asset_pipeline/{builder}.")
    return dataclasses.replace(skin, crouch_idle=None, crouch_walk=None,
                               prone_crawl=None, search_kneel=None)


def player_skin():
    """The adventurer if the pipeline has produced all of it, else the mannequin.

    All of its assets or none: a skin resolved piecemeal is the failure that
    cannot be read off a log -- the adventurer's mesh wearing the mannequin's
    anim BP compiles, runs, and stands in the reference pose forever.
    """
    eas = _assets()
    if PLAYER_RIG == "metahuman":
        if all(eas.does_asset_exist(p) for p in (BODY_MESH, FACE_MESH, ABP_RETARGET)):
            return _without_missing_clips(SKIN_METAHUMAN, eas, "the MetaHuman",
                                          "retarget_ual_to_mannequin.py")
        _log(f"note: PLAYER_RIG is \"metahuman\" and {BODY_MESH} or {ABP_RETARGET} "
             "is not built — wearing the bound body. Run "
             "asset_pipeline/import_metahuman.py, then build_metahuman_retarget.py.")
    if PLAYER_RIG in ("mannequin", "metahuman"):
        if eas.does_asset_exist(SKIN_BOUND.mesh):
            return _without_missing_clips(SKIN_BOUND, eas, "the bound body",
                                          "retarget_ual_to_mannequin.py")
        _log(f"note: PLAYER_RIG is \"mannequin\" and {SKIN_BOUND.mesh} is not "
             "imported — wearing the body on its own skeleton. Run "
             "asset_pipeline/bind_to_mannequin.py, then import_bound.py.")
    want = (SKIN_ADVENTURER.mesh, SKIN_ADVENTURER.anim_bp,
            SKIN_ADVENTURER.aim_rifle, SKIN_ADVENTURER.aim_pistol,
            SKIN_ADVENTURER.idle, SKIN_ADVENTURER.punch)
    missing = [p for p in want if not eas.does_asset_exist(p)]
    if not missing:
        return _without_missing_clips(SKIN_ADVENTURER, eas, "the adventurer",
                                      "import_quaternius.py")
    if len(missing) < len(want):
        _log(f"note: the adventurer skin is incomplete ({len(missing)} of "
             f"{len(want)} assets missing, first {missing[0]}) — wearing the "
             "mannequin. Run Scripts/asset_pipeline to build it.")
    return SKIN_QUINN


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
    anim_class = unreal.load_class(None, f"{skin.anim_bp}.{skin.anim_bp.rsplit('/', 1)[1]}_C")
    if not anim_class:
        raise RuntimeError(f"{skin.anim_bp} has no generated class — it did not compile")

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
        metahuman_body.install(bp, mesh_handle)
    else:
        metahuman_body.remove(bp)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_ThirdPersonCharacter failed to compile after the skin")
    eas.save_loaded_asset(bp)
    _log(f"player: wearing {mesh_asset.get_name()} animated by "
         f"{anim_class.get_name()}, weapon on {skin.grip}"
         + (" -- drawn as the MetaHuman" if skin.metahuman else ""))
    return skin
