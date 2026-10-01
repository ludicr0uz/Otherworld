"""build_weapon_component(): declares BP_WeaponComponent's variables, sets
its defaults and authors BeginPlay and Tick from the sibling modules.
"""

import unreal

from combat.carry_tuning import LOWERED_VAR, POSE_LOWERED_VAR, RAISE_FORCED_VAR
from combat.game_state import DEBUG_MODE_VAR
from combat.graph import (
    BEL, BGE, _apply_defaults, _assets, _create_blueprint, _declare, _events,
    _float_type, _key, _log, _must_load, _post_physics_tick, _struct_type,
)
from combat.hit_zones import HIT_BONE_VAR, HIT_POINT_VAR
from combat.paths import (
    CHARACTER_BP_PATH, HEALTH_BP_PATH, ITEM_BP_PATH, THROW_ARC_BP_PATH,
    WEAPON_COMP_BP_PATH,
)
from combat.skin import player_skin
from combat.sway_tuning import SWAY_VARS
from combat.tuning import BIND_VARS, COMBAT
from combat.weapon_component.accuracy import ACCURACY_OUT_VARS
from combat.weapon_component.consume import TRIGGER_SPENT
from combat.weapon_component.firing import SHOT_DIRECTION_VAR
from combat.weapon_component.inventory import (
    STARTER_CLASS_VARS, _author_wc_begin_play,
)
from combat.weapon_component.knife import (
    KNIFE_ANIM_VAR, KNIFE_DUE_VAR, KNIFE_PENDING_VAR, KNIFE_QUEUED_VAR,
    NEXT_KNIFE_VAR,
)
from combat.weapon_component.pickup import (
    PICKUP_FORCED_VAR, PICK_BEST_VAR, PICK_GAP_VAR, PICK_NO_GAP,
)
from combat.weapon_component.pose_weights import HELD_TWO_HANDED, SEARCHING_VAR
from combat.weapon_component.punch import (
    NEXT_PUNCH_VAR, PUNCH_ANIM_VAR, PUNCH_DUE_VAR, PUNCH_PENDING_VAR,
    PUNCH_QUEUED_VAR,
)
from combat.weapon_component.sprint import SPRINT_SPENT_VAR
from combat.weapon_component.stance import STANCE_VAR, STAND
from combat.weapon_component.surface_impact import IMPACT_CLASS_VAR
from combat.weapon_component.throw import (
    THROWN_VAR, THROW_AIMING_VAR, THROW_ARC_CLASS_VAR, THROW_ARC_VAR,
    THROW_CLICK_FORCED_VAR, THROW_FORCED_VAR, THROW_LAST_VAR, THROW_START_VAR,
    THROW_TIME_VAR, THROW_VELOCITY_VAR,
)
from combat.weapon_component.dead import OWNER_DEAD_VAR
from combat.weapon_component.tick import FIRE_FORCED_VAR, _author_wc_tick


def build_weapon_component(item_bp, shotgun_bp, pistol_bp, knife_bp, axe_bp,
                           knife_clip, blood_bp, impact_bp, throw_arc_bp, rebuild=True):
    # Cast nodes only appear in the palette for classes that are already loaded,
    # and this graph casts to all three. Without these loads
    # create_node_from_name returns None and the failure reads as a typo in the
    # node name rather than as a missing asset.
    for path in (CHARACTER_BP_PATH, ITEM_BP_PATH, HEALTH_BP_PATH, THROW_ARC_BP_PATH):
        if not _assets().load_asset(path):
            raise RuntimeError(f"could not load {path} for its cast node")

    bp = _create_blueprint(WEAPON_COMP_BP_PATH, unreal.ActorComponent)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    tick, begin = _events(ed, rebuild)

    item_class = BEL.generated_class(item_bp)
    _declare(ed, "Inventory",
             BEL.get_array_type(BEL.get_object_reference_type(item_class)))
    _declare(ed, "Held", BEL.get_object_reference_type(item_class))
    _declare(ed, "EquippedIndex", BEL.get_basic_type_by_name("int"))
    _declare(ed, "NeedsRefresh", BEL.get_basic_type_by_name("bool"))
    _declare(ed, "OwnerMesh", BEL.get_object_reference_type(
        unreal.SkeletalMeshComponent.static_class()))
    # Where this frame's shot lands, and whether there is anything to draw a
    # reticle on. The HUD reads all three; nothing else writes them.
    _declare(ed, "AimPoint", _struct_type(unreal.Vector.static_struct()))
    _declare(ed, "AimValid", BEL.get_basic_type_by_name("bool"))
    _declare(ed, "AimBlocked", BEL.get_basic_type_by_name("bool"))
    # Sprint. The HUD reads Stamina/MaxStamina for the bar under the player's
    # HP bar; BaseSpeed is cached off the character at BeginPlay, never a
    # literal. Sprinting is what the fire gate refuses on.
    for name in ("Stamina", "MaxStamina", "BaseSpeed"):
        _declare(ed, name, _float_type())
    _declare(ed, "Sprinting", BEL.get_basic_type_by_name("bool"))
    _declare(ed, SPRINT_SPENT_VAR, BEL.get_basic_type_by_name("bool"))
    # The guard (block.py). Read by the fire gate, and by every wanderer's
    # swing, which also writes Stamina here when the guard takes the hit.
    _declare(ed, "Blocking", BEL.get_basic_type_by_name("bool"))
    # Standing, crouched or prone (stance.py). Written only by the stance
    # block; the movement component and the footsteps are told from it.
    _declare(ed, STANCE_VAR, BEL.get_basic_type_by_name("int"))
    # Held.TwoHanded, or false with nothing held: copied behind an IsValid
    # Branch once a frame so the guard pose never reads a null Held.
    _declare(ed, HELD_TWO_HANDED, BEL.get_basic_type_by_name("bool"))
    # A body is being searched: the HUD writes it while its loot window is
    # open, and the pose weights kneel the body from it.
    _declare(ed, SEARCHING_VAR, BEL.get_basic_type_by_name("bool"))
    # Aiming down the sights. BaseFOV is cached off the camera at BeginPlay for
    # the same reason BaseSpeed is cached off the movement component; CurrentFOV
    # is stored because FInterpTo's input is its own previous output, and
    # TargetFOV because the two arms of the zoom branch must write one value
    # that one interpolation then reads.
    for name in ("BaseFOV", "CurrentFOV", "TargetFOV"):
        _declare(ed, name, _float_type())
    # Aiming is either aim key (the cone and the recoil read it); SightAiming
    # is the down-the-sights key alone (the camera and the scope read it).
    # AimZoom is the zoom being aimed at, stored so the walk slowdown's
    # ease-out divides by the zoom being let go of; SightBlend is how far the
    # camera has travelled from the boom to the sight (weapon_component/sights).
    _declare(ed, "Aiming", BEL.get_basic_type_by_name("bool"))
    _declare(ed, "SightAiming", BEL.get_basic_type_by_name("bool"))
    _declare(ed, "AimZoom", _float_type())
    _declare(ed, "SightBlend", _float_type())
    # The sight sway (sway.py): its clock, and how far it has turned the view.
    for name in SWAY_VARS:
        _declare(ed, name, _float_type())
    # The polled keys, as variables rather than as pin literals. Nothing
    # in this component loads them: the HUD pushes the player's binds in every
    # DrawHUD frame (see graphics_menu/settings_page._author_push_settings), which is
    # what keeps the component free of any cast to the HUD and of any knowledge
    # that a save file exists. The CDO defaults below are therefore also the
    # standalone fallback -- a weapon component on an actor with no HUD in front
    # of it still plays with the keys this file documents.
    for name, _default in BIND_VARS:
        _declare(ed, name, _struct_type(unreal.Key.static_struct()))
    # Mouse sensitivity, and the two controller scales it multiplies. Both
    # bases are cached off the PlayerController at BeginPlay -- BasePitchScale
    # especially, because the engine ships it negative and a literal would
    # invert the look. See the ADS block for what the zoom does to them.
    # ScopeSensitivity is the scope's extra multiplier on top of the zoom's
    # own slowdown -- the settings screen's second row, pushed like the first.
    for name in ("MouseSensitivity", "ScopeSensitivity", "BaseYawScale",
                 "BasePitchScale"):
        _declare(ed, name, _float_type())
    # What the ready pose should reflect (carry.py writes it) and what it
    # currently does. The pair is what makes the pose edge-triggered; see
    # ready_pose.py.
    for name in (LOWERED_VAR, POSE_LOWERED_VAR, RAISE_FORCED_VAR):
        _declare(ed, name, BEL.get_basic_type_by_name("bool"))
    # Recoil. RecoilDebt/RecoilYawDebt are what has been kicked and not yet
    # given back, recovered toward zero every frame; RecoilYawKick holds the
    # one draw of the sideways component for the frame it is fired on, because
    # RandomFloatInRange is pure and a second read would be a second number.
    for name in ("RecoilDebt", "RecoilYawDebt", "RecoilYawKick"):
        _declare(ed, name, _float_type())
    # Accuracy (accuracy.py): the cloud, the kick's scale and the reticle's
    # size, written once a frame. ShotDirection is the one draw of a shot's
    # direction inside the cloud, stored because the cone is pure and every
    # pellet of the shotgun must share it.
    for name in ACCURACY_OUT_VARS:
        _declare(ed, name, _float_type())
    _declare(ed, SHOT_DIRECTION_VAR, _struct_type(unreal.Vector.static_struct()))
    # How many rounds this reload moves, computed once and read back three
    # times. See _author_reload for why it cannot just be recomputed.
    _declare(ed, "ReloadTake", BEL.get_basic_type_by_name("int"))
    # The fire press that ate an item, until it is released; see consume.py.
    _declare(ed, TRIGGER_SPENT, BEL.get_basic_type_by_name("bool"))
    # The dead gate's answer (dead.py), and a probe's stand-in for the fire key.
    for name in (OWNER_DEAD_VAR, FIRE_FORCED_VAR):
        _declare(ed, name, BEL.get_basic_type_by_name("bool"))
    # The GameMode's DebugMode, cached at the moment of firing so the pellet
    # loop can branch on a plain bool instead of casting eight times.
    _declare(ed, DEBUG_MODE_VAR, BEL.get_basic_type_by_name("bool"))
    _declare(ed, HIT_BONE_VAR, BEL.get_basic_type_by_name("name"))
    _declare(ed, HIT_POINT_VAR, _struct_type(unreal.Vector.static_struct()))
    # Typed as "class of BP_WeaponItem", not "class of Actor": SpawnActor's
    # return pin takes its type from its Class pin, and an Actor-typed return
    # cannot be added to an array of BP_WeaponItem.
    for name in (*STARTER_CLASS_VARS, "ItemClass"):
        _declare(ed, name, BEL.get_class_reference_type(item_class))
    for name in ("BloodClass", IMPACT_CLASS_VAR):
        _declare(ed, name,
                 BEL.get_class_reference_type(unreal.Actor.static_class()))
    # The empty-handed punch (punch.py): its clip on the worn rig, the press
    # queued for the swing, the cooldown, and the blow still to land.
    _declare(ed, PUNCH_ANIM_VAR, BEL.get_object_reference_type(
        unreal.AnimSequenceBase.static_class()))
    for name in (PUNCH_QUEUED_VAR, PUNCH_PENDING_VAR):
        _declare(ed, name, BEL.get_basic_type_by_name("bool"))
    for name in (NEXT_PUNCH_VAR, PUNCH_DUE_VAR):
        _declare(ed, name, _float_type())
    # The knife's slash (knife.py): the same four, on the knife's own clip.
    _declare(ed, KNIFE_ANIM_VAR, BEL.get_object_reference_type(
        unreal.AnimSequenceBase.static_class()))
    for name in (KNIFE_QUEUED_VAR, KNIFE_PENDING_VAR):
        _declare(ed, name, BEL.get_basic_type_by_name("bool"))
    for name in (NEXT_KNIFE_VAR, KNIFE_DUE_VAR):
        _declare(ed, name, _float_type())
    # The pick-up (pickup.py): the candidate nearest the reticle's point so
    # far, its distance to that point, and the probe's stand-in for the key.
    _declare(ed, PICK_BEST_VAR, BEL.get_object_reference_type(item_class))
    _declare(ed, PICK_GAP_VAR, _float_type())
    _declare(ed, PICKUP_FORCED_VAR, BEL.get_basic_type_by_name("bool"))
    # The throw (throw.py): the aim and the launch it stores, the item in the
    # air, and the arc actor it draws on.
    for name in (THROW_AIMING_VAR, THROW_FORCED_VAR, THROW_CLICK_FORCED_VAR):
        _declare(ed, name, BEL.get_basic_type_by_name("bool"))
    _declare(ed, THROWN_VAR, BEL.get_object_reference_type(item_class))
    for name in (THROW_START_VAR, THROW_VELOCITY_VAR, THROW_LAST_VAR):
        _declare(ed, name, _struct_type(unreal.Vector.static_struct()))
    _declare(ed, THROW_TIME_VAR, _float_type())
    arc_class = BEL.generated_class(throw_arc_bp)
    _declare(ed, THROW_ARC_VAR, BEL.get_object_reference_type(arc_class))
    _declare(ed, THROW_ARC_CLASS_VAR, BEL.get_class_reference_type(arc_class))

    _author_wc_begin_play(ed, begin)
    _author_wc_tick(ed, tick)

    _post_physics_tick(bp)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_WeaponComponent failed to compile")
    _apply_defaults(bp, {
        "EquippedIndex": 0,
        "NeedsRefresh": True,
        "Stamina": COMBAT.max_stamina,
        "MaxStamina": COMBAT.max_stamina,
        # Overwritten on the first frame of BeginPlay; this is only what the
        # bar would divide by if that somehow never ran.
        "BaseSpeed": 500.0,
        "Sprinting": False,
        SPRINT_SPENT_VAR: False,
        "Blocking": False,
        STANCE_VAR: STAND,
        HELD_TWO_HANDED: False,
        SEARCHING_VAR: False,
        # 1.0 is "exactly what the controller already does", because the two
        # base scales this multiplies are the controller's own. A player who
        # never opens the settings screen therefore gets the stock feel.
        "MouseSensitivity": COMBAT.mouse_sensitivity_default,
        "ScopeSensitivity": COMBAT.ads_scope_sens_scale,
        "SightAiming": False,
        # A divisor (AimZoom - 1) from the first frame, so never 1.0.
        "AimZoom": COMBAT.shoulder_zoom,
        "SightBlend": 0.0,
        **{name: 0.0 for name in SWAY_VARS},
        **{name: _key(k) for name, k in BIND_VARS},
        # Both overwritten on the first frame of BeginPlay. Seeded with the
        # engine's own defaults, signs included, so that a BeginPlay that
        # somehow never ran leaves the look working rather than dead.
        "BaseYawScale": 2.5,
        "BasePitchScale": -2.5,
        # The two match, so the first frame sees no edge and does not
        # re-equip for nothing.
        LOWERED_VAR: False,
        POSE_LOWERED_VAR: False,
        RAISE_FORCED_VAR: False,
        "ReloadTake": 0,
        TRIGGER_SPENT: False,
        OWNER_DEAD_VAR: False,
        FIRE_FORCED_VAR: False,
        "RecoilDebt": 0.0,
        "RecoilYawDebt": 0.0,
        "RecoilYawKick": 0.0,
        **{name: 0.0 for name in ACCURACY_OUT_VARS},
        DEBUG_MODE_VAR: False,
        "ShotgunClass": BEL.generated_class(shotgun_bp),
        "PistolClass": BEL.generated_class(pistol_bp),
        "KnifeClass": BEL.generated_class(knife_bp),
        "AxeClass": BEL.generated_class(axe_bp),
        "ItemClass": item_class,
        "BloodClass": BEL.generated_class(blood_bp),
        IMPACT_CLASS_VAR: BEL.generated_class(impact_bp),
        PUNCH_ANIM_VAR: _must_load(player_skin().punch),
        PUNCH_QUEUED_VAR: False,
        PUNCH_PENDING_VAR: False,
        NEXT_PUNCH_VAR: 0.0,
        PUNCH_DUE_VAR: 0.0,
        KNIFE_ANIM_VAR: knife_clip,
        KNIFE_QUEUED_VAR: False,
        KNIFE_PENDING_VAR: False,
        NEXT_KNIFE_VAR: 0.0,
        KNIFE_DUE_VAR: 0.0,
        PICK_GAP_VAR: PICK_NO_GAP,
        PICKUP_FORCED_VAR: False,
        THROW_AIMING_VAR: False,
        THROW_FORCED_VAR: False,
        THROW_CLICK_FORCED_VAR: False,
        THROW_TIME_VAR: 0.0,
        THROW_ARC_CLASS_VAR: arc_class,
    })
    _log(f"built {WEAPON_COMP_BP_PATH}")
    return bp
