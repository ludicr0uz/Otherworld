"""The shot log (Source/Otherworld/Private/OtherworldShotLog.h): with the
GameState's DebugShotLog (the DEBUG SETTINGS tab's "Shot log") a shot the
authority judges writes SHOT-LOG lines; without it, none.

    python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_shot_log.py

A wanderer is stood in front of the player, its controller taken off it, and
the player holds the pistol (as probe_headshot.py does).

  - switch off: IsShotLogOn is false, and a round writes no line;
  - switch on: IsShotLogOn is true; a round in the chest writes the ask and
    the pellet, whose block names the muzzle, what stopped it, the wanderer
    as the target with its mesh and capsule, the bone struck and HIT with
    the damage and the health before and after;
  - a round aimed beside it writes a pellet that did no damage, and names
    the wanderer as the character nearest its line;
  - switch off again: no line.

FireForced stands in for the fire key. Any profile on disk is set aside first.
"""

SYSTEMS = ('weapons',)
LEVEL = "/Game/Maps/Lvl_Forest_200m"  # as probe_headshot.py: the 50 m level's wanderers kill the player between rounds

import os
import shutil

import unreal

from combat import health_vars as HV
from combat.paths import HEALTH_BP_PATH, HEALTH_CLASS_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.weapon_component import vars as WV
from combat.weapon_component.tick import FIRE_FORCED_VAR
from net.state_consts import DEBUG_SHOT_LOG_VAR, GAME_STATE_BP_PATH
from probes.probe_bullet_impact import _file, _fire, _look, _until, _wanderer
from probes.probe_headshot import IN_FRONT_CM, _aim

WRITABLE = [(WEAPON_COMP_BP_PATH, v) for v in
            (FIRE_FORCED_VAR, WV.EquippedIndex, WV.NeedsRefresh)] + [
    (HEALTH_BP_PATH, HV.Health), (GAME_STATE_BP_PATH, DEBUG_SHOT_LOG_VAR)]

SHL = unreal.OtherworldShotLibrary
BODY_ROUNDS = 3          # the hip's cloud may send one past the chest
BESIDE_CM = 250.0        # the miss: this far to the wanderer's side


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        p.set(p.game_state(), DEBUG_SHOT_LOG_VAR, False)
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _switch(p, on):
    p.set(p.game_state(), DEBUG_SHOT_LOG_VAR, on)
    return bool(SHL.is_shot_log_on(p.world())) == on


def _run(p):
    yield lambda: _wanderer(p) is not None
    yield 0.5
    player, npc = p.pawn(), _wanderer(p)
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)

    names = [i.get_class().get_name() for i in p.get(wc, "Inventory")]
    index = names.index("BP_Pistol_C")
    p.set(wc, "EquippedIndex", index)
    p.set(wc, "NeedsRefresh", True)
    yield _until(lambda: p.get(wc, "Held") == p.get(wc, "Inventory")[index])
    yield 0.3
    held = p.get(wc, "Held")

    health = p.component(npc, HEALTH_CLASS_PATH)
    p.set(health, "Health", 5000.0)
    npc.get_controller().un_possess()
    _look(p, 0.0)
    spot = player.get_actor_location() + player.get_actor_forward_vector() * IN_FRONT_CM

    def stand():
        npc.set_actor_location(spot, False, True)

    stand()
    yield 0.1
    mesh = npc.mesh
    chest = lambda: mesh.get_socket_location("Spine02")

    # --- off: nothing written ------------------------------------------------
    p.check("with DebugShotLog off the shot log is off", _switch(p, False))
    lines = SHL.shot_log_lines()
    yield from _aim(p, wc, stand, chest)
    yield from _fire(p, wc, held)
    yield 0.05
    p.check("...and a round writes no SHOT-LOG line", SHL.shot_log_lines() == lines,
            f"{lines} -> {SHL.shot_log_lines()}")

    # --- on: a round in the chest --------------------------------------------
    p.check("DebugShotLog on turns the shot log on", _switch(p, True))
    before, fired, block = p.get(health, "Health"), 0, ""
    while fired < BODY_ROUNDS and p.get(health, "Health") == before:
        lines = SHL.shot_log_lines()
        yield from _aim(p, wc, stand, chest)
        yield from _fire(p, wc, held)
        yield 0.05
        fired += 1
        block = str(SHL.last_shot_log())
    written = SHL.shot_log_lines() - lines
    p.check("a round in the chest hurts", p.get(health, "Health") < before,
            f"{before:.0f} -> {p.get(health, 'Health'):.0f}, after {fired} round(s)")
    p.check("...and writes the ask and the pellet (7 lines or more)", written >= 7,
            f"{written} line(s)")
    wanted = ("pellet 1/1", "muzzle=", "dir=", "stopped by " + npc.get_name(),
              "impact=", "target " + npc.get_name(), "mesh=", "capsule r=",
              "body struck: bone=", "HIT " + npc.get_name(), "damage=", "health ")
    missing = [w for w in wanted if w not in block]
    p.check("...the pellet's block names the line, the target and its body, "
            "the bone and the damage", not missing, f"missing {missing}:\n{block}")
    unreal.log(f"[PROBE] the hit's block:\n{block}")

    # --- on: a round beside it -----------------------------------------------
    beside = lambda: chest() + player.get_actor_right_vector() * BESIDE_CM
    yield from _aim(p, wc, stand, beside)
    yield from _fire(p, wc, held)
    yield 0.05
    block = str(SHL.last_shot_log())
    p.check("a round beside it logs no damage and the wanderer as the character "
            "nearest its line", "no damage" in block
            and "nearest character " + npc.get_name() in block, block)
    unreal.log(f"[PROBE] the miss's block:\n{block}")

    # --- off again -------------------------------------------------------------
    p.check("DebugShotLog off turns it off again", _switch(p, False))
    lines = SHL.shot_log_lines()
    yield from _aim(p, wc, stand, chest)
    yield from _fire(p, wc, held)
    yield 0.05
    p.check("...and the next round writes nothing", SHL.shot_log_lines() == lines,
            f"{lines} -> {SHL.shot_log_lines()}")
