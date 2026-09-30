"""The five weapons as data: their primitive parts, muzzle offsets, icons
and the _weapon_specs() table every builder and the verifier iterate.
Adding a weapon is a row here. The SMG, the rifle and the sniper are Fab
models, and their parts, muzzles and sights come from weapon_models.py.
"""

import unreal

from build_ui_art import ICON_NAME_FOR
from combat.audio import (
    SND_RELOAD_PISTOL, SND_RELOAD_RIFLE, SND_RELOAD_SHOTGUN,
)
from combat.graph import _log, _rot
from combat.grip import _barrel_rotation, _grip_location, _grip_rotation
from combat.paths import (
    AUDIO_DIR, CUBE, CYLINDER, MAT_METAL, MAT_WOOD, PISTOL_BP_PATH,
    RIFLE_BP_PATH, SHOTGUN_BP_PATH, SMG_BP_PATH, SNIPER_BP_PATH, UI_ART_DIR,
)
from combat.skin import player_skin
from combat.weapon_models import (
    RIFLE_MODEL, RIFLE_MUZZLE, RIFLE_SIGHT, SMG_MODEL, SMG_MUZZLE, SMG_SIGHT,
    SNIPER_MODEL, SNIPER_MUZZLE, SNIPER_SIGHT, rifle_outline, smg_outline,
    sniper_outline,
)
from combat.tuning import (
    COMBAT, GUN_LOOT_TABLE, PISTOL_FIRE_INTERVAL, PISTOL_MAGAZINE,
    PISTOL_RELOAD_SECONDS, RIFLE_FIRE_INTERVAL, RIFLE_MAGAZINE,
    RIFLE_RELOAD_SECONDS, RIFLE_RESERVE, SHOTGUN_FIRE_INTERVAL,
    SHOTGUN_MAGAZINE, SHOTGUN_RELOAD_SECONDS, SHOTGUN_RESERVE,
    SHOT_VOLUME_CM, SMG_FIRE_INTERVAL, SMG_MAGAZINE, SMG_RELOAD_SECONDS,
    SMG_RESERVE, SNIPER_FIRE_INTERVAL, SNIPER_MAGAZINE, SNIPER_RELOAD_SECONDS,
    SNIPER_RESERVE,
)


# Each part: (name, mesh, location, rotation, scale, material).
# Local frame: +X is the muzzle direction, +Z is up, origin sits in the fist.
# A Cube is 100 cm, so scale is the size in metres; a Cylinder is 100 cm tall
# with a 50 cm radius, so scale 0.02 gives a 1 cm radius.

def _shotgun_parts():
    barrel = _barrel_rotation()
    return (
        ("Receiver",     CUBE,     (25.0, 0.0, 0.0),   _rot(),          (0.30, 0.055, 0.075),  MAT_METAL),
        ("Barrel",       CYLINDER, (70.0, 0.0, 2.2),   barrel,          (0.024, 0.024, 0.60),  MAT_METAL),
        ("MagTube",      CYLINDER, (66.0, 0.0, -2.6),  barrel,          (0.020, 0.020, 0.52),  MAT_METAL),
        ("Pump",         CUBE,     (55.0, 0.0, -2.6),  _rot(),          (0.20, 0.050, 0.050),  MAT_WOOD),
        ("Stock",        CUBE,     (-8.0, 0.0, -2.5),  _rot(pitch=6.0), (0.34, 0.048, 0.070),  MAT_WOOD),
        ("Grip",         CUBE,     (8.0, 0.0, -6.0),   _rot(pitch=20.0),(0.055, 0.042, 0.085), MAT_WOOD),
        ("TriggerGuard", CUBE,     (14.0, 0.0, -4.5),  _rot(),          (0.070, 0.030, 0.020), MAT_METAL),
    )


def _pistol_parts():
    """Shorter, all-metal, and with the grip raked back under the receiver.

    The silhouette is what sells which weapon is in hand at a glance, so the
    pistol is deliberately a third the shotgun's length with no wood on it.
    """
    barrel = _barrel_rotation()
    return (
        ("Slide",        CUBE,     (14.0, 0.0, 1.5),   _rot(),           (0.17, 0.035, 0.040), MAT_METAL),
        ("Frame",        CUBE,     (10.0, 0.0, -2.0),  _rot(),           (0.14, 0.032, 0.030), MAT_METAL),
        ("Barrel",       CYLINDER, (24.0, 0.0, 1.5),   barrel,           (0.011, 0.011, 0.10), MAT_METAL),
        ("Grip",         CUBE,     (1.0, 0.0, -7.5),   _rot(pitch=15.0), (0.045, 0.036, 0.095), MAT_WOOD),
        ("TriggerGuard", CUBE,     (7.0, 0.0, -4.5),   _rot(),           (0.050, 0.026, 0.016), MAT_METAL),
    )


# Muzzle tip in the weapon's own space: where the barrel actually ends, so the
# pellet cone starts at the gun rather than inside the player's chest.
SHOTGUN_MUZZLE = (101.0, 0.0, 2.2)
PISTOL_MUZZLE = (30.0, 0.0, 1.5)

# The eye when aiming down the sights, in the same space. None of the primitive
# guns has a modelled sight, so the sight line is the top of the gun: the eye sits a
# centimetre or two above the highest part along the bore, and 20-ish cm
# behind the rear of the receiver (or slide). Tuned by eye in PIE: 14 cm back
# and the receiver's back face filled a third of the screen; 34 cm back and
# the camera was inside the adventurer's head, whose hair crossed the view.
# The SMG (over its receiver), the rifle (over its irons) and the sniper (on
# its scope's axis) are in weapon_models.py.
SHOTGUN_SIGHT = (-12.0, 0.0, 5.5)
PISTOL_SIGHT = (-16.0, 0.0, 5.0)


# ─── Accuracy: where the shot goes, and what it does to the view ─────────────
#
# Two separate mechanics, every number per gun (the task that added them asked
# for exactly that, so nothing here is a global in COMBAT):
#
# THE CLOUD decides where a shot lands. Each trigger pull draws ONE direction
# inside a cone of AimSpread degrees around the reticle's line, and the round
# (or the shotgun's whole pellet pattern) flies down it. AimSpread is written
# every frame by weapon_component/accuracy.py:
#
#     spread x (sights ? 0 : shoulder ? spread_shoulder : 1)
#            x (prone ? spread_prone : crouched ? spread_crouch : 1)
#
# so down the sights it is zero and the shot goes exactly where the reticle is.
# The HUD sizes the reticle from the same number, so its gap is the cloud.
# `pellet_spread` is not the cloud: it is the shotgun's pattern around wherever
# the cloud put the shot, and zero on a single-round gun.
#
# RECOIL moves the view (and so the reticle) after the shot, never the shot:
#
#     up       = recoil     x scale
#     sideways = +/- recoil_yaw x scale                (drawn once per shot)
#     scale    = (sights ? recoil_sights : shoulder ? recoil_shoulder : 1)
#              x (prone ? recoil_prone : crouched ? recoil_crouch : 1)
#
# recoil_yaw is a quarter of recoil on every gun (four times more climb than
# swing); it is a column so a gun may break that, and the verifier asserts the
# 4x for the five that exist. The orderings the verifier holds every row to:
# prone < crouched < 1 for both mechanics, and shoulder < 1.
#
# `recoil` is degrees of muzzle climb per shot. The ordering is the point of
# the numbers: the two heavy, slow weapons kick hardest (sniper 2.4, shotgun
# 2.2), the assault rifle next (0.85), the SMG less (0.45) and the pistol least
# (0.30). Read against the fire interval it is also a rate: the SMG's 0.45
# every 0.09 s is five degrees a second against the rifle's six, so the rifle
# is the one that walks off target under sustained fire.
GUN_ACCURACY = {
    #            cloud (deg) and its factors             pattern      recoil (deg) and its factors
    "Shotgun": dict(spread=3.0, spread_shoulder=0.50, spread_crouch=0.75, spread_prone=0.55,
                    pellet_spread=5.0,
                    recoil=2.2, recoil_yaw=0.55, recoil_shoulder=0.80, recoil_sights=0.65,
                    recoil_crouch=0.75, recoil_prone=0.50),
    "Pistol":  dict(spread=1.6, spread_shoulder=0.45, spread_crouch=0.75, spread_prone=0.55,
                    pellet_spread=0.0,
                    recoil=0.30, recoil_yaw=0.075, recoil_shoulder=0.80, recoil_sights=0.65,
                    recoil_crouch=0.80, recoil_prone=0.60),
    "SMG":     dict(spread=2.6, spread_shoulder=0.50, spread_crouch=0.75, spread_prone=0.55,
                    pellet_spread=0.0,
                    recoil=0.45, recoil_yaw=0.1125, recoil_shoulder=0.80, recoil_sights=0.65,
                    recoil_crouch=0.75, recoil_prone=0.50),
    "Rifle":   dict(spread=2.0, spread_shoulder=0.40, spread_crouch=0.70, spread_prone=0.45,
                    pellet_spread=0.0,
                    recoil=0.85, recoil_yaw=0.2125, recoil_shoulder=0.75, recoil_sights=0.60,
                    recoil_crouch=0.70, recoil_prone=0.45),
    # A sniper fired from the hip is a guess; from the scope it is exact.
    "Sniper":  dict(spread=3.0, spread_shoulder=0.35, spread_crouch=0.70, spread_prone=0.35,
                    pellet_spread=0.0,
                    recoil=2.4, recoil_yaw=0.6, recoil_shoulder=0.80, recoil_sights=0.60,
                    recoil_crouch=0.70, recoil_prone=0.40),
}

# Each accuracy column and the BP_WeaponItem variable it becomes.
ACCURACY_VARS = (
    ("spread", "SpreadDegrees"),
    ("spread_shoulder", "SpreadShoulderScale"),
    ("spread_crouch", "SpreadCrouchScale"),
    ("spread_prone", "SpreadProneScale"),
    ("pellet_spread", "PelletSpreadDegrees"),
    ("recoil", "RecoilPitch"),
    ("recoil_yaw", "RecoilYaw"),
    ("recoil_shoulder", "RecoilShoulderScale"),
    ("recoil_sights", "RecoilSightsScale"),
    ("recoil_crouch", "RecoilCrouchScale"),
    ("recoil_prone", "RecoilProneScale"),
)


def _weapon_icon(display):
    """The weapon's HUD silhouette, or None if the UI art is not built yet.

    Soft rather than fatal: a clone that has not run build_ui_art.py should
    still get a working game, with an empty slot where the icon goes.
    """
    path = f"{UI_ART_DIR}/{ICON_NAME_FOR(display)}"
    tex = unreal.EditorAssetLibrary.load_asset(path)
    if not tex:
        _log(f"note: {path} missing -- {display} will have no inventory icon. "
             "Run `python3 Scripts/build_ui_art.py` then "
             "Scripts/asset_pipeline/import_ui_art.py")
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
    _author_fire, _author_reload or the fire gate changed to accommodate them:
    pellet count, spread, range, interval, magazine and reload time were
    already the parameters those graphs read off Held. The only code the three
    needed is the code for *finding* one, which is a property of the drop and
    not of the weapon.

    DropClasses below is what marks a weapon as findable rather than issued.

    A row with a `model` is drawn by that model (weapon_models.py), and its
    `parts` are the model's measured outline: never built, but read by the
    grip solve and the sight checks exactly as a primitive gun's parts are.

    Spread and recoil are columns too, but they live in GUN_ACCURACY above and
    are merged into each row here, so the accuracy of all five reads as one
    table.

    `shot_volume` is how far the shot is heard, and it is read from
    SHOT_VOLUME_CM in tuning.py rather than written inline, because the five
    only mean something against each other: that table is where "the sniper
    is the loudest, the pistol the quietest" is visible in one place.
    """
    skin = player_skin()
    AIM_RIFLE, AIM_PISTOL = skin.aim_rifle, skin.aim_pistol
    specs = (
        dict(path=SHOTGUN_BP_PATH, parts=_shotgun_parts(), muzzle=SHOTGUN_MUZZLE, sight=SHOTGUN_SIGHT,
             display="Shotgun", automatic=False, damage=18.0, pellets=8, range=4000.0,
             sound=f"{AUDIO_DIR}/A_ShotgunFire", reload_sound=SND_RELOAD_SHOTGUN, aim=AIM_RIFLE,
             grip_rot=_grip_rotation(AIM_RIFLE),
             colour=(0.85, 0.45, 0.10),
             uses_ammo=True, magazine=SHOTGUN_MAGAZINE, reserve=SHOTGUN_RESERVE,
             interval=SHOTGUN_FIRE_INTERVAL, reload_s=SHOTGUN_RELOAD_SECONDS,
             shot_volume=SHOT_VOLUME_CM["Shotgun"]),
        dict(path=PISTOL_BP_PATH, parts=_pistol_parts(), muzzle=PISTOL_MUZZLE, sight=PISTOL_SIGHT,
             display="Pistol", automatic=False, damage=26.0, pellets=1, range=6000.0,
             sound=f"{AUDIO_DIR}/A_PistolFire", reload_sound=SND_RELOAD_PISTOL, aim=AIM_PISTOL,
             grip_rot=_grip_rotation(AIM_PISTOL),
             colour=(0.35, 0.65, 0.95),
             uses_ammo=True, magazine=PISTOL_MAGAZINE, reserve=0, infinite_reserve=True,
             interval=PISTOL_FIRE_INTERVAL, reload_s=PISTOL_RELOAD_SECONDS,
             shot_volume=SHOT_VOLUME_CM["Pistol"]),
        # 12 x 9 = 108 damage to kill, delivered in 0.81 s. The lowest damage
        # per round of the five and the highest per second, which is the whole
        # identity: it wins a fight it is already in and empties fast.
        dict(path=SMG_BP_PATH, parts=smg_outline(), model=SMG_MODEL, muzzle=SMG_MUZZLE, sight=SMG_SIGHT,
             display="SMG", automatic=True, damage=12.0, pellets=1, range=4500.0,
             sound=f"{AUDIO_DIR}/A_SMGFire", reload_sound=SND_RELOAD_RIFLE, aim=AIM_RIFLE,
             grip_rot=_grip_rotation(AIM_RIFLE),
             colour=(0.45, 0.85, 0.35),
             uses_ammo=True, magazine=SMG_MAGAZINE, reserve=SMG_RESERVE,
             interval=SMG_FIRE_INTERVAL, reload_s=SMG_RELOAD_SECONDS,
             shot_volume=SHOT_VOLUME_CM["SMG"]),
        # Five rounds to a kill at 0.14 s apart, accurate to 90 m. The generalist,
        # and the one a player who finds it will simply keep.
        dict(path=RIFLE_BP_PATH, parts=rifle_outline(), model=RIFLE_MODEL, muzzle=RIFLE_MUZZLE, sight=RIFLE_SIGHT,
             display="Rifle", automatic=True, damage=24.0, pellets=1, range=9000.0,
             sound=f"{AUDIO_DIR}/A_RifleFire", reload_sound=SND_RELOAD_RIFLE, aim=AIM_RIFLE,
             grip_rot=_grip_rotation(AIM_RIFLE),
             colour=(0.70, 0.45, 0.95),
             uses_ammo=True, magazine=RIFLE_MAGAZINE, reserve=RIFLE_RESERVE,
             interval=RIFLE_FIRE_INTERVAL, reload_s=RIFLE_RELOAD_SECONDS,
             shot_volume=SHOT_VOLUME_CM["Rifle"]),
        # One shot, one kill: 120 against 100 HP, exact down the scope, and
        # 200 m of range -- further than anything in a 200 m forest is visible.
        # The cost is 1.6 s between shots, which against a pack of five that
        # runs at 600 cm/s is the difference between opening at distance and
        # being caught reloading.
        dict(path=SNIPER_BP_PATH, parts=sniper_outline(), model=SNIPER_MODEL, muzzle=SNIPER_MUZZLE, sight=SNIPER_SIGHT,
             display="Sniper", automatic=False, damage=120.0, pellets=1, range=20000.0,
             sound=f"{AUDIO_DIR}/A_SniperFire", reload_sound=SND_RELOAD_PISTOL, aim=AIM_RIFLE,
             grip_rot=_grip_rotation(AIM_RIFLE),
             colour=(0.95, 0.30, 0.35), ads_zoom=COMBAT.ads_zoom_scope, scoped=True,
             uses_ammo=True, magazine=SNIPER_MAGAZINE, reserve=SNIPER_RESERVE,
             interval=SNIPER_FIRE_INTERVAL, reload_s=SNIPER_RELOAD_SECONDS,
             shot_volume=SHOT_VOLUME_CM["Sniper"]),
    )
    for spec in specs:
        spec.update(GUN_ACCURACY[spec["display"]])
        # Held in both hands is what the rifle ready pose does; the guard pose
        # (body_pose.py) picks fists or the gun across the body on it.
        spec["two_handed"] = spec["aim"] == AIM_RIFLE
        spec["grip_loc"] = _grip_location(spec["aim"], spec["grip_rot"], spec["parts"])
    return specs


# Which of the five a killed wanderer can be carrying, in loot-table order. The
# starting loadout is excluded by construction: a drop the player already has in
# slot 0 is not a reward, and GUN_LOOT_TABLE is the only thing that decides.
DROP_DISPLAYS = tuple(name for name, _ in GUN_LOOT_TABLE)
# The table expanded to one entry per ticket, which is what DropClasses holds:
# a uniform draw over these is the weighted draw over the table.
DROP_TICKETS = tuple(name for name, weight in GUN_LOOT_TABLE
                     for _ in range(weight))
