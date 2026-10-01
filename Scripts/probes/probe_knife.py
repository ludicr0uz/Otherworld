"""The knife: issued at the start, taken in hand, and slashed at a wanderer.

The player must start carrying BP_Knife. The probe equips it the way Q does
(EquippedIndex + NeedsRefresh), then writes KnifeQueued, which is all the
press gate does (no key can be injected into a headless game; verify/knife.py
checks the gate). A wanderer in front must see the slash clip play in the
upper-body slot and lose COMBAT.knife_damage when the blow lands, and the
knife's ready pose must come back once the clip is done.

Any profile on disk is set aside first, so the game starts on the issued
loadout, and put back at the end.
"""

import os
import shutil

import unreal

from combat.anim_blueprint import AIM_SLOT
from combat.paths import (
    HEALTH_BP_PATH, HEALTH_CLASS_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH,
)
from combat.tuning import COMBAT
from combat.weapon_component.knife import (
    KNIFE_ANIM_VAR, KNIFE_PENDING_VAR, KNIFE_QUEUED_VAR, NEXT_KNIFE_VAR,
)
from graphics_menu.profile_consts import PROFILE_SLOT

WRITABLE = [(WEAPON_COMP_BP_PATH, "EquippedIndex"), (WEAPON_COMP_BP_PATH, "NeedsRefresh"),
            (WEAPON_COMP_BP_PATH, KNIFE_QUEUED_VAR), (HEALTH_BP_PATH, "Health")]

IN_FRONT_CM = 100.0   # capsule centre to capsule centre: inside the reach
KNIFE = "BP_Knife_C"


def _file():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames",
                        f"{PROFILE_SLOT}.sav")


def _wanderer(p):
    ctrls = unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.AIController)
    pawns = [c.get_controlled_pawn() for c in ctrls
             if "ForestWandererAI" in c.get_class().get_name()]
    return next((x for x in pawns if x is not None), None)


def _place(npc, player):
    spot = player.get_actor_location() + player.get_actor_forward_vector() * IN_FRONT_CM
    npc.set_actor_location(spot, False, True)


def _held_name(p, wc):
    held = p.get(wc, "Held")
    return held.get_class().get_name() if held else None


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
    yield lambda: _wanderer(p) is not None
    yield 0.5
    player, npc = p.pawn(), _wanderer(p)
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    health = p.component(npc, HEALTH_CLASS_PATH)
    p.check("the player has a weapon component and a wanderer has health",
            wc is not None and health is not None)
    if wc is None or health is None:
        return

    bag = [i.get_class().get_name() for i in p.get(wc, "Inventory")]
    p.check("the knife is issued with the shotgun and the pistol (then the axe and the matches)",
            bag == ["BP_Shotgun_C", "BP_Pistol_C", KNIFE, "BP_Axe_C", "BP_Matches_C"],
            str(bag))
    p.check("...and the shotgun is what is held at the start",
            _held_name(p, wc) == "BP_Shotgun_C", str(_held_name(p, wc)))
    if KNIFE not in bag:
        return

    p.set(wc, "EquippedIndex", bag.index(KNIFE))
    p.set(wc, "NeedsRefresh", True)
    yield lambda: _held_name(p, wc) == KNIFE
    knife = p.get(wc, "Held")
    p.check("equipped like any item, the knife is in hand",
            knife is not None and knife.get_attach_parent_actor() == player
            and not knife.get_editor_property("hidden"), str(knife.get_attach_parent_actor()))
    anim = player.get_editor_property("mesh").get_anim_instance()
    pose = knife.get_editor_property("AimPose")
    yield 0.2
    p.check("...in its ready pose (A_HoldKnife)",
            anim is not None and anim.is_playing_slot_animation(pose, AIM_SLOT))

    p.set(health, "Health", 100.0)
    _place(npc, player)
    yield 0.05
    _place(npc, player)
    before = p.get(health, "Health")
    t0 = unreal.GameplayStatics.get_time_seconds(p.world())
    p.set(wc, KNIFE_QUEUED_VAR, True)

    yield lambda: not p.get(wc, KNIFE_QUEUED_VAR)
    clip = p.get(wc, KNIFE_ANIM_VAR)
    p.check("the swing takes the queued slash",
            not p.get(wc, KNIFE_QUEUED_VAR) and p.get(wc, KNIFE_PENDING_VAR))
    p.check(f"...and plays A_KnifeSlash in {AIM_SLOT}",
            clip is not None and anim.is_playing_slot_animation(clip, AIM_SLOT),
            str(anim.get_current_active_montage()))
    p.check("...and stamps the knife's cooldown",
            abs(p.get(wc, NEXT_KNIFE_VAR) - t0 - COMBAT.knife_interval_s) < 0.2,
            f"{p.get(wc, NEXT_KNIFE_VAR):.2f} at t0 {t0:.2f}")
    p.check("the blow has not landed before the cut",
            abs(p.get(health, "Health") - before) < 1e-3, f"{p.get(health, 'Health')}")

    _place(npc, player)
    yield lambda: not p.get(wc, KNIFE_PENDING_VAR)
    after = p.get(health, "Health")
    p.check(f"the blow takes {COMBAT.knife_damage:.0f} HP off the wanderer in front",
            abs((before - after) - COMBAT.knife_damage) < 1e-3, f"{before} -> {after}")
    p.check("...and credits the player", p.get(health, "DamagedByPlayer") is True)
    p.check("...and the knife is still in hand (a slash spends nothing)",
            p.get(wc, "Held") == knife)

    yield lambda: anim.is_playing_slot_animation(pose, AIM_SLOT)
    p.check("once the slash is over, the ready pose is back",
            anim.is_playing_slot_animation(pose, AIM_SLOT)
            and not anim.is_playing_slot_animation(clip, AIM_SLOT))
