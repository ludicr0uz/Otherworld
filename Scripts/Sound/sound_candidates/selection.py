"""The selection: which takes were chosen for which use, after listening.

One row per use of a sound in the game. The takes are candidate names
(`assets/generated/sound_candidates/<take>.wav`), picked from the ratings
given on the audition page: the great ones, and the ok ones where a sound
needs more takes than there were great ones.

A row's `status` says where it stands:

  GAME    the game plays it: `install.py` writes its takes to
          `assets/generated/sounds/<asset>_NN.wav`, which the builders import
  READY   chosen, and nothing in the game plays it yet
  FUTURE  a good sound for something the game does not have yet; the note
          says what, in the words written on the audition page

`asset` is the SoundWave name the game knows the sound by. A row with one
take is `<asset>.wav`; with several, `<asset>_01.wav` and on.

A row whose sound is put together from several takes (a reload is a magazine
out, a magazine in and a bolt) has a `recipe`: `(take, start in seconds)`.
The recipes were laid out by each take's length, not by ear: they are the
first thing to listen to.

Pure Python: the builders import the asset tables from here.
"""

import dataclasses

GAME, READY, FUTURE = "in game", "ready, not wired", "future"

FS = "freesound"   # previews: an MP3, to be replaced by the original


@dataclasses.dataclass(frozen=True)
class Use:
    key: str
    category: str
    label: str
    takes: tuple = ()
    status: str = READY
    asset: str = ""
    note: str = ""
    recipe: tuple = ()
    peak: float = 0.0       # 0 keeps the candidate's own level
    seconds: float = 0.0    # 0 keeps the candidate's own length
    stereo: bool = False


def _n(stem, *numbers):
    return tuple(f"{stem}_{i:02d}" for i in numbers)


# The gun in the player's hands. The shots picked on the audition page from
# real guns recorded close (manifest_guns.py): "great shotgun sound, use this
# one", "great pistol sound", "good for uzi", the AKM "worth trying". No
# sniper among them was liked (the Remington clips), so the sniper keeps the
# shot the game had from 26 September, as the rest did until these.
WEAPONS = (
    Use("shotgun_shot", "weapons", "shotgun shot", ("gunshots/shotgun/ts_slug_near_01",), GAME,
        "A_ShotgunFire"),
    Use("pistol_shot", "weapons", "pistol shot", ("gunshots/pistol/glock18_near_02",), GAME,
        "A_PistolFire"),
    Use("smg_shot", "weapons", "SMG shot", ("gunshots/smg/mini_uzi_near_02",), GAME, "A_SMGFire"),
    Use("rifle_shot", "weapons", "rifle shot", ("gunshots/rifle/akm_near_02",), GAME, "A_RifleFire"),
    Use("sniper_shot", "weapons", "sniper shot", ("weapons/backup_sep26_sniper",), GAME, "A_SniperFire"),
    Use("shots_spare", "weapons", "other shots that were liked",
        ("gunshots/pistol/glock18_near_01", "gunshots/pistol/beretta93r_near_02",
         "gunshots/smg/mini_uzi_near_01", "gunshots/rifle/akm_near_01",
         "gunshots/shotgun/usas12_near_02", "weapons/backup_sep26_shotgun",
         "weapons/backup_sep26_smg", "weapons/backup_sep26_rifle"), READY,
        note="the second take of each gun picked, and the 26 September shots they replaced"),
    Use("dry_fire", "weapons", "dry fire", ("weapons/dry_fire_metal_latch_01",), GAME, "A_DryFire"),
    # The first set's too: the pump cocked, one take.
    Use("shotgun_reload", "weapons", "shotgun reload: the pump", ("weapons/original_reload_shotgun",),
        GAME, "A_ReloadShotgun"),
    Use("rifle_reload", "weapons", "rifle and SMG reload: magazine out, magazine in, bolt", (), GAME,
        "A_ReloadRifle", peak=0.9, recipe=(
            ("weapons/handling_rifle_mag_01", 0.00), ("weapons/handling_rifle_mag_03", 0.65),
            ("weapons/handling_shotgun_cock_02", 1.15))),
    Use("pistol_reload", "weapons", "pistol and sniper reload: magazine out, in, slide", (), GAME,
        "A_ReloadPistol", peak=0.9, recipe=(
            ("weapons/handling_rifle_mag_05", 0.00), ("weapons/handling_rifle_mag_06", 0.40),
            ("weapons/handling_smg_cock_dry_01", 0.85))),
    Use("shots_distant", "weapons", "each gun heard from beyond 100 m: a nearer take and a farther",
        ("weapons/shotgun_near", "weapons/shotgun_far", "weapons/pistol_near", "weapons/pistol_far",
         "weapons/smg_near", "weapons/smg_far", "weapons/rifle_near", "weapons/rifle_far",
         "weapons/sniper_near", "weapons/sniper_far", "weapons/shotgun_alt_near",
         "weapons/original_shotgun", "weapons/original_pistol", "weapons/original_smg",
         "weapons/original_rifle", "weapons/original_sniper", "gunshots/smg/mini_uzi_far_01"), READY,
        note="within 100 m, and in the player's own hands, a gun is its shot above. Nothing "
             "fires from farther yet: only the player shoots, and no sound carries past 100 m"),
    Use("shotgun_reload_spare", "weapons", "a shotgun reload from real handling: three shells, the action",
        _n("weapons/shotgun_shell_load", 1, 2, 3) + ("weapons/handling_shotgun_cock_01",), READY,
        note="put together and tried in the game, and turned down for the first set's pump"),
    Use("handling_spare", "weapons", "gun handling, the takes no reload uses",
        _n("weapons/handling_rifle_mag", 2, 4, 7, 8) + _n("weapons/handling_shotgun_cock", 3, 4, 5, 6)
        + _n("weapons/handling_smg_cock_dry", 2, 3, 4, 5, 6, 7, 8) + ("weapons/shotgun_pump_01",),
        READY, note="for a gun brought to hand, put away, or aimed"),
)

FOOTSTEPS = (
    Use("footsteps", "footsteps", "footsteps on the forest floor",
        _n("footsteps/leaves2_walk", 5, 7, 8, 9, 10, 11), GAME, "A_Footstep"),
    Use("footsteps_run", "footsteps", "running", _n("footsteps/leaves2_run", 5, 6), READY,
        note="the game has one footstep sound for every speed"),
    Use("footsteps_grass", "footsteps", "footsteps on grass", _n("footsteps/grass2_walk", 3, 5, 7, 10, 11),
        READY, note="the game does not tell one surface from another"),
    Use("footsteps_dirt", "footsteps", "footsteps on bare ground",
        _n("footsteps/dirt_walk", 1, 2, 3, 4, 5, 6), READY,
        note="the game does not tell one surface from another"),
    Use("footsteps_monster", "footsteps", "a wanderer's footsteps", _n("footsteps/dirt_walk", 1, 2, 3, 4, 5, 6),
        GAME, "A_MonsterFootstep",
        note="the bare-ground takes: heavier than the player's own leaves, so a wanderer "
             "running up is told from one's own feet. Not picked by ear for this use yet"),
    Use("land", "footsteps", "landing from a jump", ("footsteps/dirt_land_02",), READY),
    Use("grass_rustle", "footsteps", "moving through tall grass", _n("footsteps/grass_rustle", 1, 2, 3, 4, 5, 6),
        GAME, "A_GrassRustle", note="a footfall inside a bush, the player's or a wanderer's"),
)

AMBIENCE = (
    Use("ambience_day", "ambience", "the day bed: birds",
        ("ambience/day_birds",), GAME, "A_Amb_DayBirds", stereo=True),
    Use("ambience_wind", "ambience", "the wind, day and night",
        ("ambience/wind_grass_norway",), GAME, "A_Amb_Wind", stereo=True,
        note="not a good match: in the game and silent by default (volume 0 on the "
             "SOUND SETTINGS tab) until a better wind is found"),
    Use("ambience_night", "ambience", "the night bed: crickets and owls",
        ("ambience/night_crickets_owls",), GAME, "A_Amb_Night", stereo=True),
    Use("ambience_night_spare", "ambience", "other nights",
        ("ambience/night", "ambience/night_crickets_connecticut", "ambience/night_crickets_gusts",
         "ambience/night_crickets_quiet", "ambience/night_owl_river_distant",
         "ambience/north_woods_night_wolves", "ambience/wind_calm"), READY,
        note="for a second forest, or a night that changes as it goes on"),
)

FIRE = (
    Use("campfire", "fire", "a campfire burning", ("fire/campfire_medium",), GAME, "A_Campfire"),
    Use("match", "fire", "a match struck", _n("fire/match", 1, 7, 9, 13), GAME, "A_Match"),
    Use("fire_spare", "fire", "other fires", ("fire/fire_big", "fire/campfire_small",
                                             f"{FS}/match_strike/398448_brachern"), READY,
        note="the big fire for a bonfire; the small one for the burning stick"),
)

CREATURES = (
    Use("wendigo_roar", "creatures", "the wendigo's roar",
        _n("creatures/wendigo/troll_roar", 1, 2, 4, 5, 6), GAME, "A_WendigoRoar"),
    Use("wendigo_spare", "creatures", "the wendigo: growl, hurt, death, other roars",
        ("creatures/wendigo/troll2_growl_01", "creatures/wendigo/troll2_hurt_01",
         "creatures/wendigo/troll2_death_01", "creatures/wendigo/troll_roar_03",
         "creatures/wendigo/deep_roar_01", "creatures/wendigo/herbivore_roar_01",
         f"{FS}/zombie_hurt/784771_pdfpxf520"), READY,
        note="one take each of growl, hurt and death: too few to play every time"),
    Use("zombie_growl", "creatures", "the zombie's growl",
        _n("creatures/zombie/monster", 3, 6, 2, 5, 12) + _n("creatures/zombie/infected_vocal", 2, 3, 5, 7)
        + _n("creatures/zombie/zombie_groan", 2, 3), GAME, "A_ZombieGrowl"),
    Use("zombie_attack", "creatures", "the zombie's bite and swing",
        ("creatures/zombie/creature_attack_01", "creatures/zombie/monster_bite_01")
        + _n("creatures/zombie/infected_bite", 1, 2, 3, 4), READY),
    Use("zombie_hurt_death", "creatures", "the zombie hurt, and dying",
        ("creatures/zombie/creature_pain_01", f"{FS}/zombie_hurt/506514_LilMati",
         "creatures/zombie/pain_death_01", f"{FS}/zombie_death/754441_OwNathan"), READY,
        note="two takes each"),
)

PLAYER = (
    Use("player_hit", "player", "the player hit",
        _n("player/hit", 5, 8, 1, 2, 3, 4) + ("player/pain_07", "player/pain_grunt_01"), GAME,
        "A_PlayerHit"),
    Use("player_death", "player", "the player dying", ("player/pain_shout_01",), GAME, "A_PlayerDeath"),
    Use("player_effort", "player", "the player's effort: a swing, a throw",
        _n("player/effort", 1, 2, 3, 4, 5, 6) + _n("player/attack", 1, 2, 6), READY),
    Use("player_breath", "player", "out of breath: the run key held with no stamina left",
        ("player/breath_fast_01",), GAME, "A_PlayerBreath"),
    Use("player_breath_spare", "player", "out of breath, the other takes",
        ("player/breath_fast_03", "player/gasp_04", "player/gasp_05"), READY),
    Use("player_land", "player", "the player's grunt on landing", _n("player/land", 1, 2, 4), READY),
    # The take is 56 s and speeds up. Its first 6.5 s are steady, a beat every
    # 1.64 s: four beats, played again as they end (sound_world.HEARTBEAT_S).
    # Mono: it is played at the player, and a stereo wave cannot be placed.
    Use("heartbeat", "player", "low health", ("player/heartbeat_panic_01",), GAME, "A_Heartbeat",
        note="cut to its first four beats; turned down by its volume row", seconds=6.5),
    Use("eating", "player", "eating food", (f"{FS}/eating/718593_JoMungus",), GAME, "A_Eating",
        note="a preview"),
    Use("drinking", "player", "drinking water", (f"{FS}/drinking/674543_laboratoriosonoridades2022",),
        READY, note="rated ok, and a preview"),
)

MELEE = (
    Use("melee_hit", "melee", "a blow landing", _n("melee/punch_body", 1, 2, 3, 4) + ("melee/punch_wet_01",),
        GAME, "A_MeleeHit"),
    Use("melee_swing", "melee", "a swing through the air", _n("melee/swing", 1, 4, 2, 3, 5, 6, 7, 8), GAME,
        "A_MeleeSwing"),
    Use("blade_hit", "melee", "a knife or an axe landing on a body",
        ("melee/stab_dagger_05",), GAME, "A_BladeHit",
        note="the stab alone, for now: the gore takes were too gory for every blow"),
    Use("blade_lodge", "melee", "a thrown knife or axe sticking in a body", ("melee/stab_dagger_05",), GAME,
        "A_BladeLodge", note="the stab too, for now; in a tree, it is the axe's chop"),
    Use("axe_head_kill", "melee", "a thrown axe killing with a blow to the head", ("melee/gore_weapon_02",),
        GAME, "A_AxeHeadKill", note="the 1.9 s take"),
    Use("blade_gore_spare", "melee", "the gory takes a blade's blow had", ("melee/blood_splat_01", "melee/gore_02"),
        READY, note="too gory for an ordinary blow"),
    # Told apart by ear in the game: these five are a blunt thing thrown, and
    # the knife's swing is a sharp one.
    Use("throw", "melee", "a blunt item thrown, as it leaves the hand",
        _n("melee/swing", 9, 10, 11, 12, 13), GAME, "A_Throw"),
    Use("throw_sharp", "melee", "a knife or an axe thrown, as it leaves the hand",
        ("melee/knife_swing_01",), GAME, "A_ThrowSharp"),
    Use("swing_thud", "melee", "a heavy swing and its thud", _n("melee/swing_thud", 6, 1, 5), READY),
)

IMPACTS = (
    Use("bullet_wood", "impacts", "a bullet into wood", _n("impacts/bullet_wood", 1, 2, 3, 4, 5), READY),
    Use("bullet_body", "impacts", "a bullet into a body", ("impacts/bullet_body_01",), READY),
    Use("bullet_dirt", "impacts", "a bullet into the ground", ("impacts/bullet_dirt_01",), READY),
    Use("axe_chop", "impacts", "the axe on a tree",
        ("impacts/axe_wood_01", "impacts/axe_wood_05", "impacts/axe_wood_03"), GAME, "A_AxeChop"),
    Use("axe_chop_spare", "impacts", "another axe", (f"{FS}/axe_chop/536736_egomassive",), READY,
        note="rated great, and a preview"),
    Use("wood_piece", "impacts", "a piece of wood coming off the tree", ("impacts/branch_crush_01",), READY),
)

INVENTORY = (
    # Handling: what an item sounds like as it is moved between slots or
    # brought to hand, by its type (sound_items.ITEM_HANDLING).
    Use("handle_item", "inventory", "an item handled: moved in the inventory, brought to hand",
        ("inventory/grab_pickup_01", "inventory/backpack_pickup_01"), GAME, "A_HandleItem",
        note="also the takes for an item picked up, which nothing plays yet"),
    Use("drop", "inventory", "an item set down", ("inventory/drop_01", "inventory/backpack_drop_01"), READY),
    Use("handle_cloth", "inventory", "a garment handled, put on or taken off",
        _n("inventory/cloth", 2, 1, 3, 4), GAME, "A_HandleCloth"),
    Use("wear_spare", "inventory", "a coat picked up", ("inventory/coat_pickup_01",), READY,
        note="13 s: too long to play on a move"),
    Use("handle_gun", "inventory", "a gun handled or brought to hand",
        ("inventory/leather_01", "inventory/leather_02") + _n("inventory/belt", 1, 2), GAME, "A_HandleGun"),
    Use("handle_blade", "inventory", "a knife or an axe handled or drawn",
        ("inventory/knife_draw_01", "inventory/knife_draw_03"), GAME, "A_HandleBlade"),
)

UI = (
    Use("ui", "menu", "the menu: move, take, back, error, switch",
        ("ui/rollover_01", "ui/click_03", f"{FS}/ui_soft_click/477640_Joao_Janz", "ui/select_01",
         "ui/menu_confirm_01", "ui/back_03", "ui/error_02", "ui/switch_01", "ui/drop_01"), READY),
    Use("ui_open", "menu", "the menu opening and closing",
        (f"{FS}/ui_page/437121_mosaichorse", f"{FS}/ui_page/667180_MBPL"), READY,
        note="rated ok, and previews"),
)

STINGERS = (
    Use("title", "stingers", "the title screen", ("stingers/trailer_boom_01",), READY, stereo=True),
    Use("stingers", "stingers", "a scare: the wendigo has seen you",
        ("stingers/noise_box_hit_01", "stingers/noise_box_hit_02", "stingers/jumpscare_whisper_01"), READY,
        stereo=True),
    Use("tension", "stingers", "a bed under a hunt", (f"{FS}/tension_dark_ambient/560618_szegvari",), READY,
        note="rated ok, and a preview", stereo=True),
)

LATER = (
    Use("revolver", "for later", "a revolver", ("gunshots/pistol/designed_revolver_near_01",), FUTURE),
    Use("dog_monster", "for later", "a growling, dog-like monster",
        _n("creatures/wendigo/monster_growl", 1, 2, 3, 4, 5) + ("creatures/wendigo/roar_growl_01",
                                                               f"{FS}/wolf_howl/420449_Mrthenoronha"), FUTURE),
    Use("ghosts", "for later", "ghosts, and a ghost boss",
        ("stingers/bedlam_01", "stingers/bedlam_04", "stingers/eerie_passby_01",
         "tension/distorted_perception_01", "tension/drone_swirling_wind", "tension/growl_entity_drone",
         f"{FS}/tension_dark_ambient/607205_Fupicat"), FUTURE, stereo=True),
    Use("tribe", "for later", "a tribe", (f"{FS}/tension_dark_ambient/596463_szegvari",), FUTURE, stereo=True),
    Use("finishers", "for later", "finishing moves, a mace",
        ("melee/chop_flesh_01", "melee/chop_flesh_02", "melee/gore_04", "melee/stab_01", "melee/gore_03"),
        FUTURE),
    Use("crafting", "for later", "bandages, skinning a rabbit, building",
        ("melee/crunch_rip_01", "melee/gore_01", "impacts/log_fall_01"), FUTURE),
    Use("blood_steps", "for later", "walking on blood", ("melee/splatter_01",), FUTURE),
    Use("food_items", "for later", "an apple, crackers, a sip",
        ("player/eating_apple_01", "player/eating_crunch_01", f"{FS}/eating/699846_8bitmyketison",
         "player/drinking_sip_01"), FUTURE),
    Use("creaky_house", "for later", "a creaky house",
        (f"{FS}/tree_creak/797992_Comradar", f"{FS}/tree_creak/797993_Comradar",
         f"{FS}/tree_creak/797994_Comradar", f"{FS}/tree_creak/94359_Ryding"), FUTURE),
)

USES = (WEAPONS + FOOTSTEPS + AMBIENCE + FIRE + CREATURES + PLAYER + MELEE + IMPACTS + INVENTORY + UI
        + STINGERS + LATER)
BY_KEY = {use.key: use for use in USES}


def asset_names(key):
    """The SoundWave names a GAME row installs: `A_Footstep_01` and on, or the
    bare name for a row with one sound."""
    use = BY_KEY[key]
    count = 1 if use.recipe else len(use.takes)
    if count == 1:
        return (use.asset,)
    return tuple(f"{use.asset}_{i:02d}" for i in range(1, count + 1))
