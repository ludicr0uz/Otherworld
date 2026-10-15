"""A round that draws blood leaves a splat (BP_BloodSprite, combat/blood_sprite.py)
at the wound, sized by the zone it struck: a limb's smallest, the chest's
medium, the head's largest (blood_sprite_consts.splat_scale).

A wanderer is stood in front of the player, its controller taken off it, and
the player holds the pistol (one pellet a round, so one splat). Rounds are
put at a leg, the chest and the head in turn. Each round that hurts is
judged by the bone it struck (HitBone, against the wanderer's own HeadBones
and LimbBones): exactly one new splat, scaled as that zone says, facing the
camera, its card drawn in M_BloodSprite. The splats are gone once their
SPLAT_LIFETIME has passed.

The hip's cloud may send a round aimed at one zone into another: it is
judged by the bone it struck, and the probe goes on until each of the three
zones has been seen or its rounds run out. The magazine is topped up before
each round.
"""

SYSTEMS = ('weapons',)
LEVEL = "/Game/Maps/Lvl_Forest_200m"  # probe_headshot's reason: on the 50 m level the wanderers reach the player between rounds

import os
import shutil

import unreal

from combat.blood_sprite_consts import SPLAT_COMPONENT, SPLAT_LIFETIME, splat_scale
from combat.paths import (
    BLOOD_SPRITE_CLASS_PATH, HEALTH_BP_PATH, HEALTH_CLASS_PATH, ITEM_BP_PATH, WEAPON_COMP_BP_PATH,
    WEAPON_COMP_CLASS_PATH,
)
from combat.tuning import COMBAT
from combat.weapon_component import vars as WV
from combat.weapon_component.tick import FIRE_FORCED_VAR
from probes.probe_bullet_impact import _all, _file, _fire, _look, _until, _wanderer
from probes.probe_headshot import IN_FRONT_CM, _aim
from combat import health_vars as HV
from combat import item_vars as IV

WRITABLE = [(WEAPON_COMP_BP_PATH, v) for v in
            (FIRE_FORCED_VAR, WV.EquippedIndex, WV.NeedsRefresh)] + [
    (HEALTH_BP_PATH, HV.Health), (ITEM_BP_PATH, IV.Loaded)]

ROUNDS_PER_ZONE = 8
SCALE_TOLERANCE = 1e-3
FACING_DOT = 0.9          # the card's +X toward the camera, within ~25 degrees


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _zone(bone, heads, limbs):
    if bone in heads:
        return "head"
    if bone in limbs:
        return "limb"
    return "chest"


def _want(zone):
    worth = {"head": COMBAT.head_multiplier, "limb": COMBAT.limb_multiplier}.get(zone, 1.0)
    return splat_scale(zone == "head", worth)


def _judge(p, zone, bone, new):
    """The splats one round left, read at once: they live SPLAT_LIFETIME."""
    scales = [round(s.get_actor_scale3d().x, 4) for s in new]
    p.check(f"a round in the {zone} ({bone}) leaves one splat, scaled {_want(zone):.2f}",
            len(new) == 1 and abs(new[0].get_actor_scale3d().x - _want(zone)) < SCALE_TOLERANCE,
            f"{len(new)} splat(s), scales {scales}")
    if len(new) != 1:
        return
    splat = new[0]
    cam = unreal.GameplayStatics.get_player_camera_manager(p.world(), 0)
    toward = cam.get_camera_location() - splat.get_actor_location()
    toward.normalize()
    facing = splat.get_actor_forward_vector().dot(toward)
    p.check("...facing the camera", facing > FACING_DOT, f"{facing:.3f}")
    # The card's spawn-time stamp has no getter in Python (custom primitive
    # data is not a reflected property): verify/blood_sprite.py holds the
    # BeginPlay that writes it. Here: the card is there, in the splat's material.
    card = next((c for c in splat.get_components_by_class(unreal.StaticMeshComponent)
                 if c.get_name() == SPLAT_COMPONENT), None)
    mat = card.get_material(0) if card else None
    p.check(f"...its {SPLAT_COMPONENT} card drawn in M_BloodSprite",
            mat is not None and mat.get_name() == "M_BloodSprite", str(mat))


def _run(p):
    yield lambda: _wanderer(p) is not None
    yield 0.5
    player, npc = p.pawn(), _wanderer(p)
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    splats = lambda: _all(p, BLOOD_SPRITE_CLASS_PATH)

    names = [i.get_class().get_name() for i in p.get(wc, "Inventory")]
    index = names.index("BP_Pistol_C")
    p.set(wc, "EquippedIndex", index)
    p.set(wc, "NeedsRefresh", True)
    yield _until(lambda: p.get(wc, "Held") == p.get(wc, "Inventory")[index])
    yield 0.3
    held = p.get(wc, "Held")
    p.check("the player holds the loaded pistol",
            held is not None and "Pistol" in held.get_class().get_name()
            and p.get(held, "Loaded") > 0, str(held))

    health = p.component(npc, HEALTH_CLASS_PATH)
    p.set(health, "Health", 5000.0)
    npc.get_controller().un_possess()
    heads = {str(b) for b in p.get(health, "HeadBones")}
    limbs = {str(b) for b in p.get(health, "LimbBones")}
    leg = "LeftUpLeg" if "LeftUpLeg" in limbs else ""
    knee = "LeftLeg" if "LeftLeg" in limbs else leg
    p.check("the wanderer has a head and a thigh to aim at", bool(heads) and bool(leg),
            f"heads {sorted(heads)}, limbs {sorted(limbs)}")
    _look(p, 0.0)
    spot = player.get_actor_location() + player.get_actor_forward_vector() * IN_FRONT_CM

    def stand():
        npc.set_actor_location(spot, False, True)

    stand()
    yield 0.1
    stand()
    mesh = npc.mesh
    # The leg last, at the middle of the thigh: its bone starts at the hip
    # joint, and a round aimed there strikes the Hips (the chest's zone).
    thigh = lambda: (mesh.get_socket_location(leg) + mesh.get_socket_location(knee)) * 0.5
    targets = (("chest", lambda: mesh.get_socket_location("Spine02")),
               ("head", lambda: mesh.get_socket_location("Head") + unreal.Vector(0, 0, 8.0)),
               ("limb", thigh))
    seen = set()
    for aimed, point in targets:
        fired = 0
        while fired < ROUNDS_PER_ZONE and aimed not in seen:
            p.set(held, IV.Loaded, 8)            # never empty
            yield from _aim(p, wc, stand, point)
            before_hp, before = p.get(health, "Health"), set(splats())
            yield from _fire(p, wc, held)
            fired += 1
            new = [s for s in splats() if s not in before]
            if p.get(health, "Health") >= before_hp:
                p.check("...a round that misses leaves no splat", not new, f"{len(new)}")
                continue
            bone = str(p.get(wc, "HitBone"))
            zone = _zone(bone, heads, limbs)
            if zone not in seen:
                seen.add(zone)
                _judge(p, zone, bone, new)
    for zone in ("limb", "chest", "head"):
        if zone not in seen:
            p.check(f"a round struck the {zone}", False, f"after {ROUNDS_PER_ZONE} round(s)")

    yield SPLAT_LIFETIME + 0.3
    p.check(f"the splats are gone after {SPLAT_LIFETIME}s", not splats(), f"{len(splats())}")
