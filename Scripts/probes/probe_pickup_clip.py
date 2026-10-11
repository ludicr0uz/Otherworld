"""The reach down: picking an item up off the ground plays the pick-up clip.

The knife is brought to hand (its hold pose is always in the upper-body
slot; a carried gun is lowered and owes none), one of the level's forage
items is laid on the ground in front of the player and the interact key
pressed (InteractForced, as probe_pickup.py presses it). The press must take
the item and, on the same frame, start the skin's pick-up clip (PickUpAnim,
Quaternius UAL2's Farm_Harvest) in the upper-body slot over the knife's
pose; over the next second the right hand must drop well below where it
stood, the clip must end on its own, and the knife's pose come back into the
slot after it (ready_pose.py's keep-alive, which waits for the clip).

Any profile on disk is set aside first, so the game starts on the issued
loadout with room in the bag, and put back at the end.
"""

SYSTEMS = ('inventory',)

import math
import os
import shutil

import unreal

from combat.anim_blueprint import AIM_SLOT
from combat.paths import ITEM_CLASS_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.pickup_tuning import PICKUP_CLIP_START_S
from combat.slot_tuning import MELEE_SLOT
from combat.tuning import INTERACT_RADIUS
from combat.weapon_component.interact import INTERACT_FORCED_VAR
from combat.weapon_component.pickup_clip import PICKUP_ANIM_VAR
from graphics_menu.profile_consts import PROFILE_SLOT

WRITABLE = [(WEAPON_COMP_BP_PATH, INTERACT_FORCED_VAR)]

AHEAD_CM = 120.0       # where the item is laid, in front of the player
DOWN_CM = 60.0         # below the capsule's centre: on the ground
LOOK_DOWN_DEG = -35.0  # the reticle on the ground ahead
SETTLE = 0.2           # game seconds for the aim trace after the view moves
HAND_BONE = "hand_r"
WATCH_S = 1.2          # how long the hand is watched after the press
DROP_CM = 30.0         # how far below its standing height the hand must reach
SAMPLE_S = 0.05
QUIET_S = 3.5          # by when the clip (2.3 s played, blends) has ended


def _file():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames",
                        f"{PROFILE_SLOT}.sav")


def _hand_height(player):
    mesh = player.get_editor_property("mesh")
    return (mesh.get_socket_location(HAND_BONE) - player.get_actor_location()).z


def _playing(mesh, clip):
    anim = mesh.get_anim_instance()
    return bool(anim and clip and anim.is_playing_slot_animation(clip, AIM_SLOT))


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _run(p):
    yield lambda: p.pawn() is not None
    yield 0.3
    player = p.pawn()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    yield lambda: p.get(wc, "Held") is not None
    mesh = player.get_editor_property("mesh")
    clip = p.get(wc, PICKUP_ANIM_VAR)
    p.check("the worn skin has a pick-up clip", clip is not None, str(clip))
    if clip is None:
        return

    def knife_held():
        held = p.get(wc, "Held")
        return held is not None and held.get_class() == p.get(wc, "KnifeClass")

    p.ask_slot(wc, MELEE_SLOT)
    yield lambda: knife_held()
    yield lambda: mesh.get_anim_instance().is_slot_active(AIM_SLOT)
    yield 0.3
    p.check(f"the knife is in hand and its hold pose in {AIM_SLOT}",
            knife_held() and mesh.get_anim_instance().is_slot_active(AIM_SLOT))

    yaw = p.controller().get_control_rotation().yaw
    p.controller().set_control_rotation(
        unreal.Rotator(roll=0.0, pitch=LOOK_DOWN_DEG, yaw=yaw))
    yield SETTLE
    here = player.get_actor_location()
    every = unreal.GameplayStatics.get_all_actors_of_class(
        p.world(), p.load_class(ITEM_CLASS_PATH))
    dropped = [i for i in every if i.get_editor_property("Dropped")]
    for i in dropped:   # forage that happens to lie at the spawn: out of reach
        if (i.get_actor_location() - here).length() < INTERACT_RADIUS:
            i.set_actor_location(here + unreal.Vector(0.0, 0.0, 5000.0), False, True)
    p.check("the level has an item lying in it to lay in front of the player",
            bool(dropped), f"{len(dropped)} found")
    if not dropped:
        return
    item = dropped[0]
    a = math.radians(yaw)
    item.set_actor_location(
        here + unreal.Vector(AHEAD_CM * math.cos(a), AHEAD_CM * math.sin(a), -DOWN_CM),
        False, True)
    yield SETTLE
    standing = _hand_height(player)
    p.check("before the press the clip is not in the slot", not _playing(mesh, clip))

    carried = len(p.get(wc, "Inventory"))
    p.set(wc, INTERACT_FORCED_VAR, True)
    yield lambda: not p.get(wc, INTERACT_FORCED_VAR)
    p.check("the press takes the item", len(p.get(wc, "Inventory")) == carried + 1,
            f"{carried} -> {len(p.get(wc, 'Inventory'))} carried")
    p.check(f"...and the pick-up clip is in {AIM_SLOT} on the frame of the press",
            _playing(mesh, clip))
    anim = mesh.get_anim_instance()
    at = anim.montage_get_position(anim.get_current_active_montage()) if anim else -1.0
    p.check(f"...started {PICKUP_CLIP_START_S:g} s in, where the hand is on its way down",
            PICKUP_CLIP_START_S - 0.05 <= at <= PICKUP_CLIP_START_S + 0.3, f"{at:.2f} s")

    lowest, playing_throughout, t = standing, True, 0.0
    while t < WATCH_S:
        yield SAMPLE_S
        t += SAMPLE_S
        lowest = min(lowest, _hand_height(player))
        playing_throughout = playing_throughout and _playing(mesh, clip)
    p.check(f"the right hand reaches at least {DROP_CM:g} cm below where it stood "
            f"within {WATCH_S:g} s: the reach down to the ground",
            standing - lowest >= DROP_CM,
            f"stood {standing:.0f} cm, lowest {lowest:.0f} cm over the capsule's centre")
    p.check("...and the clip stays in the slot meanwhile: the equip the take runs "
            "and the keep-alive leave it be", playing_throughout)

    yield lambda: not _playing(mesh, clip)
    p.check("the clip ends on its own", not _playing(mesh, clip))
    yield 0.5
    p.check(f"...and the knife's hold pose is back in {AIM_SLOT} after it (the keep-alive)",
            bool(anim) and anim.is_slot_active(AIM_SLOT) and knife_held())
    p.check("the hand is back up", _hand_height(player) > lowest + DROP_CM * 0.5,
            f"{_hand_height(player):.0f} cm")
