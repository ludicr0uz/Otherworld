"""The weapons' sounds: each gun's shot and reload, the dry click, and what a
fist or a blade does -- a swing, a blow on a body, a thrown blade leaving the
hand and going in.

SOUNDS is the area's rows of the sound table and BINDINGS where each is played
from. A gun's are three variables of its own item Blueprint (the graphs read
them off Held, so a new weapon is a row: weapon_component/firing.py, ammo.py);
the rest are arrays of takes on BP_WeaponComponent, one drawn per play
(Sound/play.py):

    SwingSounds       a punch, a slash, an axe swing: as the clip starts, at
                      the player (punch._author_swing)
    PunchHitSounds    a fist landing on a body: at the hit (punch._author_blow)
    BladeHitSounds    a knife or an axe landing on a body: at the hit (the same
                      blow, on the knife's Strike)
    ThrowSharpSounds  a Melee item (the knife, the axe) thrown, as it leaves
                      the hand (throw.py)
    LodgeSounds       a thrown blade going into a body: at the wound
                      (throw_strike.py)
    HeadKillSounds    in LodgeSounds' place, where a thrown axe (an item
                      that Chops) kills with a blow to the head

To give a gun another shot or reload, change its row of GUN_SOUNDS and run
Scripts/build_sound.py: no other build is needed.
"""

from combat import item_vars as IV
from combat.paths import (
    PISTOL_BP_PATH, RIFLE_BP_PATH, SHOTGUN_BP_PATH, SMG_BP_PATH, SNIPER_BP_PATH,
    WEAPON_COMP_BP_PATH)
from combat.weapon_component import vars as WV
from Sound.sound_def import (
    ATT_CREATURE, ATT_FOLEY, ATT_GUNFIRE, WEAPON_AUDIO_DIR, Binding, Sound, takes)


def _gun(key, label, name, attenuation):
    """A sound of the guns' own folder: one wave, named here."""
    return Sound(key, label, (name,), attenuation, folder=WEAPON_AUDIO_DIR)


# A gunshot is heard across the map and a magazine change is not: the two
# halves carry different distances.
SHOTGUN_SHOT = _gun("shotgun_shot", "shotgun shot", "A_ShotgunFire", ATT_GUNFIRE)
PISTOL_SHOT = _gun("pistol_shot", "pistol shot", "A_PistolFire", ATT_GUNFIRE)
SMG_SHOT = _gun("smg_shot", "SMG shot", "A_SMGFire", ATT_GUNFIRE)
RIFLE_SHOT = _gun("rifle_shot", "rifle shot", "A_RifleFire", ATT_GUNFIRE)
SNIPER_SHOT = _gun("sniper_shot", "sniper shot", "A_SniperFire", ATT_GUNFIRE)

# The mechanical sounds. All of these, and the five gunshots, are cut from
# recordings of real firearms. Which take each one is was chosen by ear on the
# audition page, and Scripts/Sound/install_selected_sounds.py writes the WAVs
# (assets/generated/sounds/SELECTED.md says what each was cut from).
#
# The click stays SHARED by all five weapons: a hammer falling on an empty
# chamber genuinely is the same noise in every receiver, and five copies would
# be five things to keep in step for no audible gain.
#
# The reload does NOT, and that is the one thing the real recordings changed
# about the shape of this data. When it was a synthesised clack, one sound for
# five weapons was defensible because none of them sounded like anything in
# particular. A pump shotgun, a magazine swap and a hand-fed reload are three
# different actions that take three different lengths of time, and the weapon
# already carried a per-weapon ReloadSound slot -- so which one to play is now
# a column in _weapon_specs() like every other difference between guns.
DRY_FIRE = _gun("dry_fire", "dry fire", "A_DryFire", ATT_FOLEY)
SHOTGUN_RELOAD = _gun("shotgun_reload", "shotgun reload", "A_ReloadShotgun", ATT_FOLEY)  # 0.47 s -- a pump cocked
RIFLE_RELOAD = _gun("rifle_reload", "rifle reload", "A_ReloadRifle", ATT_FOLEY)   # 1.56 s -- mag out, mag in, bolt
PISTOL_RELOAD = _gun("pistol_reload", "pistol reload", "A_ReloadPistol", ATT_FOLEY)   # 1.58 s -- slower, hand-fed

# A fist and a blade. The blows carry as a creature's voice does; the wanderers'
# blow on the player is the fist's thud too (sound_monsters.py).
MELEE_SWING = Sound("melee_swing", "melee swing", takes("melee_swing"), ATT_FOLEY)
MELEE_HIT = Sound("melee_hit", "melee hit", takes("melee_hit"), ATT_CREATURE)
BLADE_HIT = Sound("blade_hit", "blade hit", takes("blade_hit"), ATT_CREATURE)
BLADE_LODGE = Sound("blade_lodge", "thrown blade in a body", takes("blade_lodge"), ATT_CREATURE)
THROW_SHARP = Sound("throw_sharp", "blade throw", takes("throw_sharp"), ATT_FOLEY)
# The one gory take left: a thrown axe that kills with a blow to the head.
AXE_HEAD_KILL = Sound("axe_head_kill", "axe head kill", takes("axe_head_kill"), ATT_CREATURE)

SOUNDS = (SHOTGUN_SHOT, PISTOL_SHOT, SMG_SHOT, RIFLE_SHOT, SNIPER_SHOT, DRY_FIRE,
          SHOTGUN_RELOAD, RIFLE_RELOAD, PISTOL_RELOAD, MELEE_SWING, MELEE_HIT, BLADE_HIT,
          BLADE_LODGE, THROW_SHARP, AXE_HEAD_KILL)

# Retiring A_Reload (the single shared synthesised clack) is deliberate and is
# handled by retire_old_assets(): a builder that simply stops referencing an
# asset leaves it on disk forever.
RETIRED_SOUNDS = (f"{WEAPON_AUDIO_DIR}/A_Reload",)

# Each gun's (shot, reload): the gun's Blueprint, its FireSound and ReloadSound.
GUN_SOUNDS = {
    SHOTGUN_BP_PATH: (SHOTGUN_SHOT, SHOTGUN_RELOAD),
    PISTOL_BP_PATH: (PISTOL_SHOT, PISTOL_RELOAD),
    SMG_BP_PATH: (SMG_SHOT, RIFLE_RELOAD),
    RIFLE_BP_PATH: (RIFLE_SHOT, RIFLE_RELOAD),
    SNIPER_BP_PATH: (SNIPER_SHOT, PISTOL_RELOAD),
}

BINDINGS = tuple(
    row for gun, (shot, reload) in GUN_SOUNDS.items() for row in (
        Binding(gun, IV.FireSound, shot, single=True),
        Binding(gun, IV.DryFireSound, DRY_FIRE, single=True),
        Binding(gun, IV.ReloadSound, reload, single=True))
) + (
    Binding(WEAPON_COMP_BP_PATH, WV.SwingSounds, MELEE_SWING),
    Binding(WEAPON_COMP_BP_PATH, WV.PunchHitSounds, MELEE_HIT),
    Binding(WEAPON_COMP_BP_PATH, WV.BladeHitSounds, BLADE_HIT),
    Binding(WEAPON_COMP_BP_PATH, WV.LodgeSounds, BLADE_LODGE),
    Binding(WEAPON_COMP_BP_PATH, WV.ThrowSharpSounds, THROW_SHARP),
    Binding(WEAPON_COMP_BP_PATH, WV.HeadKillSounds, AXE_HEAD_KILL),
)


def fire_sound(gun):
    """The gun's shot, as an asset path (weapon_specs' ``sound`` column)."""
    return GUN_SOUNDS[gun][0].paths[0]


def reload_sound(gun):
    """The gun's reload, as an asset path (weapon_specs' ``reload_sound``)."""
    return GUN_SOUNDS[gun][1].paths[0]
