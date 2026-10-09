"""A round in a wanderer's head stamps the weapon component's HeadshotTime
(the HUD's X round the reticle, graphics_menu/hit_marker.py); one in its
chest does not.

A wanderer is stood in front of the player, its controller taken off it, and
the player holds the pistol. A round is
put in its chest first (a second or third if the hip's cloud sends one past
it): it hurts, and HeadshotTime stays where a level
starts it (HEADSHOT_NEVER, so no X is drawn at the start). Then rounds are
put at its head until one strikes it: HeadshotTime is the game time of that
round, inside the HEADSHOT_MARK_SECONDS the X is up for.

The X itself is drawn by DrawHUD, which a headless game never calls: that
it is drawn is the graph's (graphics_menu/reticle_checks.py).

FireForced stands in for the fire key. Any profile on disk is set aside first.
"""

SYSTEMS = ('weapons',)

import os
import shutil

import unreal

from combat.headshot_tuning import (
    HEADSHOT_MARK_SECONDS, HEADSHOT_NEVER, HEADSHOT_TIME_VAR,
)
from combat.paths import (
    HEALTH_BP_PATH, HEALTH_CLASS_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH,
)
from combat.weapon_component import vars as WV
from combat.weapon_component.tick import FIRE_FORCED_VAR
from probes.probe_bullet_impact import _file, _fire, _look, _until, _wanderer
from combat import health_vars as HV

WRITABLE = [(WEAPON_COMP_BP_PATH, v) for v in
            (FIRE_FORCED_VAR, WV.EquippedIndex, WV.NeedsRefresh)] + [
    (HEALTH_BP_PATH, HV.Health)]

# Far enough that a hip round's line from the muzzle to the reticle's point
# goes on into the body: at 150 cm the point is on the capsule 35 cm ahead of
# the muzzle and 50 cm to its side (the camera is over the shoulder), and two
# rounds in three left through the capsule's side.
IN_FRONT_CM = 300.0
AIM_NEAR_CM = 40.0       # the reticle is on the capsule in front of the bone
HEAD_ROUNDS = 5          # the hip's cloud: a round or two may pass the head
BODY_ROUNDS = 3          # ...or, in a rendered run, the chest


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _aim(p, wc, stand, point):
    """Rest the reticle on ``point()``. The camera sits over the shoulder and
    its boom swings as the view turns, so close in on it."""
    cam = unreal.GameplayStatics.get_player_camera_manager(p.world(), 0)
    for _ in range(4):
        stand()
        p.controller().set_control_rotation(unreal.MathLibrary.find_look_at_rotation(
            cam.get_camera_location(), point()))
        yield 0.1
    stand()
    yield _until(lambda: p.get(wc, "AimValid")
                 and (p.get(wc, "AimPoint") - point()).length() < AIM_NEAR_CM)


def _run(p):
    yield lambda: _wanderer(p) is not None
    yield 0.5
    player, npc = p.pawn(), _wanderer(p)
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    now = lambda: unreal.GameplayStatics.get_time_seconds(p.world())
    stamp = lambda: p.get(wc, HEADSHOT_TIME_VAR)

    p.check(f"a level starts with {HEADSHOT_TIME_VAR} far in the past: no X at the start",
            stamp() == HEADSHOT_NEVER and now() - stamp() > HEADSHOT_MARK_SECONDS,
            f"{stamp()} at {now():.2f} s")

    # The pistol: one round, a small cloud.
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
    p.set(health, "Health", 5000.0)    # it must outlive the rounds
    # Its tree would have it swing at the player, who was dead before the
    # last round one run in two.
    npc.get_controller().un_possess()
    _look(p, 0.0)
    spot = player.get_actor_location() + player.get_actor_forward_vector() * IN_FRONT_CM

    def stand():
        npc.set_actor_location(spot, False, True)

    stand()
    yield 0.1
    stand()
    mesh = npc.mesh

    # --- a round in the chest ------------------------------------------------
    before, fired = p.get(health, "Health"), 0
    while fired < BODY_ROUNDS and p.get(health, "Health") == before:
        yield from _aim(p, wc, stand, lambda: mesh.get_socket_location("Spine02"))
        yield from _fire(p, wc, held)
        yield 0.05
        fired += 1
    p.check("a round in the chest hurts", p.get(health, "Health") < before,
            f"{before:.0f} -> {p.get(health, 'Health'):.0f}, after {fired} round(s)")
    p.check(f"...and leaves {HEADSHOT_TIME_VAR} alone: no X", stamp() == HEADSHOT_NEVER,
            str(stamp()))

    # --- rounds at the head, until one strikes it ----------------------------
    # The head bone is the head's base; its middle is a few centimetres up.
    head = lambda: mesh.get_socket_location("Head") + unreal.Vector(0, 0, 8.0)
    fired = 0
    while fired < HEAD_ROUNDS and stamp() == HEADSHOT_NEVER:
        yield from _aim(p, wc, stand, head)
        yield from _fire(p, wc, held)
        yield 0.02
        fired += 1
    age = now() - stamp()
    p.check(f"a round in the head stamps {HEADSHOT_TIME_VAR} with the game's time",
            stamp() != HEADSHOT_NEVER and 0.0 <= age,
            f"{stamp():.3f} at {now():.3f} s, after {fired} round(s); "
            f"bone under the reticle {p.get(wc, 'HitBone')}")
    p.check(f"...so the HUD's test (now - {HEADSHOT_TIME_VAR} < "
            f"{HEADSHOT_MARK_SECONDS:g} s) draws the X",
            0.0 <= age < HEADSHOT_MARK_SECONDS, f"{age:.3f} s old")
    yield _until(lambda: now() - stamp() > HEADSHOT_MARK_SECONDS)
    p.check("...and it is gone again once that has passed",
            now() - stamp() > HEADSHOT_MARK_SECONDS, f"{now() - stamp():.3f} s old")
