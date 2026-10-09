"""A pellet has to strike the zombie's body, not just its capsule.

The capsule stops a pellet and is 68 cm across; the model is far narrower, and
its physics bodies are fitted to it (combat/hit_bodies.py). Three things are
measured on a live wanderer:

  * its bodies sit on the animated model: a line through the head bone strikes
    the head's body, and one a hand's width beside the head strikes the capsule
    and no body at all;
  * a round fired at it while it has no bodies to strike (its mesh's collision
    is switched off for the shot, so every pellet meets the capsule alone) draws
    no blood and does no damage -- before, that was a body hit;
  * the same round with the bodies back bleeds and hurts, and the blood sits
    on the body, not on the capsule in front of it.

FireForced stands in for the fire key. Any profile on disk is set aside first.
"""

SYSTEMS = ('health',)

import os
import shutil

import unreal

from combat.paths import (
    BLOOD_CLASS_PATH, HEALTH_BP_PATH, HEALTH_CLASS_PATH, WEAPON_COMP_BP_PATH,
    WEAPON_COMP_CLASS_PATH,
)
from combat.weapon_component.tick import FIRE_FORCED_VAR
from probes.probe_bullet_impact import _all, _file, _fire, _look, _until, _wanderer
from combat import health_vars as HV

WRITABLE = [(WEAPON_COMP_BP_PATH, FIRE_FORCED_VAR), (HEALTH_BP_PATH, HV.Health)]

IN_FRONT_CM = 150.0      # past the muzzle, inside every pellet's pattern
SWEEP_CM = 40            # either side of the head, a line per centimetre
HEAD_MAX_CM = 22         # the fitted head's capsule is 20 across
AIM_NEAR_CM = 40.0       # the reticle is on the capsule in front of the chest
ON_BODY_CM = 5.0         # a splash is traced from this far in front of itself


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _through(comp, at, along):
    """The bone a line through ``at`` strikes on ``comp``; None for a miss."""
    hit = comp.line_trace_component(at - along * 200.0, at + along * 200.0,
                                    False, False, False)
    return str(hit[2]) if hit else None


def _aim_at_chest(p, wc, npc, stand):
    """Rest the reticle on the wanderer's chest. The camera sits over the
    shoulder, so looking level puts it beside a wanderer stood dead ahead."""
    cam = unreal.GameplayStatics.get_player_camera_manager(p.world(), 0)
    chest = lambda: npc.mesh.get_socket_location("Spine02")
    for _ in range(4):     # the boom swings as the view turns: close in on it
        stand()
        p.controller().set_control_rotation(unreal.MathLibrary.find_look_at_rotation(
            cam.get_camera_location(), chest()))
        yield 0.1
    stand()
    yield _until(lambda: p.get(wc, "AimValid")
                 and (p.get(wc, "AimPoint") - chest()).length() < AIM_NEAR_CM)
    p.check("the reticle rests on the wanderer's chest",
            (p.get(wc, "AimPoint") - chest()).length() < AIM_NEAR_CM,
            f"{(p.get(wc, 'AimPoint') - chest()).length():.0f} cm off; camera "
            f"{(cam.get_camera_location() - chest()).length():.0f} cm from the chest, "
            f"view {p.controller().get_control_rotation()}")


def _run(p):
    yield lambda: _wanderer(p) is not None
    yield 0.5
    player, npc = p.pawn(), _wanderer(p)
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    held = p.get(wc, "Held")
    p.check("the player holds a loaded gun",
            held is not None and p.get(held, "Loaded") > 0, str(held))
    health = p.component(npc, HEALTH_CLASS_PATH)
    p.set(health, "Health", 1000.0)    # it must outlive the rounds
    _look(p, 0.0)

    # One spot, fixed now: the player turns with the view, and a wanderer
    # re-stood "ahead" each time would circle away from the reticle.
    spot = player.get_actor_location() + player.get_actor_forward_vector() * IN_FRONT_CM

    def stand():
        npc.set_actor_location(spot, False, True)

    stand()
    yield 0.1
    stand()

    # --- the bodies sit on the model ----------------------------------------
    mesh, capsule = npc.mesh, npc.capsule_component
    p.check("the wanderer wears the zombie", "Zombie" in mesh.get_skeletal_mesh_asset().get_name(),
            mesh.get_skeletal_mesh_asset().get_name())
    head = mesh.get_socket_location("Head")
    along = player.get_actor_forward_vector()
    side = along.cross(unreal.Vector(0, 0, 1))
    # The head bone is the head's base; its middle is a few centimetres up.
    middle = head + unreal.Vector(0, 0, 8.0)
    p.check("a line through the head strikes the head's body",
            (_through(mesh, middle, along) or "").lower() == "head",
            str(_through(mesh, middle, along)))
    # Across the head, a centimetre at a time: how wide the head's body is,
    # and how much wider the capsule is round it. The idle hunches the head
    # forward and the wanderer faces any way, so it is measured from eight
    # sides and the narrowest counts: a leaning capsule's true width.
    widths = []
    for step in range(8):
        yaw = unreal.Rotator(roll=0.0, pitch=0.0, yaw=step * 22.5)
        ray, across = (unreal.MathLibrary.greater_greater_vector_rotator(v, yaw)
                       for v in (along, side))
        lines = [middle + across * float(cm) for cm in range(-SWEEP_CM, SWEEP_CM + 1)]
        widths.append((
            sum((_through(mesh, at, ray) or "").lower() == "head" for at in lines),
            sum(_through(capsule, at, ray) is not None for at in lines)))
    on_head, on_capsule = min(widths)
    p.check(f"the head's body is no wider than {HEAD_MAX_CM} cm (the importer's: 26)",
            10 <= on_head <= HEAD_MAX_CM, f"{on_head} cm; from eight sides {widths}")
    p.check("...inside a capsule far wider at that height: the near misses",
            on_capsule >= on_head + 10, f"capsule {on_capsule} cm, head {on_head} cm")

    # --- a round that meets the capsule alone -------------------------------
    was = mesh.get_collision_enabled()
    mesh.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    yield from _aim_at_chest(p, wc, npc, stand)
    before = p.get(health, "Health")
    yield from _fire(p, wc, held)
    yield 0.05
    p.check("a round that strikes no body draws no blood",
            not _all(p, BLOOD_CLASS_PATH), f"{len(_all(p, BLOOD_CLASS_PATH))} BP_BloodSplash")
    p.check("...and does no damage", p.get(health, "Health") == before,
            f"{before:.0f} -> {p.get(health, 'Health'):.0f}")

    # --- the same round with the bodies back --------------------------------
    mesh.set_collision_enabled(was)
    yield from _aim_at_chest(p, wc, npc, stand)
    yield from _fire(p, wc, held)
    blood = _all(p, BLOOD_CLASS_PATH)
    p.check("with its bodies back, the same round bleeds", len(blood) >= 1,
            f"{len(blood)} BP_BloodSplash")
    p.check("...and hurts", p.get(health, "Health") < before,
            f"{before:.0f} -> {p.get(health, 'Health'):.0f}")
    # On the body, not on the capsule in front of it: from each splash, along
    # the shot, a body is within a few centimetres. (The capsule's surface is
    # 10-25 cm off the chest, and a zombie's reaching arms are outside it.)
    shot = unreal.GameplayStatics.get_player_camera_manager(
        p.world(), 0).get_actor_forward_vector()
    gaps = []
    for b in blood:
        at = b.get_actor_location()
        hit = mesh.line_trace_component(at - shot * ON_BODY_CM, at + shot * 60.0,
                                        False, False, False)
        gaps.append(round((hit[0] - at).length(), 1) if hit else None)
    close = [g for g in gaps if g is not None and g <= 2 * ON_BODY_CM]
    p.check(f"...and the blood is on the body: within {2 * ON_BODY_CM:.0f} cm of it",
            bool(gaps) and len(close) == len(gaps), str(gaps))
