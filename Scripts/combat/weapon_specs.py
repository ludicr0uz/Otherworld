"""The five weapons as data: their muzzle offsets, icons and the
_weapon_specs() table every builder and the verifier iterate. Adding a weapon
is a row here. Every gun is a model now, and its parts (the measured outline),
muzzle and sight come from weapon_models.py.
"""

import unreal

from combat.log import _log
from combat import item_vars as IV
from combat.gun_rows import gun_row
from combat.gun_tuning import read_table
from combat.grip import _grip_location, _grip_rotation
from combat.paths import (
    PISTOL_BP_PATH,
    RIFLE_BP_PATH, SHOTGUN_BP_PATH, SMG_BP_PATH, SNIPER_BP_PATH,
    UI_ART_DIR,
)
from combat.skin import player_skin
from Sound.sound_weapons import fire_sound, reload_sound
from combat import finger_pose, gun_hold
from item_icons.items import icon_name
from combat.weapon_models import (
    PISTOL_MODEL, PISTOL_MUZZLE, PISTOL_SIGHT, PISTOL_SIGHT_FRONT,
    PISTOL_SIGHT_REAR, RIFLE_MODEL, RIFLE_MUZZLE, RIFLE_SIGHT,
    RIFLE_SIGHT_FRONT, RIFLE_SIGHT_REAR, SHOTGUN_MODEL, SHOTGUN_MUZZLE,
    SHOTGUN_SIGHT, SHOTGUN_SIGHT_FRONT, SHOTGUN_SIGHT_REAR,
    SHOTGUN_TRIGGER_REACH_CM, PISTOL_POSE_TRIGGER_REACH_CM, TRIGGER_REACH_CM, SMG_MODEL, SMG_MUZZLE, SMG_SIGHT,
    SMG_SIGHT_FRONT, SMG_SIGHT_REAR, SNIPER_MODEL, SNIPER_MUZZLE, SNIPER_SIGHT,
    SNIPER_SIGHT_FRONT, SNIPER_SIGHT_REAR, pistol_outline, rifle_outline,
    shotgun_outline, smg_outline, sniper_outline,
    PISTOL_SUPPORT, RIFLE_SUPPORT, SHOTGUN_SUPPORT, SMG_SUPPORT, SNIPER_SUPPORT,
)
from combat.tuning import (
    GUN_LOOT_TABLE, RIFLE_RESERVE, SHOTGUN_RESERVE, SMG_RESERVE, SNIPER_RESERVE,
)


# Each accuracy column and the BP_WeaponItem variable it becomes.
ACCURACY_VARS = (
    ("spread", IV.SpreadDegrees),
    ("spread_shoulder", IV.SpreadShoulderScale),
    ("spread_crouch", IV.SpreadCrouchScale),
    ("spread_prone", IV.SpreadProneScale),
    ("pellet_spread", IV.PelletSpreadDegrees),
    ("recoil", IV.RecoilPitch),
    ("recoil_yaw", IV.RecoilYaw),
    ("recoil_shoulder", IV.RecoilShoulderScale),
    ("recoil_sights", IV.RecoilSightsScale),
    ("recoil_crouch", IV.RecoilCrouchScale),
    ("recoil_prone", IV.RecoilProneScale),
)


def _weapon_icon(display):
    """The item's inventory icon, or None if it has not been rendered yet.

    Soft rather than fatal, and it has to be: the icon is a picture of the
    item's own model (Scripts/build_item_icons.py), so on a fresh clone the
    item is built first, with an empty slot where the icon goes, and built
    again once its icon exists.
    """
    path = f"{UI_ART_DIR}/{icon_name(display)}"
    tex = unreal.EditorAssetLibrary.load_asset(path)
    if not tex:
        _log(f"note: {path} missing -- {display} will have no inventory icon. "
             "Run `python3 Scripts/build_item_icons.py`, then this build again")
    return tex


def _weapon_specs():
    """Everything that differs between the two weapons, in one table.

    Each grip is solved against that weapon's own ready pose, so the two differ
    because the poses differ -- not because a fudge factor was added to one of
    them. GripLocation is solved the same way, never typed in: each weapon's
    "Grip" part is moved to where the fingers close in its ready pose
    (grip._grip_location), which is filled in below once the rotation is known.

    The ammunition columns are here too rather than branched on DisplayName
    anywhere in the graphs: the firing code asks the weapon whether it uses
    ammo, so a third weapon needs a row in this table and no new nodes. The
    same is true of `automatic`: the tick polls the fire key both ways every
    frame and asks the weapon which answer counts, so making a sixth weapon
    full-auto is a True in this table and nothing else.

    That claim has now been tested. The SMG, the assault rifle and the sniper
    were added as three rows here plus three part tables, and not one node in
    _author_fire, the reload or the fire gate changed to accommodate them:
    pellet count, spread, range, interval, magazine and reload time were
    already the parameters those graphs read off Held. The only code the three
    needed is the code for *finding* one, which is a property of the drop and
    not of the weapon.

    DropClasses below is what marks a weapon as findable rather than issued.

    A row with a `model` is drawn by that model (weapon_models.py), and its
    `parts` are the model's measured outline: never built, but read by the
    grip solve and the sight checks exactly as a primitive gun's parts are.

    Every number the GUN SETTINGS page can change is not a literal here: it
    is the gun's row of gun_rows.py (GUN_DEFAULTS, and GUN_ACCURACY for the
    spread and the recoil, so the accuracy of all five reads as one table),
    overridden by its cell in gun_tuning.csv. gun_row() lays the one over
    the other, in plain Python, so dev/tests/test_weapon_tuning.py holds
    what is built to the CSV without an editor.

    `shot_volume` is how far the shot is heard, and it is read from
    SHOT_VOLUME_CM in tuning.py rather than written inline, because the five
    only mean something against each other: that table is where "the sniper
    is the loudest, the pistol the quietest" is visible in one place.
    """
    skin = player_skin()
    AIM_RIFLE, AIM_PISTOL = skin.aim_rifle, skin.aim_pistol
    # Where the pistol pose keeps the index off the trigger (PlayerSkin.fist_index).
    PISTOL_REACH = PISTOL_POSE_TRIGGER_REACH_CM if skin.fist_index else TRIGGER_REACH_CM
    # The rifle's pose: the left hand's point is its own (shotgun_hold.py).
    AIM_SHOTGUN = AIM_RIFLE
    specs = (
        dict(path=SHOTGUN_BP_PATH, parts=shotgun_outline(), model=SHOTGUN_MODEL, muzzle=SHOTGUN_MUZZLE, sight=SHOTGUN_SIGHT, support=SHOTGUN_SUPPORT,
             sight_rear=SHOTGUN_SIGHT_REAR, sight_front=SHOTGUN_SIGHT_FRONT,
             display="Shotgun", automatic=False,
             sound=fire_sound(SHOTGUN_BP_PATH), reload_sound=reload_sound(SHOTGUN_BP_PATH), aim=AIM_SHOTGUN,
             grip_rot=_grip_rotation(AIM_SHOTGUN), trigger_reach=SHOTGUN_TRIGGER_REACH_CM,
             uses_ammo=True, reserve=SHOTGUN_RESERVE),
        dict(path=PISTOL_BP_PATH, parts=pistol_outline(), model=PISTOL_MODEL, muzzle=PISTOL_MUZZLE, sight=PISTOL_SIGHT, support=PISTOL_SUPPORT,
             sight_rear=PISTOL_SIGHT_REAR, sight_front=PISTOL_SIGHT_FRONT,
             display="Pistol", automatic=False,
             sound=fire_sound(PISTOL_BP_PATH), reload_sound=reload_sound(PISTOL_BP_PATH), aim=AIM_PISTOL,
             grip_rot=_grip_rotation(AIM_PISTOL), trigger_reach=PISTOL_REACH,
             uses_ammo=True, reserve=0, infinite_reserve=True),
        # 12 x 9 = 108 damage to kill, delivered in 0.81 s. The lowest damage
        # per round of the five and the highest per second, which is the whole
        # identity: it wins a fight it is already in and empties fast. The SMG11
        # is a machine pistol, so it is held in the pistol's ready pose.
        dict(path=SMG_BP_PATH, parts=smg_outline(), model=SMG_MODEL, muzzle=SMG_MUZZLE, sight=SMG_SIGHT, support=SMG_SUPPORT,
             sight_rear=SMG_SIGHT_REAR, sight_front=SMG_SIGHT_FRONT,
             display="SMG", automatic=True,
             sound=fire_sound(SMG_BP_PATH), reload_sound=reload_sound(SMG_BP_PATH), aim=AIM_PISTOL,
             grip_rot=_grip_rotation(AIM_PISTOL), trigger_reach=PISTOL_REACH,
             uses_ammo=True, reserve=SMG_RESERVE),
        # Five rounds to a kill at 0.14 s apart, accurate to 90 m. The generalist,
        # and the one a player who finds it will simply keep.
        dict(path=RIFLE_BP_PATH, parts=rifle_outline(), model=RIFLE_MODEL, muzzle=RIFLE_MUZZLE, sight=RIFLE_SIGHT, support=RIFLE_SUPPORT,
             sight_rear=RIFLE_SIGHT_REAR, sight_front=RIFLE_SIGHT_FRONT,
             display="Rifle", automatic=True,
             sound=fire_sound(RIFLE_BP_PATH), reload_sound=reload_sound(RIFLE_BP_PATH), aim=AIM_RIFLE,
             grip_rot=_grip_rotation(AIM_RIFLE),
             uses_ammo=True, reserve=RIFLE_RESERVE),
        # One shot, one kill: 120 against 100 HP, exact down the scope, and
        # 200 m of range -- further than anything in a 200 m forest is visible.
        # The cost is 1.6 s between shots, which against a pack of five that
        # runs at 600 cm/s is the difference between opening at distance and
        # being caught reloading.
        dict(path=SNIPER_BP_PATH, parts=sniper_outline(), model=SNIPER_MODEL, muzzle=SNIPER_MUZZLE, sight=SNIPER_SIGHT, support=SNIPER_SUPPORT,
             sight_rear=SNIPER_SIGHT_REAR, sight_front=SNIPER_SIGHT_FRONT,
             display="Sniper", automatic=False,
             sound=fire_sound(SNIPER_BP_PATH), reload_sound=reload_sound(SNIPER_BP_PATH), aim=AIM_RIFLE,
             grip_rot=_grip_rotation(AIM_RIFLE),
             scoped=True,
             uses_ammo=True, reserve=SNIPER_RESERVE),
    )
    # gun_tuning.csv last: what the in-game GUN SETTINGS page saved wins over
    # every default of gun_rows.py (gun_tuning.py lists the columns it may hold).
    tuned = read_table()
    for spec in specs:
        spec.update(gun_row(spec["display"], tuned))
        # Held in both hands is what the rifle ready pose does (the shotgun
        # is held in it too); the guard pose (body_pose.py) picks fists or
        # the gun across the body on it.
        # `pose` is the shipped clip the grip and the hands are solved in;
        # `aim` is the clip the gun is held in, which is its own where its
        # fingers are bent onto its model (finger_pose.py).
        spec["pose"] = spec["aim"]
        spec["two_handed"] = spec["pose"] in two_handed_poses(skin)
        spec["grip_loc"] = _grip_location(spec["pose"], spec["grip_rot"], spec["parts"])
        # Where the left hand is held down the sights (support_hand.py):
        # its ready pose's place, moved onto the part the row names.
        spec["support_point"] = support_point_of(skin, spec)
        if finger_pose.fitted(spec):
            spec["aim"] = finger_pose.clip_path(spec)
    return specs


def support_point_of(skin, spec, quiet=False):
    """Where ``spec``'s gun has the left hand down the sights, in the right
    hand's bone space: where its ready pose has it, moved onto the part of
    the model its row names (`support`, gun_hold.py)."""
    return gun_hold.support_point(skin, spec, quiet)


def two_handed_poses(skin):
    """The ready poses that hold a gun in both hands."""
    return (skin.aim_rifle,)


# Which of the five a killed wanderer can be carrying, in loot-table order. The
# starting loadout is excluded by construction: a drop the player already has in
# slot 0 is not a reward, and GUN_LOOT_TABLE is the only thing that decides.
DROP_DISPLAYS = tuple(name for name, _ in GUN_LOOT_TABLE)
# The table expanded to one entry per ticket, which is what DropClasses holds:
# a uniform draw over these is the weighted draw over the table.
DROP_TICKETS = tuple(name for name, weight in GUN_LOOT_TABLE
                     for _ in range(weight))
