"""The axe: issued at the start, taken in hand, and swung at a wanderer.

The player must start carrying BP_Axe, fourth of the issued items. The
probe equips it the way Q does (EquippedIndex + NeedsRefresh) and checks it
is drawn in the fist in its own ready pose (A_HoldAxe, Mixamo's axe idle),
then writes KnifeQueued, which is all the press gate does for any Melee item
(probe_knife.py says why). The axe has no strike of its own: the swing must be
the knife's stage and damage, in the axe's own clip (A_AxeSwing, picked by the
ready pose in hand: weapon_component/knife.py).

Any profile on disk is set aside first, so the game starts on the issued
loadout, and put back at the end.
"""

import os
import shutil

import unreal

from combat.anim_blueprint import AIM_SLOT
from combat.axe import AXE_MESH
from combat.paths import (
    AXE_ANIM_PATH, HEALTH_BP_PATH, HEALTH_CLASS_PATH, HOLD_AXE_ANIM_PATH,
    WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH,
)
from combat.tuning import COMBAT
from combat.weapon_component.knife import (
    AXE_ANIM_VAR, KNIFE_ANIM_VAR, KNIFE_PENDING_VAR, KNIFE_QUEUED_VAR,
)
from probes.probe_knife import _file, _held_name, _place, _wanderer
from combat import health_vars as HV
from combat.weapon_component import vars as WV

WRITABLE = [(WEAPON_COMP_BP_PATH, WV.EquippedIndex), (WEAPON_COMP_BP_PATH, WV.NeedsRefresh),
            (WEAPON_COMP_BP_PATH, KNIFE_QUEUED_VAR), (HEALTH_BP_PATH, HV.Health)]

AXE = "BP_Axe_C"
# How far the middle of the drawn axe may be from the hand's socket (cm): the middle of
# a 65 cm axe held near its knob is about 15 cm up the haft. Nearer, it is
# drawn at no size; further, it is not in the hand.
MODEL_FROM_HAND_CM = (8.0, 40.0)


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
    p.check("the axe is issued, after the shotgun, the pistol and the knife",
            bag[:4] == ["BP_Shotgun_C", "BP_Pistol_C", "BP_Knife_C", AXE], str(bag))
    if AXE not in bag:
        return
    axe = list(p.get(wc, "Inventory"))[bag.index(AXE)]
    p.check("...carried, not lying in the world, and put away until taken up",
            not p.get(axe, "Dropped") and axe.get_editor_property("hidden")
            and _held_name(p, wc) == "BP_Shotgun_C",
            f"dropped {p.get(axe, 'Dropped')} held {_held_name(p, wc)}")
    p.check("...named for the HUD, with its icon",
            str(p.get(axe, "DisplayName")) == "Axe" and p.get(axe, "Icon") is not None,
            f"{p.get(axe, 'DisplayName')} {p.get(axe, 'Icon')}")

    p.set(wc, "EquippedIndex", bag.index(AXE))
    p.set(wc, "NeedsRefresh", True)
    yield lambda: _held_name(p, wc) == AXE
    p.check("equipped like any item, the axe is in hand",
            p.get(wc, "Held") == axe and axe.get_attach_parent_actor() == player
            and not axe.get_editor_property("hidden"), str(axe.get_attach_parent_actor()))
    anim = player.get_editor_property("mesh").get_anim_instance()
    pose = p.get(axe, "AimPose")
    yield 0.2
    p.check("...in its own ready pose (A_HoldAxe)",
            anim is not None and anim.is_playing_slot_animation(pose, AIM_SLOT)
            and pose.get_path_name().split(".")[0] == HOLD_AXE_ANIM_PATH, str(pose))
    model = next((c for c in axe.get_components_by_class(unreal.StaticMeshComponent)
                  if c.get_editor_property("static_mesh") is not None
                  and c.get_editor_property("static_mesh").get_path_name().startswith(AXE_MESH)),
                 None)
    # The socket it hangs from, whatever the worn rig calls its hand bone.
    socket = axe.get_attach_parent_socket_name()
    hand = player.get_editor_property("mesh").get_socket_location(socket)
    reach = ((unreal.SystemLibrary.get_component_bounds(model)[0] - hand).length()
             if model else -1.0)
    p.check("...its model on it, at its size, the haft in the hand",
            MODEL_FROM_HAND_CM[0] < reach < MODEL_FROM_HAND_CM[1],
            f"the model's middle is {reach:.1f} cm from {socket}")

    p.set(health, "Health", 100.0)
    _place(npc, player)
    yield 0.05
    _place(npc, player)
    before = p.get(health, "Health")
    p.set(wc, KNIFE_QUEUED_VAR, True)
    yield lambda: not p.get(wc, KNIFE_QUEUED_VAR)
    clip, knifes = p.get(wc, AXE_ANIM_VAR), p.get(wc, KNIFE_ANIM_VAR)
    p.check("a queued swing is taken with the axe in hand, in the axe's own clip "
            "(A_AxeSwing) and not the knife's",
            p.get(wc, KNIFE_PENDING_VAR) and clip is not None
            and clip.get_path_name().split(".")[0] == AXE_ANIM_PATH
            and anim.is_playing_slot_animation(clip, AIM_SLOT)
            and not anim.is_playing_slot_animation(knifes, AIM_SLOT),
            str(anim.get_current_active_montage()))
    _place(npc, player)
    yield lambda: not p.get(wc, KNIFE_PENDING_VAR)
    after = p.get(health, "Health")
    p.check(f"the blow takes {COMBAT.knife_damage:.0f} HP off the wanderer in front",
            abs((before - after) - COMBAT.knife_damage) < 1e-3, f"{before} -> {after}")
    p.check("...and the axe is still in hand (a swing spends nothing)",
            p.get(wc, "Held") == axe)
