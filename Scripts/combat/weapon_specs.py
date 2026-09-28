"""The five weapons as data: their primitive parts, muzzle offsets, icons
and the _weapon_specs() table every builder and the verifier iterate.
Adding a weapon is a row here.
"""

import unreal

from build_ui_art import ICON_NAME_FOR
from combat.audio import (
    SND_RELOAD_PISTOL, SND_RELOAD_RIFLE, SND_RELOAD_SHOTGUN,
)
from combat.graph import _log, _rot
from combat.grip import _barrel_rotation, _grip_rotation
from combat.paths import (
    AUDIO_DIR, CUBE, CYLINDER, MAT_METAL, MAT_WOOD, PISTOL_BP_PATH,
    RIFLE_BP_PATH, SHOTGUN_BP_PATH, SMG_BP_PATH, SNIPER_BP_PATH, UI_ART_DIR,
)
from combat.skin import player_skin
from combat.tuning import (
    COMBAT, PISTOL_FIRE_INTERVAL, RIFLE_FIRE_INTERVAL, RIFLE_MAGAZINE,
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


def _smg_parts():
    """Compact and all-metal, with the magazine hanging straight down.

    The five weapons have to be told apart in a fist at 3 m with no UI, so each
    silhouette commits to one thing. The SMG's is *short* -- barely longer than
    the pistol -- and the vertical box magazine under the receiver is the one
    feature no other weapon here has.
    """
    barrel = _barrel_rotation()
    return (
        ("Receiver",     CUBE,     (20.0, 0.0, 0.0),   _rot(),           (0.24, 0.050, 0.070), MAT_METAL),
        ("Handguard",    CUBE,     (34.0, 0.0, 1.0),   _rot(),           (0.12, 0.045, 0.045), MAT_METAL),
        ("Barrel",       CYLINDER, (44.0, 0.0, 1.5),   barrel,           (0.014, 0.014, 0.22), MAT_METAL),
        ("Magazine",     CUBE,     (14.0, 0.0, -9.0),  _rot(pitch=8.0),  (0.035, 0.030, 0.110), MAT_METAL),
        ("Grip",         CUBE,     (4.0, 0.0, -7.0),   _rot(pitch=18.0), (0.048, 0.038, 0.088), MAT_METAL),
        ("Stock",        CUBE,     (-6.0, 0.0, 0.0),   _rot(),           (0.18, 0.030, 0.030), MAT_METAL),
        ("TriggerGuard", CUBE,     (10.0, 0.0, -4.5),  _rot(),           (0.060, 0.028, 0.018), MAT_METAL),
    )


def _rifle_parts():
    """Long, straight and flat-topped, with a carry handle above the receiver.

    The handle is doing real work: it is the only part above the bore line on
    any weapon but the sniper, and it is what stops the rifle reading as a
    slightly bigger SMG when both are seen from behind the shoulder.
    """
    barrel = _barrel_rotation()
    return (
        ("Receiver",     CUBE,     (26.0, 0.0, 0.0),    _rot(),            (0.30, 0.052, 0.072), MAT_METAL),
        ("Handguard",    CUBE,     (58.0, 0.0, 1.0),    _rot(),            (0.22, 0.048, 0.050), MAT_METAL),
        ("Barrel",       CYLINDER, (86.0, 0.0, 1.8),    barrel,            (0.016, 0.016, 0.34), MAT_METAL),
        ("CarryHandle",  CUBE,     (30.0, 0.0, 6.5),    _rot(),            (0.14, 0.030, 0.020), MAT_METAL),
        ("Magazine",     CUBE,     (18.0, 0.0, -10.0),  _rot(pitch=-12.0), (0.040, 0.032, 0.130), MAT_METAL),
        ("Grip",         CUBE,     (6.0, 0.0, -7.5),    _rot(pitch=20.0),  (0.050, 0.040, 0.090), MAT_METAL),
        ("Stock",        CUBE,     (-12.0, 0.0, -1.0),  _rot(),            (0.30, 0.045, 0.060), MAT_METAL),
        ("TriggerGuard", CUBE,     (13.0, 0.0, -4.5),   _rot(),            (0.065, 0.028, 0.018), MAT_METAL),
    )


def _sniper_parts():
    """The longest of the five, with wood furniture and a scope on rings.

    Wood is shared with the shotgun on purpose -- these are the two slow, heavy
    weapons -- and the scope plus the bolt handle are what separate them at a
    glance. It is also the only weapon whose barrel reaches past 1.4 m, which
    is visible in third person every time the player turns.
    """
    barrel = _barrel_rotation()
    return (
        ("Receiver",     CUBE,     (28.0, 0.0, 0.0),    _rot(),            (0.32, 0.055, 0.075), MAT_METAL),
        ("Barrel",       CYLINDER, (96.0, 0.0, 2.0),    barrel,            (0.018, 0.018, 0.52), MAT_METAL),
        ("Forestock",    CUBE,     (58.0, 0.0, -1.5),   _rot(),            (0.26, 0.050, 0.050), MAT_WOOD),
        ("Stock",        CUBE,     (-14.0, 0.0, -2.0),  _rot(pitch=4.0),   (0.42, 0.050, 0.078), MAT_WOOD),
        ("Scope",        CYLINDER, (34.0, 0.0, 9.0),    barrel,            (0.030, 0.030, 0.30), MAT_METAL),
        ("ScopeMountF",  CUBE,     (22.0, 0.0, 5.5),    _rot(),            (0.020, 0.020, 0.045), MAT_METAL),
        ("ScopeMountR",  CUBE,     (46.0, 0.0, 5.5),    _rot(),            (0.020, 0.020, 0.045), MAT_METAL),
        # Sticking out to the shooter's left in the weapon's own frame, which
        # reads as the bolt handle from the third-person camera behind them.
        ("Bolt",         CYLINDER, (18.0, -4.5, 2.0),   _rot(roll=90.0),   (0.012, 0.012, 0.090), MAT_METAL),
        ("Grip",         CUBE,     (10.0, 0.0, -6.5),   _rot(pitch=18.0),  (0.052, 0.040, 0.085), MAT_WOOD),
        ("TriggerGuard", CUBE,     (16.0, 0.0, -4.5),   _rot(),            (0.070, 0.030, 0.020), MAT_METAL),
    )


# Muzzle tip in the weapon's own space: where the barrel actually ends, so the
# pellet cone starts at the gun rather than inside the player's chest.
SHOTGUN_MUZZLE = (101.0, 0.0, 2.2)
PISTOL_MUZZLE = (30.0, 0.0, 1.5)
SMG_MUZZLE = (56.0, 0.0, 1.5)
RIFLE_MUZZLE = (122.0, 0.0, 1.8)
SNIPER_MUZZLE = (148.0, 0.0, 2.0)


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
    them. GripLocation stays at the socket for both: HandGrip_R sits in the fist
    already, and an invented offset is one more number nobody can later explain.

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

    `recoil` is degrees of muzzle climb per shot, and it is a column here for
    the same reason `spread` is -- how hard a gun kicks is a fact about the
    gun. The ordering is the point of the numbers: the two heavy, slow weapons
    kick hardest (sniper 2.4, shotgun 2.2), the assault rifle next (0.85), the
    SMG noticeably less (0.45) and the pistol least (0.30). Read against
    `interval` it is also a rate: the SMG's 0.45 every 0.09 s is five degrees a
    second of raw climb against the rifle's six, so the rifle is the one that
    walks off target under sustained fire while the SMG stays controllable --
    which is the same "wins the fight it is already in" identity its damage
    gives it. The two singles pay their whole kick in one visible jolt and
    then have a second to recover.

    `shot_volume` is how far the shot is heard, and it is read from
    SHOT_VOLUME_CM in tuning.py rather than written inline, because the five
    only mean something against each other: that table is where "the sniper
    is the loudest, the pistol the quietest" is visible in one place.
    """
    skin = player_skin()
    AIM_RIFLE, AIM_PISTOL = skin.aim_rifle, skin.aim_pistol
    return (
        dict(path=SHOTGUN_BP_PATH, parts=_shotgun_parts(), muzzle=SHOTGUN_MUZZLE,
             display="Shotgun", automatic=False, damage=18.0, pellets=8, spread=5.0, range=4000.0,
             sound=f"{AUDIO_DIR}/A_ShotgunFire", reload_sound=SND_RELOAD_SHOTGUN, aim=AIM_RIFLE,
             grip_loc=(0.0, 0.0, 0.0), grip_rot=_grip_rotation(AIM_RIFLE),
             colour=(0.85, 0.45, 0.10),
             uses_ammo=True, magazine=SHOTGUN_MAGAZINE, reserve=SHOTGUN_RESERVE,
             interval=SHOTGUN_FIRE_INTERVAL, reload_s=SHOTGUN_RELOAD_SECONDS,
             recoil=2.2, shot_volume=SHOT_VOLUME_CM["Shotgun"]),
        dict(path=PISTOL_BP_PATH, parts=_pistol_parts(), muzzle=PISTOL_MUZZLE,
             display="Pistol", automatic=False, damage=26.0, pellets=1, spread=1.0, range=6000.0,
             sound=f"{AUDIO_DIR}/A_PistolFire", reload_sound=SND_RELOAD_PISTOL, aim=AIM_PISTOL,
             grip_loc=(0.0, 0.0, 0.0), grip_rot=_grip_rotation(AIM_PISTOL),
             colour=(0.35, 0.65, 0.95),
             uses_ammo=False, magazine=0, reserve=0,
             interval=PISTOL_FIRE_INTERVAL, reload_s=0.0,
             recoil=0.30, shot_volume=SHOT_VOLUME_CM["Pistol"]),
        # 12 x 9 = 108 damage to kill, delivered in 0.81 s. The lowest damage
        # per round of the five and the highest per second, which is the whole
        # identity: it wins a fight it is already in and empties fast.
        dict(path=SMG_BP_PATH, parts=_smg_parts(), muzzle=SMG_MUZZLE,
             display="SMG", automatic=True, damage=12.0, pellets=1, spread=2.6, range=4500.0,
             sound=f"{AUDIO_DIR}/A_SMGFire", reload_sound=SND_RELOAD_RIFLE, aim=AIM_RIFLE,
             grip_loc=(0.0, 0.0, 0.0), grip_rot=_grip_rotation(AIM_RIFLE),
             colour=(0.45, 0.85, 0.35),
             uses_ammo=True, magazine=SMG_MAGAZINE, reserve=SMG_RESERVE,
             interval=SMG_FIRE_INTERVAL, reload_s=SMG_RELOAD_SECONDS,
             recoil=0.45, shot_volume=SHOT_VOLUME_CM["SMG"]),
        # Five rounds to a kill at 0.14 s apart, accurate to 90 m. The generalist,
        # and the one a player who finds it will simply keep.
        dict(path=RIFLE_BP_PATH, parts=_rifle_parts(), muzzle=RIFLE_MUZZLE,
             display="Rifle", automatic=True, damage=24.0, pellets=1, spread=1.4, range=9000.0,
             sound=f"{AUDIO_DIR}/A_RifleFire", reload_sound=SND_RELOAD_RIFLE, aim=AIM_RIFLE,
             grip_loc=(0.0, 0.0, 0.0), grip_rot=_grip_rotation(AIM_RIFLE),
             colour=(0.70, 0.45, 0.95),
             uses_ammo=True, magazine=RIFLE_MAGAZINE, reserve=RIFLE_RESERVE,
             interval=RIFLE_FIRE_INTERVAL, reload_s=RIFLE_RELOAD_SECONDS,
             recoil=0.85, shot_volume=SHOT_VOLUME_CM["Rifle"]),
        # One shot, one kill: 120 against 100 HP, at 0.2 degrees of spread and
        # 200 m of range -- further than anything in a 200 m forest is visible.
        # The cost is 1.6 s between shots, which against a pack of five that
        # runs at 600 cm/s is the difference between opening at distance and
        # being caught reloading.
        dict(path=SNIPER_BP_PATH, parts=_sniper_parts(), muzzle=SNIPER_MUZZLE,
             display="Sniper", automatic=False, damage=120.0, pellets=1, spread=0.2, range=20000.0,
             sound=f"{AUDIO_DIR}/A_SniperFire", reload_sound=SND_RELOAD_PISTOL, aim=AIM_RIFLE,
             grip_loc=(0.0, 0.0, 0.0), grip_rot=_grip_rotation(AIM_RIFLE),
             colour=(0.95, 0.30, 0.35), ads_zoom=COMBAT.ads_zoom_scope, scoped=True,
             uses_ammo=True, magazine=SNIPER_MAGAZINE, reserve=SNIPER_RESERVE,
             interval=SNIPER_FIRE_INTERVAL, reload_s=SNIPER_RELOAD_SECONDS,
             recoil=2.4, shot_volume=SHOT_VOLUME_CM["Sniper"]),
    )


# Which of the five a killed wanderer can be carrying. The starting loadout is
# excluded by construction: a drop the player already has in slot 0 is not a
# reward, and this list is the only thing that decides.
DROP_DISPLAYS = ("SMG", "Rifle", "Sniper")
