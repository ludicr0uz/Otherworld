"""BP_ForestWanderer (the body) and one child Blueprint per creature."""

import unreal

from forest_generator.npc_placement import (
    NPC_ANIM_BP, NPC_ANIM_BP_FALLBACK, NPC_BASE_MESH, NPC_BASE_MESH_FALLBACK,
    NPC_MELEE_MONTAGE_FALLBACK, NPC_RUN_SPEED_CMS,
    NPC_RUN_SPEED_CMS as _NPC_RUN_SPEED_CMS,
)
from npc.paths import (
    MESH_RELATIVE_YAW_DEG, MESH_RELATIVE_Z_CM, NPC_BP_PATH,
)
from npc.graph import (
    _asset_sub, BEL, _create_blueprint, _log, _mesh_object, _resolve,
    _try_set,
)
from npc.controller import build_ai_controller_blueprint


# ─── The character ──────────────────────────────────────────────────────────

def build_npc_blueprint(ai_bp):
    """Create BP_ForestWanderer and point it at the AI controller."""
    bp = _create_blueprint(NPC_BP_PATH, unreal.Character)
    eas = _asset_sub()

    generated = BEL.generated_class(bp)
    cdo = unreal.get_default_object(generated)

    # Possession: the controller must take over wherever the NPC comes from.
    cdo.set_editor_property("ai_controller_class", BEL.generated_class(ai_bp))
    cdo.set_editor_property(
        "auto_possess_ai", unreal.AutoPossessAI.PLACED_IN_WORLD_OR_SPAWNED)

    # Body — the default creature. Each variant child overrides just this.
    mesh_comp = cdo.get_editor_property("mesh")
    mesh_path = _resolve(NPC_BASE_MESH, NPC_BASE_MESH_FALLBACK, "base mesh")
    skel = eas.load_asset(mesh_path)
    if skel:
        mesh_comp.set_editor_property("skeletal_mesh_asset", skel)
    else:
        unreal.log_error(f"[NPC] missing skeletal mesh {mesh_path}")

    # The wanderer wears the mesh's own materials. This array is written every
    # build, empty included, because this builder edits the Blueprint in place:
    # anything it does not write survives from the previous build. An abandoned
    # re-skin experiment left two material instances here that no code
    # referenced any more, and no amount of rebuilding cleared them -- the
    # builder simply never mentioned the array. Silence is not a default.
    previous = list(mesh_comp.get_editor_property("override_materials") or [])
    mesh_comp.set_editor_property("override_materials", [])
    if previous:
        names = ", ".join(m.get_name() if m else "None" for m in previous)
        unreal.log_warning(f"[NPC] cleared {len(previous)} material override(s): {names}")
    # ── Animation ────────────────────────────────────────────────────────────
    # ABP_Unarmed's locomotion gates on
    #   ShouldMove = (GroundSpeed > threshold) AND (GetCurrentAcceleration() != 0)
    # The acceleration half of that is supplied by use_acceleration_for_paths
    # below -- see the note there; it is the load-bearing setting for whether a
    # walk cycle plays at all, not anything in this block.
    #
    # animation_mode is already ANIMATION_BLUEPRINT once anim_class is set; it
    # is pinned here only because this builder updates blueprints in place and
    # should not inherit a stale AnimationSingleNode/AnimationCustomMode value.
    # _resolve hands back an object path; a Blueprint's runtime class is that
    # plus _C, which is what a component's anim_class actually wants.
    anim_bp = _resolve(NPC_ANIM_BP, NPC_ANIM_BP_FALLBACK, "anim blueprint")
    anim_class = unreal.load_class(None, f"{anim_bp}_C")
    if anim_class:
        _try_set(mesh_comp, "animation_mode",
                 unreal.AnimationMode.ANIMATION_BLUEPRINT)
        mesh_comp.set_editor_property("anim_class", anim_class)
    else:
        unreal.log_error(f"[NPC] missing anim blueprint {anim_bp}_C")

    # Keep the pose updating even when the NPC is off-screen, so it is mid-stride
    # when the player turns to look rather than snapping into a pose.
    _try_set(mesh_comp, "visibility_based_anim_tick_option",
             unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)

    # Stock Character capsule is 88 cm half-height; drop the mesh to its feet.
    mesh_comp.set_editor_property(
        "relative_location", unreal.Vector(0, 0, MESH_RELATIVE_Z_CM))
    mesh_comp.set_editor_property(
        "relative_rotation",
        unreal.Rotator(pitch=0.0, yaw=MESH_RELATIVE_YAW_DEG, roll=0.0))

    movement = cdo.get_editor_property("character_movement")
    movement.set_editor_property("max_walk_speed", NPC_RUN_SPEED_CMS)
    # Turn in place smoothly instead of snapping to each new path segment.
    movement.set_editor_property(
        "rotation_rate", unreal.Rotator(pitch=0.0, yaw=180.0, roll=0.0))
    movement.set_editor_property("orient_rotation_to_movement", True)

    # MUST be True, and pinned explicitly rather than left to the engine default:
    # this builder updates blueprints IN PLACE, so any property it does not set
    # keeps whatever the asset already had -- deleting a line does not revert it.
    #
    # With it False, UCharacterMovementComponent::ApplyRequestedMove takes its
    # "just set velocity directly" branch and leaves Acceleration at exactly
    # zero every frame.  ABP_Unarmed gates locomotion on
    #   ShouldMove = GroundSpeed > threshold AND GetCurrentAcceleration() != 0
    # so the state machine stays in Idle and the NPC slides along in its idle
    # pose -- which is precisely the bug this was once (wrongly) blamed for.
    # With it True the branch guard is
    #   CurrentSpeedSq < Square(RequestedSpeed * 1.01f)
    # which still holds at cruising speed, so acceleration stays non-zero.
    #
    # A note here used to claim True was measured at 0.0 m over 91 s versus
    # 51.7 m with False.  That measurement predates the navmesh fix (section 7
    # of generate_forest_level.py): the level had zero nav tiles, so every
    # MoveTo failed and the NPC covered 0 m regardless of this flag.
    nav_props = movement.get_editor_property("nav_movement_properties")
    nav_props.set_editor_property("use_acceleration_for_paths", True)
    movement.set_editor_property("nav_movement_properties", nav_props)
    # A stock Character has use_controller_rotation_yaw = True, which forces the
    # pawn's yaw to the controller's every frame and fights the line above.
    # The third-person template turns it off for the same reason.
    cdo.set_editor_property("use_controller_rotation_yaw", False)

    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_ForestWanderer failed to compile")
    eas.save_loaded_asset(bp)
    _log(f"built {NPC_BP_PATH} (run speed {NPC_RUN_SPEED_CMS} cm/s)")
    return bp


# ─── Creature variants ──────────────────────────────────────────────────────

def build_variant_blueprint(base_bp, variant):
    """A child of BP_ForestWanderer wearing one creature.

    Child Blueprints rather than a mesh swap at spawn time, and rather than one
    builder per creature.  Inheritance is what keeps the SHARED behaviour from
    drifting: the capsule, the melee numbers, the rotation rate and the whole
    chase loop are defined once on the parent and are not repeated here.

    Two stats are now per creature -- health and run speed, see
    WENDIGO_HEALTH_MULTIPLIER in npc_placement.py -- and they are both read
    from the variant record rather than written out here, so "a wendigo has
    three times the health" is stated in one place and applied in another.
    Everything else this function sets is an asset reference.

    It sets three of them rather than one, because a creature is its own
    skeleton: the mesh, the anim Blueprint retargeted against THAT skeleton,
    and an AI controller holding THAT skeleton's attack clip.  The melee
    numbers inside those controllers still come from one place -- they are
    generated by build_ai_controller_blueprint from the same constants.

    Adding a creature is therefore an entry in NPC_VARIANTS and nothing else.
    """
    eas = _asset_sub()
    parent_class = BEL.generated_class(base_bp)
    if not parent_class:
        raise RuntimeError("base NPC blueprint has no generated class")

    bp = _create_blueprint(variant.blueprint, parent_class)
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    mesh_comp = cdo.get_editor_property("mesh")

    mesh = eas.load_asset(_mesh_object(variant.mesh))
    if mesh:
        mesh_comp.set_editor_property("skeletal_mesh_asset", mesh)
    else:
        # Not fatal: the child still inherits the parent's mesh, so the NPC
        # spawns and behaves correctly, it just wears the wrong creature.
        unreal.log_warning(
            f"[NPC] {variant.key}: {variant.mesh} is missing -- this variant "
            "will wear the base mesh")

    # The creature carries its own material instance (MI_Zombie01 and friends,
    # built by build_creature_materials.py), so an override here could only
    # ever be wrong.  Written explicitly rather than left alone because this
    # builder edits in place: an override set by a previous build survives
    # until something states otherwise.
    mesh_comp.set_editor_property("override_materials", [])

    # The anim BP is skeleton-bound, so the parent's cannot drive this mesh:
    # assigning a mismatched one leaves the creature in its bind pose, still
    # sliding around on its capsule, with nothing logged.
    anim_bp = _resolve(variant.anim_bp, NPC_ANIM_BP_FALLBACK,
                       f"{variant.key} anim blueprint")
    anim_class = unreal.load_class(None, f"{anim_bp}_C")
    if not anim_class:
        raise RuntimeError(f"[NPC] {variant.key}: {anim_bp} has no generated class")
    mesh_comp.set_editor_property("animation_mode",
                                  unreal.AnimationMode.ANIMATION_BLUEPRINT)
    mesh_comp.set_editor_property("anim_class", anim_class)

    # How fast this creature runs. The one stat that IS set on the pawn,
    # because MaxWalkSpeed lives on CharacterMovement -- a native subobject,
    # which a CDO does expose -- rather than on an added component. Health
    # cannot be set here for exactly that reason; see _author_stats_and_voice.
    #
    # The animation rate is scaled by the same factor at spawn time (see
    # generate_forest_level.py), not here, because it multiplies with the
    # per-instance gait variance and there is one place that composes the two.
    speed = _NPC_RUN_SPEED_CMS * variant.speed_scale
    move = cdo.get_editor_property("character_movement")
    move.set_editor_property("max_walk_speed", speed)
    got = move.get_editor_property("max_walk_speed")
    if abs(got - speed) > 1e-3:
        raise RuntimeError(
            f"{variant.key}: MaxWalkSpeed stayed at {got}, wanted {speed}")

    # Its own controller, because the attack clip inside it belongs to this
    # creature's skeleton and will not play on any other -- and because its
    # health and its voice are per creature too.
    ai_bp = build_ai_controller_blueprint(
        rebuild=True, path=variant.ai_blueprint,
        melee_anim=_resolve(variant.melee, NPC_MELEE_MONTAGE_FALLBACK,
                            f"{variant.key} melee clip"),
        voices=variant.voices, reactions=variant.reactions, key=variant.key)
    cdo.set_editor_property("ai_controller_class", BEL.generated_class(ai_bp))

    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{variant.blueprint} failed to compile")
    eas.save_loaded_asset(bp)
    _log(f"built {variant.blueprint} "
         f"({mesh.get_name() if mesh else 'inherited mesh'}, "
         f"{anim_class.get_name()}, {ai_bp.get_name()}, "
         f"{variant.health:.0f} HP, {speed:.0f} cm/s)")
    return bp
