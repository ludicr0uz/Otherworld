"""
build_weapons_and_combat.py -- weapons, inventory, aiming, damage and death.

Run inside the editor:
    python3 Scripts/dev/uepy.py Scripts/build_weapons_and_combat.py
or cold:
    UnrealEditor-Cmd <uproject> \\
      -ExecutePythonScript="<abs>/Scripts/build_weapons_and_combat.py" -NoUI -stdout

This file is only the entry point: main() runs the steps in dependency order.
The code lives in the ``combat`` package next to it, one module per
responsibility -- Scripts/combat/__init__.py maps which module owns what.
Checked by verify_weapons_and_combat.py (the ``combat.verify`` package).

Supersedes build_shotgun_and_health.py, which built a single shotgun welded to
the character. Everything that file installed is removed by this one (see
combat.install._uninstall_old_shotgun) -- keep the old script only as history.

WHAT THIS BUILDS
----------------
/Game/Weapons
  M_Gunmetal, M_GunWood, M_Blood, M_ImpactChip, M_ImpactDust   flat materials
  Audio/A_ShotgunFire, A_PistolFire  imported from assets/generated/sounds
  BP_WeaponItem     Actor. The base class: every variable the weapon component
                    reads lives here, so the component casts once and never
                    branches per weapon type.
  BP_Shotgun        child of BP_WeaponItem: 7 primitives, 8 pellets, 5 deg cone
  BP_Pistol         child of BP_WeaponItem: 5 primitives, 1 shot, tight, held
                    at a different angle with a different ready pose
  BP_Knife          child of BP_WeaponItem: the Fab pack's M9 knife, Melee --
                    the fire key slashes (combat/knife.py)
  BP_Axe            child of BP_WeaponItem: Quaternius's Survival Pack axe,
                    Melee too, swung as the knife is (combat/axe.py)
  BP_Wood           child of BP_WeaponItem: a log, what a tree gives the axe
                    (combat/wood.py, weapon_component/chop.py)
  BP_Matches        child of BP_WeaponItem: a box of matches; struck with wood
                    in the bag, it lights a campfire (combat/matches.py,
                    weapon_component/light.py; the campfire is survival's)
  Anims/A_KnifeSlash  the slash, keyed for the worn body (combat/knife_anim.py)
  Anims/A_HoldItem, A_HoldKnife  how food and the knife are held (combat/hold_pose.py)
  Anims/A_ThrowReady  the arm cocked while a throw is aimed (combat/throw_pose.py)
  Anims/A_AimShotgun             the shotgun's ready pose: the thumb over the stock (combat/shotgun_pose.py)
  BP_HealthComponent  Health/MaxHealth + death, despawn and respawn
  BP_WeaponComponent  inventory of 5, equip/switch/fire/drop/pick up
  BP_BloodSplash    short-lived red burst spawned at each impact on a body
  BP_BulletImpact   short-lived chips and dust where a bullet hits the scenery
  BP_ThrowArc, M_ThrowArc  the dotted arc drawn while a throw is aimed
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# A live editor keeps imported modules between runs: drop the combat package so
# an edit to any of its modules is what actually runs.
for _name in [m for m in sys.modules if m.split(".")[0] in ("combat", "loot", "item_icons")]:
    del sys.modules[_name]

from combat.aim_pitch import patch_aim_pitch                      # noqa: E402
from combat.ammo_pickup import build_ammo_pickup                  # noqa: E402
from combat.anim_blueprint import patch_anim_blueprint            # noqa: E402
from combat.audio import (                                        # noqa: E402
    apply_attenuation, build_sound_attenuations, import_sounds,
)
from combat.body_pose import patch_body_pose                      # noqa: E402
from combat.stance_clips import (                                 # noqa: E402
    patch_stance_clips, unpatch_stance_clips,
)
from combat.support_hand import patch_support_hand                # noqa: E402
from combat.blood import build_blood_splash                       # noqa: E402
from combat.bullet_impact import build_bullet_impact              # noqa: E402
from combat.combat_trace import build_combat_trace_switch         # noqa: E402
from combat.footsteps import build_footstep_component             # noqa: E402
from combat.game_state import ensure_game_mode_vars               # noqa: E402
from combat.graph import BEL, _apply_defaults, _log               # noqa: E402
from combat.health_component import build_health_component        # noqa: E402
from combat.axe import build_axe                                  # noqa: E402
from combat.wood import build_wood                                # noqa: E402
from combat.matches import build_matches                          # noqa: E402
from combat.stick import build_stick                              # noqa: E402
from combat.knife import build_knife                              # noqa: E402
from combat.knife_anim import build_knife_slash                   # noqa: E402
from combat.hold_pose import build_hold_poses                     # noqa: E402
from combat.shotgun_pose import build_shotgun_pose                # noqa: E402
from combat.install import (                                      # noqa: E402
    install_on_character, install_on_npc, retire_old_assets,
)
from combat.materials import build_materials                      # noqa: E402
from combat.heat import build_hot_material                        # noqa: E402
from combat.throw_arc import build_throw_arc                      # noqa: E402
from combat.throw_pose import build_throw_ready                   # noqa: E402
from combat.paths import AMMO_BP_PATH, HEALTH_BP_PATH             # noqa: E402
from combat.player_gait import patch_gait                         # noqa: E402
from combat.hit_bodies import fit_hit_bodies                      # noqa: E402
from combat.ragdoll import tune_ragdolls                          # noqa: E402
from combat.settings_savegame import build_settings_savegame      # noqa: E402
from combat.skin import wear_skin                                 # noqa: E402
from combat.tuning import GUN_DROP_CHANCE, GUN_LOOT_TABLE         # noqa: E402
from combat.weapon_component.build import build_weapon_component  # noqa: E402
from combat.weapon_items import build_weapon, build_weapon_item   # noqa: E402
from combat.weapon_specs import DROP_TICKETS, _weapon_specs       # noqa: E402


# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    build_materials()
    # Before the knife and the axe, whose glow is an instance of it.
    build_hot_material()
    import_sounds()
    # Both halves have to exist before either can name the other, so the link
    # is a third step rather than something import_sounds() does on the way
    # past -- and it is a step that refuses to finish with a sound it has no
    # profile for.
    apply_attenuation(build_sound_attenuations())
    patch_anim_blueprint()

    # First of the Blueprints, and before anything that names its class: both
    # consumers -- this file's weapon component defaults and the HUD's settings
    # screen -- have to be able to load /Game/Weapons/BP_Settings, and the HUD
    # builder runs after this whole script.
    build_settings_savegame()

    # Before the weapons: every weapon's GripRotation is solved against the
    # ready pose as seen through the player's own rig, so the body has to be
    # the final one before the first spec is built.
    skin = wear_skin()
    # Before anything compiles the anim BP (see unpatch_stance_clips).
    unpatch_stance_clips(skin)
    # Before the weapon component, whose Tick sets the AimPitch this declares.
    patch_aim_pitch(skin)
    patch_body_pose(skin)
    # After the pitch, whose chain it joins the end of.
    patch_support_hand(skin)
    # The crouch and the crawl clips under everything else (or none, and the
    # body poses above do it procedurally).
    patch_stance_clips(skin)
    # The jog's speed onto the blend space's jog row, or the player walks.
    patch_gait(skin)

    # Before the weapons: the shotgun's row names it, and its grip is solved
    # in it.
    build_shotgun_pose(skin)
    item_bp = build_weapon_item()
    weapons = {}
    for spec in _weapon_specs():
        weapons[spec["display"]] = build_weapon(spec, item_bp)
    # Before the knife and the consumables, whose grips are solved in them.
    build_hold_poses(skin)
    # The arm cocked while a throw is aimed: the throw clip, stopped.
    build_throw_ready(skin)
    # The third starter item: a melee item, not a row of the gun table.
    knife_bp = build_knife(item_bp)
    knife_clip = build_knife_slash(skin)
    # The fourth: the axe, swung through the knife's slash.
    axe_bp = build_axe(item_bp)
    # ...and what a tree gives it.
    wood_bp = build_wood(item_bp)
    # The fifth: the matches, which burn it.
    matches_bp = build_matches(item_bp)
    # The sixth: a stick, lit at the fire they make.
    stick_bp = build_stick(item_bp)

    blood_bp = build_blood_splash()
    impact_bp = build_bullet_impact()
    # Before the health component: its BeginPlay casts to the GameMode, and a
    # cast node only appears in the palette for a class that is already loaded.
    ensure_game_mode_vars()
    build_combat_trace_switch()
    health_bp = build_health_component()
    footstep_bp = build_footstep_component()
    throw_arc_bp = build_throw_arc()
    weapon_bp = build_weapon_component(item_bp, weapons["Shotgun"],
                                       weapons["Pistol"], knife_bp, axe_bp,
                                       knife_clip, blood_bp, impact_bp, throw_arc_bp,
                                       wood_bp, matches_bp, stick_bp)

    # After the weapon component, because the pickup's graph casts to it -- and
    # therefore after the health component that spawns it, which is why the
    # link between the two is a default written here rather than a parameter.
    ammo_bp = build_ammo_pickup()
    _apply_defaults(health_bp, {
        "AmmoClass": BEL.generated_class(ammo_bp),
        # The loot table, one entry per ticket (GUN_LOOT_TABLE's weights), so
        # the graph's uniform pick roll over it is the weighted draw.
        "DropClasses": [BEL.generated_class(weapons[name])
                        for name in DROP_TICKETS],
    })
    _log(f"{HEALTH_BP_PATH}.AmmoClass -> {AMMO_BP_PATH}")
    _log(f"{HEALTH_BP_PATH}.DropClasses -> "
         f"{', '.join(f'{n} x{w}' for n, w in GUN_LOOT_TABLE)} "
         f"({GUN_DROP_CHANCE * 100:.0f}% per kill)")

    tune_ragdolls()
    fit_hit_bodies()
    install_on_character(health_bp, weapon_bp, footstep_bp)
    install_on_npc(health_bp, footstep_bp)
    retire_old_assets()

    _log(f"done — five weapons, a knife, an axe, matches and a stick, ammunition, inventory, aiming down the sights, "
         f"footsteps, blood, death, drops and respawn, worn by "
         f"{skin.mesh.rsplit('/', 1)[1]}")


if __name__ == "__main__":
    main()
