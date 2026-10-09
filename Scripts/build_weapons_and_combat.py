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
  Anims/A_KnifeSlash, A_AxeSwing, A_HoldKnife, A_HoldAxe  the knife's and the axe's
                      swing and ready pose, baked from Mixamo's (combat/melee_clips.py)
  Anims/A_HoldItem, A_HoldTorch, A_WardTorch  how food and the stick are held (combat/hold_pose.py)
  Anims/A_ThrowReady  the arm cocked while a throw is aimed (combat/throw_pose.py)
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
for _name in [m for m in sys.modules if m.split(".")[0] in ("uebp", "net", "combat", "loot", "item_icons", "Sound")]:
    del sys.modules[_name]

from combat.build_steps import run                                 # noqa: E402


# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    """Every step in order, or the ones $UEPY_BUILD_ONLY names
    (``uepy.py --only``): combat/build_steps.py."""
    run()


if __name__ == "__main__":
    main()
