"""Empty hands punch: the swing plays its clip, and the blow lands on a
zombie in front of the player.

No key can be injected into a headless game, so the probe empties the hands
(Held = None) and writes PunchQueued, which is all the press gate does
(verify/punch.py checks the gate itself). Then a wanderer is put in front of
the player and the swing is followed through: the cooldown and the blow are
stamped, the skin's punch (Lyra's melee on the motion-matching skin, played
from COMBAT.punch_clip_start_s) plays in the upper-body slot, and the blow
takes COMBAT.punch_damage off the wanderer and credits the player.
"""

import unreal

from asset_pipeline import lyra_paths as LYRA
from combat.anim_blueprint import AIM_SLOT
from combat.paths import (
    HEALTH_BP_PATH, HEALTH_CLASS_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH,
)
from combat.skin import skin_of_mesh
from combat.slot_tuning import HAND_FROM_VAR
from combat.tuning import COMBAT
from combat.weapon_component.punch import (
    NEXT_PUNCH_VAR, PUNCH_ANIM_VAR, PUNCH_PENDING_VAR, PUNCH_QUEUED_VAR,
)
from combat import health_vars as HV
from combat.weapon_component import vars as WV

WRITABLE = [(WEAPON_COMP_BP_PATH, WV.Held), (WEAPON_COMP_BP_PATH, PUNCH_QUEUED_VAR),
            (HEALTH_BP_PATH, HV.Health)]

IN_FRONT_CM = 90.0    # capsule centre to capsule centre: well inside the reach


def _wanderer(p):
    ctrls = unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.AIController)
    pawns = [c.get_controlled_pawn() for c in ctrls
             if "ForestWandererAI" in c.get_class().get_name()]
    pawns = [x for x in pawns if x is not None]
    # A zombie if there is one: the wendigo is the other creature.
    return next((x for x in pawns if "Zombie" in x.get_class().get_name()),
                pawns[0] if pawns else None)


def _place(npc, player):
    spot = player.get_actor_location() + player.get_actor_forward_vector() * IN_FRONT_CM
    npc.set_actor_location(spot, False, True)


def probe(p):
    yield lambda: _wanderer(p) is not None
    yield 0.5
    player, npc = p.pawn(), _wanderer(p)
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    health = p.component(npc, HEALTH_CLASS_PATH)
    p.check("the player has a weapon component and a wanderer has health",
            wc is not None and health is not None)
    if wc is None or health is None:
        return
    p.check("the punch clip is set on the live component",
            p.get(wc, PUNCH_ANIM_VAR) is not None, str(p.get(wc, PUNCH_ANIM_VAR)))
    skin = skin_of_mesh(player.get_editor_property("mesh").get_skeletal_mesh_asset().get_path_name())
    if skin is not None and skin.gas:
        got = p.get(wc, PUNCH_ANIM_VAR)
        p.check("...Lyra's melee, retargeted onto the worn skeleton",
                got is not None and got.get_path_name().split(".")[0]
                == LYRA.uefn_clip(LYRA.PUNCH), str(got))
    p.check("the wanderer punched is a zombie", "Zombie" in npc.get_class().get_name(),
            npc.get_class().get_name())

    # Empty hands, the way the player empties them: the hand's item back to
    # its slot. (Held written to None is put back by the next equip, and a
    # punch asked of the server with a gun in hand is refused.)
    held = p.get(wc, "Held")
    if held is not None:
        p.ask_slot(wc, p.get(wc, HAND_FROM_VAR))
        yield lambda: p.get(wc, "Held") is None
    p.set(health, "Health", 100.0)
    _place(npc, player)
    yield 0.05
    _place(npc, player)
    before = p.get(health, "Health")
    world = p.world()
    t0 = unreal.GameplayStatics.get_time_seconds(world)
    p.set(wc, PUNCH_QUEUED_VAR, True)

    yield lambda: not p.get(wc, PUNCH_QUEUED_VAR)
    anim = player.get_editor_property("mesh").get_anim_instance()
    p.check("the swing takes the queued punch",
            not p.get(wc, PUNCH_QUEUED_VAR) and p.get(wc, PUNCH_PENDING_VAR))
    clip = p.get(wc, PUNCH_ANIM_VAR)
    p.check(f"...and plays the punch clip in {AIM_SLOT}",
            anim is not None and anim.is_playing_slot_animation(clip, AIM_SLOT),
            str(anim.get_current_active_montage() if anim else None))
    montage = anim.get_current_active_montage() if anim else None
    p.check("...from COMBAT.punch_clip_start_s in, so the fist is out for the blow",
            montage is not None
            and anim.montage_get_position(montage) >= COMBAT.punch_clip_start_s - 1e-3,
            str(anim.montage_get_position(montage) if montage else None))
    p.check("...and stamps the cooldown",
            abs(p.get(wc, NEXT_PUNCH_VAR) - t0 - COMBAT.punch_interval_s) < 0.2,
            f"{p.get(wc, NEXT_PUNCH_VAR):.2f} at t0 {t0:.2f}")
    p.check("the blow has not landed before the fist is out",
            abs(p.get(health, "Health") - before) < 1e-3,
            f"{p.get(health, 'Health')}")

    _place(npc, player)
    # The slot's weight follows on the next anim update, not on the play.
    # Asked for as soon as it is there, not a fixed wait later: the wanderer
    # stood in front swings back, and its blow's flinch stops the punch's
    # montage (all the slots share one montage group: docs/health.md).
    asked = unreal.GameplayStatics.get_time_seconds(world)
    yield lambda: (anim.is_slot_active(AIM_SLOT)
                   or unreal.GameplayStatics.get_time_seconds(world) - asked > 0.1)
    p.check("...which takes the upper body", anim.is_slot_active(AIM_SLOT))
    yield lambda: not p.get(wc, PUNCH_PENDING_VAR)
    after = p.get(health, "Health")
    p.check(f"the blow takes {COMBAT.punch_damage:.0f} HP off the wanderer in front",
            abs((before - after) - COMBAT.punch_damage) < 1e-3,
            f"{before} -> {after}")
    p.check("...and credits the player", p.get(health, "DamagedByPlayer") is True)
