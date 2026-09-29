"""build_weapon_component(): declares BP_WeaponComponent's variables, sets
its defaults and authors BeginPlay and Tick from the sibling modules.
"""

import unreal

from combat.game_state import DEBUG_MODE_VAR
from combat.graph import (
    BEL, BGE, _apply_defaults, _assets, _create_blueprint, _declare, _events,
    _float_type, _key, _log, _post_physics_tick, _struct_type,
)
from combat.hit_zones import HIT_BONE_VAR
from combat.paths import (
    CHARACTER_BP_PATH, HEALTH_BP_PATH, ITEM_BP_PATH, WEAPON_COMP_BP_PATH,
)
from combat.tuning import BIND_VARS, COMBAT
from combat.weapon_component.consume import TRIGGER_SPENT
from combat.weapon_component.inventory import _author_wc_begin_play
from combat.weapon_component.tick import _author_wc_tick


def build_weapon_component(item_bp, shotgun_bp, pistol_bp, blood_bp, rebuild=True):
    # Cast nodes only appear in the palette for classes that are already loaded,
    # and this graph casts to all three. Without these loads
    # create_node_from_name returns None and the failure reads as a typo in the
    # node name rather than as a missing asset.
    for path in (CHARACTER_BP_PATH, ITEM_BP_PATH, HEALTH_BP_PATH):
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
    # Aiming down the sights. BaseFOV is cached off the camera at BeginPlay for
    # the same reason BaseSpeed is cached off the movement component; CurrentFOV
    # is stored because FInterpTo's input is its own previous output, and
    # TargetFOV because the two arms of the zoom branch must write one value
    # that one interpolation then reads.
    for name in ("BaseFOV", "CurrentFOV", "TargetFOV"):
        _declare(ed, name, _float_type())
    _declare(ed, "Aiming", BEL.get_basic_type_by_name("bool"))
    # The seven polled keys, as variables rather than as pin literals. Nothing
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
    # What the ready pose currently reflects, as opposed to what it should.
    # The pair is what makes the sprint pose edge-triggered; see _author_wc_tick.
    _declare(ed, "PoseSprinting", BEL.get_basic_type_by_name("bool"))
    # Recoil. RecoilDebt/RecoilYawDebt are what has been kicked and not yet
    # given back, recovered toward zero every frame; RecoilYawKick holds the
    # one draw of the sideways component for the frame it is fired on, because
    # RandomFloatInRange is pure and a second read would be a second number.
    for name in ("RecoilDebt", "RecoilYawDebt", "RecoilYawKick"):
        _declare(ed, name, _float_type())
    # How many rounds this reload moves, computed once and read back three
    # times. See _author_reload for why it cannot just be recomputed.
    _declare(ed, "ReloadTake", BEL.get_basic_type_by_name("int"))
    # The fire press that ate an item, until it is released; see consume.py.
    _declare(ed, TRIGGER_SPENT, BEL.get_basic_type_by_name("bool"))
    # The GameMode's DebugMode, cached at the moment of firing so the pellet
    # loop can branch on a plain bool instead of casting eight times.
    _declare(ed, DEBUG_MODE_VAR, BEL.get_basic_type_by_name("bool"))
    _declare(ed, HIT_BONE_VAR, BEL.get_basic_type_by_name("name"))
    # Typed as "class of BP_WeaponItem", not "class of Actor": SpawnActor's
    # return pin takes its type from its Class pin, and an Actor-typed return
    # cannot be added to an array of BP_WeaponItem.
    for name in ("ShotgunClass", "PistolClass", "ItemClass"):
        _declare(ed, name, BEL.get_class_reference_type(item_class))
    _declare(ed, "BloodClass",
             BEL.get_class_reference_type(unreal.Actor.static_class()))

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
        # 1.0 is "exactly what the controller already does", because the two
        # base scales this multiplies are the controller's own. A player who
        # never opens the settings screen therefore gets the stock feel.
        "MouseSensitivity": COMBAT.mouse_sensitivity_default,
        "ScopeSensitivity": COMBAT.ads_scope_sens_scale,
        **{name: _key(k) for name, k in BIND_VARS},
        # Both overwritten on the first frame of BeginPlay. Seeded with the
        # engine's own defaults, signs included, so that a BeginPlay that
        # somehow never ran leaves the look working rather than dead.
        "BaseYawScale": 2.5,
        "BasePitchScale": -2.5,
        # Matches Sprinting, so the first frame sees no edge and does not
        # re-equip for nothing.
        "PoseSprinting": False,
        "ReloadTake": 0,
        TRIGGER_SPENT: False,
        "RecoilDebt": 0.0,
        "RecoilYawDebt": 0.0,
        "RecoilYawKick": 0.0,
        DEBUG_MODE_VAR: False,
        "ShotgunClass": BEL.generated_class(shotgun_bp),
        "PistolClass": BEL.generated_class(pistol_bp),
        "ItemClass": item_class,
        "BloodClass": BEL.generated_class(blood_bp),
    })
    _log(f"built {WEAPON_COMP_BP_PATH}")
    return bp
