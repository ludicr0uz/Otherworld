"""The guns' tunable numbers as plain data: every column of the GUN SETTINGS
page (gun_tuning.TUNE_STATS) a gun has, its default here and its cell of
gun_tuning.csv over it.

    GUN_DEFAULTS   damage, pellets, range, fire interval, reload, magazine and
                   how far the shot is heard, per gun
    GUN_ACCURACY   the cloud and the recoil, per gun
    gun_row()      one gun's row as it is built: the two above, the defaults
                   every gun shares (zoom, throw arc, sway), then the CSV

weapon_specs._weapon_specs() lays gun_row() over each of its rows, so a number
here or in the CSV is the number BP_<Gun> is built with. Pure Python (no unreal
import), which weapon_specs is not: dev/tests/test_weapon_tuning.py holds every
row to the CSV without an editor.
"""

from combat.gun_tuning import read_table
from combat.sway_tuning import SWAY_RATE, SWAY_RATE_COLUMN
from combat.throw_tuning import THROW_PITCH_COLUMN, THROW_PITCH_UP_DEG
from combat.tuning import (
    COMBAT, PISTOL_FIRE_INTERVAL, PISTOL_MAGAZINE, PISTOL_RELOAD_SECONDS,
    RIFLE_FIRE_INTERVAL, RIFLE_MAGAZINE, RIFLE_RELOAD_SECONDS,
    SHOTGUN_FIRE_INTERVAL, SHOTGUN_MAGAZINE, SHOTGUN_RELOAD_SECONDS,
    SHOT_VOLUME_CM, SMG_FIRE_INTERVAL, SMG_MAGAZINE, SMG_RELOAD_SECONDS,
    SNIPER_FIRE_INTERVAL, SNIPER_MAGAZINE, SNIPER_RELOAD_SECONDS,
)

# What a gun does to what it hits and how often, by DisplayName. The notes on
# why each is what it is are beside its row in weapon_specs._weapon_specs().
# `shot_volume` is read from SHOT_VOLUME_CM in tuning.py rather than written
# inline, because the five only mean something against each other.
GUN_DEFAULTS = {
    "Shotgun": dict(damage=18.0, pellets=8, range=4000.0, magazine=SHOTGUN_MAGAZINE,
                    interval=SHOTGUN_FIRE_INTERVAL, reload_s=SHOTGUN_RELOAD_SECONDS,
                    shot_volume=SHOT_VOLUME_CM["Shotgun"]),
    "Pistol":  dict(damage=26.0, pellets=1, range=6000.0, magazine=PISTOL_MAGAZINE,
                    interval=PISTOL_FIRE_INTERVAL, reload_s=PISTOL_RELOAD_SECONDS,
                    shot_volume=SHOT_VOLUME_CM["Pistol"]),
    "SMG":     dict(damage=12.0, pellets=1, range=4500.0, magazine=SMG_MAGAZINE,
                    interval=SMG_FIRE_INTERVAL, reload_s=SMG_RELOAD_SECONDS,
                    shot_volume=SHOT_VOLUME_CM["SMG"]),
    "Rifle":   dict(damage=24.0, pellets=1, range=9000.0, magazine=RIFLE_MAGAZINE,
                    interval=RIFLE_FIRE_INTERVAL, reload_s=RIFLE_RELOAD_SECONDS,
                    shot_volume=SHOT_VOLUME_CM["Rifle"]),
    # The one gun with a scope: its zoom is the scope's, not the irons'.
    "Sniper":  dict(damage=120.0, pellets=1, range=20000.0, magazine=SNIPER_MAGAZINE,
                    interval=SNIPER_FIRE_INTERVAL, reload_s=SNIPER_RELOAD_SECONDS,
                    shot_volume=SHOT_VOLUME_CM["Sniper"],
                    ads_zoom=COMBAT.ads_zoom_scope),
}


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
assert tuple(GUN_ACCURACY) == tuple(GUN_DEFAULTS)


def gun_row(display, tuned=None):
    """{column: value} for every tunable column of the gun ``display``: its
    defaults with gun_tuning.csv's cells over them. ``tuned`` is a table
    already read (gun_tuning.read_table()); a gun with no row there, or a
    cell it lacks, keeps the default."""
    tuned = read_table() if tuned is None else tuned
    row = dict(GUN_DEFAULTS[display])
    row.update(GUN_ACCURACY[display])
    row.setdefault("ads_zoom", COMBAT.ads_zoom_irons)
    row.setdefault("ads_zoom_speed", COMBAT.ads_interp_speed)
    row.setdefault("ads_zoom_in_s", COMBAT.ads_zoom_in_s)
    row.setdefault("ads_raise_s", COMBAT.ads_raise_s)
    row.setdefault(THROW_PITCH_COLUMN, THROW_PITCH_UP_DEG)
    row.setdefault(SWAY_RATE_COLUMN, SWAY_RATE)
    row.update(tuned.get(display, {}))
    return row
