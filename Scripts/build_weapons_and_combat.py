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
  M_Gunmetal, M_GunWood, M_Blood   flat materials
  Audio/A_ShotgunFire, A_PistolFire  imported from assets/generated/sounds
  BP_WeaponItem     Actor. The base class: every variable the weapon component
                    reads lives here, so the component casts once and never
                    branches per weapon type.
  BP_Shotgun        child of BP_WeaponItem: 7 primitives, 8 pellets, 5 deg cone
  BP_Pistol         child of BP_WeaponItem: 5 primitives, 1 shot, tight, held
                    at a different angle with a different ready pose
  BP_HealthComponent  Health/MaxHealth + death, despawn and respawn
  BP_WeaponComponent  inventory of 5, equip/switch/fire/drop/pick up
  BP_BloodSplash    short-lived red burst spawned at each impact
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# A live editor keeps imported modules between runs: drop the combat package so
# an edit to any of its modules is what actually runs.
for _name in [m for m in sys.modules if m == "combat" or m.startswith("combat.")]:
    del sys.modules[_name]

from combat.ammo_pickup import build_ammo_pickup                  # noqa: E402
from combat.anim_blueprint import patch_anim_blueprint            # noqa: E402
from combat.audio import (                                        # noqa: E402
    apply_attenuation, build_sound_attenuations, import_sounds,
)
from combat.blood import build_blood_splash                       # noqa: E402
from combat.footsteps import build_footstep_component             # noqa: E402
from combat.game_state import ensure_game_mode_vars               # noqa: E402
from combat.graph import BEL, _apply_defaults, _log               # noqa: E402
from combat.health_component import build_health_component        # noqa: E402
from combat.install import (                                      # noqa: E402
    install_on_character, install_on_npc, retire_old_assets,
)
from combat.materials import build_materials                      # noqa: E402
from combat.paths import AMMO_BP_PATH, HEALTH_BP_PATH             # noqa: E402
from combat.ragdoll import tune_ragdolls                          # noqa: E402
from combat.settings_savegame import build_settings_savegame      # noqa: E402
from combat.skin import wear_skin                                 # noqa: E402
from combat.tuning import GUN_DROP_CHANCE                         # noqa: E402
from combat.weapon_component.build import build_weapon_component  # noqa: E402
from combat.weapon_items import build_weapon, build_weapon_item   # noqa: E402
from combat.weapon_specs import DROP_DISPLAYS, _weapon_specs      # noqa: E402


# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    build_materials()
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

    item_bp = build_weapon_item()
    weapons = {}
    for spec in _weapon_specs():
        weapons[spec["display"]] = build_weapon(spec, item_bp)

    blood_bp = build_blood_splash()
    # Before the health component: its BeginPlay casts to the GameMode, and a
    # cast node only appears in the palette for a class that is already loaded.
    ensure_game_mode_vars()
    health_bp = build_health_component()
    footstep_bp = build_footstep_component()
    weapon_bp = build_weapon_component(item_bp, weapons["Shotgun"],
                                       weapons["Pistol"], blood_bp)

    # After the weapon component, because the pickup's graph casts to it -- and
    # therefore after the health component that spawns it, which is why the
    # link between the two is a default written here rather than a parameter.
    ammo_bp = build_ammo_pickup()
    _apply_defaults(health_bp, {
        "AmmoClass": BEL.generated_class(ammo_bp),
        # The three findable weapons, in the order _weapon_specs() lists them
        # rather than in an order written out here -- so a weapon added to
        # DROP_DISPLAYS is in the table with no second edit.
        "DropClasses": [BEL.generated_class(weapons[name])
                        for name in DROP_DISPLAYS],
    })
    _log(f"{HEALTH_BP_PATH}.AmmoClass -> {AMMO_BP_PATH}")
    _log(f"{HEALTH_BP_PATH}.DropClasses -> {', '.join(DROP_DISPLAYS)} "
         f"({GUN_DROP_CHANCE * 100:.0f}% per kill)")

    tune_ragdolls()
    install_on_character(health_bp, weapon_bp, footstep_bp)
    install_on_npc(health_bp, footstep_bp)
    retire_old_assets()

    _log(f"done — five weapons, ammunition, inventory, aiming down the sights, "
         f"footsteps, blood, death, drops and respawn, worn by "
         f"{skin.mesh.rsplit('/', 1)[1]}")


if __name__ == "__main__":
    main()
