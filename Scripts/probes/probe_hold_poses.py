"""The hold poses in the running game: food is carried at the waist, the knife
is held up at the chest, and a pistol is still aimed at eye level.

The probe puts a placed mushroom into the inventory (no key can be injected,
so it writes Inventory, EquippedIndex and NeedsRefresh, as Q's equip does),
then takes the pistol, the mushroom and the knife in hand in turn. Each must
play its own AimPose in the upper-body slot -- A_HoldItem for the mushroom,
A_HoldKnife for the knife -- and the right hand must actually move: lowest
with the mushroom, highest with the pistol, the knife in between.

Any profile on disk is set aside first, so the game starts on the issued
loadout, and put back at the end.
"""

import os
import shutil

import unreal

from combat.anim_blueprint import AIM_SLOT
from combat.paths import (
    HOLD_ITEM_ANIM_PATH, HOLD_KNIFE_ANIM_PATH, ITEM_BP_PATH, WEAPON_COMP_BP_PATH,
    WEAPON_COMP_CLASS_PATH,
)
from combat.skin import SKIN_ADVENTURER, SKIN_QUINN
from graphics_menu.profile_consts import PROFILE_SLOT
from survival.paths import MUSHROOM_CLASS_PATH

WRITABLE = [(WEAPON_COMP_BP_PATH, "EquippedIndex"), (WEAPON_COMP_BP_PATH, "NeedsRefresh"),
            (WEAPON_COMP_BP_PATH, "Inventory"), (ITEM_BP_PATH, "Dropped")]

SETTLE_S = 0.3
APART_CM = 8.0      # how far apart the hand heights must be to count


def _file():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames",
                        f"{PROFILE_SLOT}.sav")


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _take(p, wc, index):
    p.set(wc, "EquippedIndex", index)
    p.set(wc, "NeedsRefresh", True)
    yield lambda: p.get(wc, "Held") == p.get(wc, "Inventory")[index]
    yield SETTLE_S


def _hand_z(player):
    mesh = player.get_editor_property("mesh")
    # player_skin() needs the editor's asset subsystem; read the worn rig.
    bone = next(s.pose_bones["hand_r"] for s in (SKIN_ADVENTURER, SKIN_QUINN)
                if mesh.get_bone_index(s.pose_bones["hand_r"]) >= 0)
    hand = mesh.get_socket_location(bone)
    return hand.z - player.get_actor_location().z


def _run(p):
    yield 0.5
    player = p.pawn()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    mushroom = p.actor_of(MUSHROOM_CLASS_PATH)
    p.check("the player has a weapon component and a mushroom lies in the level",
            wc is not None and mushroom is not None)
    if wc is None or mushroom is None:
        return
    mesh = player.get_editor_property("mesh")
    # A headless game renders nothing, and by default an unrendered mesh
    # never refreshes its bones: every hand would read the same height.
    mesh.set_editor_property(
        "visibility_based_anim_tick_option",
        unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES,
        unreal.PropertyAccessChangeNotifyMode.NEVER)
    anim = mesh.get_anim_instance()
    bag = list(p.get(wc, "Inventory"))
    names = [i.get_class().get_name() for i in bag]
    p.set(mushroom, "Dropped", False)
    p.set(wc, "Inventory", bag + [mushroom])

    heights = {}
    for label, index, want in (("pistol", names.index("BP_Pistol_C"), None),
                               ("mushroom", len(bag), HOLD_ITEM_ANIM_PATH),
                               ("knife", names.index("BP_Knife_C"), HOLD_KNIFE_ANIM_PATH)):
        yield from _take(p, wc, index)
        held = p.get(wc, "Held")
        pose = held.get_editor_property("AimPose") if held else None
        p.check(f"the {label} is in hand and plays its ready pose in {AIM_SLOT}",
                held is not None and held.get_attach_parent_actor() == player
                and anim.is_playing_slot_animation(pose, AIM_SLOT),
                str(pose.get_name() if pose else None))
        if want:
            p.check(f"...which is {want.rsplit('/', 1)[-1]}",
                    pose is not None and pose.get_path_name().split(".")[0] == want,
                    str(pose.get_path_name() if pose else None))
        heights[label] = _hand_z(player)
    p.note(f"right hand above the capsule centre: "
           f"{ {k: round(v, 1) for k, v in heights.items()} }")
    p.check("the mushroom is carried low, the knife higher, the pistol aimed highest",
            heights["mushroom"] + APART_CM < heights["knife"]
            and heights["knife"] + APART_CM < heights["pistol"],
            str({k: round(v, 1) for k, v in heights.items()}))
