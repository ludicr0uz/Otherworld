"""The dead do nothing: a dead wanderer's steps refuse, and a dead player's
weapon component Tick does not run.

The wanderer first, while the player is alive to be hit. Its Swing step is
called directly, the way the tree's task calls it: alive and off cooldown it
takes health off the player beside it; marked Dead it takes none, and at 0 HP
-- before its health component has even ticked -- it takes none either
(npc/corpse.py's alive gate).

Then the player. FireForced stands in for the fire key (no key can be
injected into a headless game): alive, it fires a round. Then Health is
written to 0 with the trigger still forced, in the same instant, and through
the collapse no round is spent, nothing is thrown, and the weapon component
reports OwnerDead (combat/weapon_component/dead.py).

Any profile on disk is set aside first and put back at the end: the player
dies here, and death deletes the profile.
"""

import os
import shutil

import unreal

from combat.paths import (
    HEALTH_BP_PATH, HEALTH_CLASS_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH,
)
from combat.weapon_component.dead import LET_GO_VARS, OWNER_DEAD_VAR
from combat.weapon_component.throw import THROW_CLICK_FORCED_VAR, THROW_FORCED_VAR
from combat.weapon_component.throw_flight import THROWN_VAR
from combat.weapon_component.throw_windup import THROW_WINDING_VAR
from combat.weapon_component.tick import FIRE_FORCED_VAR
from forest_generator.npc_placement import NPC_VARIANTS
from graphics_menu.profile_consts import PROFILE_FORGOTTEN_VAR, PROFILE_SLOT
from npc.paths import (
    AGGRO_VAR, AI_BP_PATH, STEP_CHASE, STEP_EVENT_PREFIX, STEP_RESULT_VAR, STEP_SWING,
)
from combat import health_vars as HV

COOLDOWN_VAR = "NextAttackTime"
_AI_BPS = [AI_BP_PATH] + [v.ai_blueprint for v in NPC_VARIANTS]

WRITABLE = ([(HEALTH_BP_PATH, HV.Health), (HEALTH_BP_PATH, HV.Dead),
             (WEAPON_COMP_BP_PATH, FIRE_FORCED_VAR),
             (WEAPON_COMP_BP_PATH, THROW_FORCED_VAR),
             (WEAPON_COMP_BP_PATH, THROW_CLICK_FORCED_VAR)]
            + [(path, COOLDOWN_VAR) for path in _AI_BPS])

BESIDE_CM = 100.0     # inside every creature's melee range


def _file():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames",
                        f"{PROFILE_SLOT}.sav")


def _wanderers(p):
    ctrls = unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.AIController)
    return [c for c in ctrls if "ForestWandererAI" in c.get_class().get_name()
            and c.get_controlled_pawn() is not None]


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _wanderer_half(p)
        yield from _player_half(p)
    finally:
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _swing(p, ctrl, mine):
    """Call the Swing step off cooldown; returns the health it took off the
    player. No game frame passes, so nothing else can have hit meanwhile."""
    p.set(ctrl, COOLDOWN_VAR, 0.0)
    before = p.get(mine, "Health")
    ctrl.call_method(f"{STEP_EVENT_PREFIX}{STEP_SWING}")
    return before - p.get(mine, "Health")


def _wanderer_half(p):
    yield lambda: len(_wanderers(p)) > 0
    yield 0.5
    player = p.pawn()
    mine = p.component(player, HEALTH_CLASS_PATH)
    ctrl = _wanderers(p)[0]
    npc = ctrl.get_controlled_pawn()
    theirs = p.component(npc, HEALTH_CLASS_PATH)
    npc.set_actor_location(
        player.get_actor_location() + player.get_actor_forward_vector() * BESIDE_CM,
        False, True)
    yield lambda: p.get(ctrl, AGGRO_VAR)
    yield 0.1

    took = _swing(p, ctrl, mine)
    p.check("alive, a wanderer's Swing step hits the player beside it",
            took > 0.0 and p.get(ctrl, STEP_RESULT_VAR), f"took {took:.1f} HP")

    p.set(theirs, "Dead", True)
    took = _swing(p, ctrl, mine)
    p.check("marked Dead, the same step does nothing and fails",
            took == 0.0 and not p.get(ctrl, STEP_RESULT_VAR), f"took {took:.1f} HP")
    p.set(theirs, "Dead", False)

    took = _swing(p, ctrl, mine)
    p.check("...and alive again it hits again (the gate reads the pawn, live)",
            took > 0.0, f"took {took:.1f} HP")

    p.set(theirs, "Health", 0.0)
    took = _swing(p, ctrl, mine)
    p.check("at 0 HP, before its health component has ticked, it does nothing either",
            took == 0.0 and not p.get(ctrl, STEP_RESULT_VAR)
            and not p.get(theirs, "Dead"), f"took {took:.1f} HP")
    ctrl.call_method(f"{STEP_EVENT_PREFIX}{STEP_CHASE}")
    p.check("...and neither does its Chase step", not p.get(ctrl, STEP_RESULT_VAR))
    yield lambda: p.get(theirs, "Dead")


def _player_half(p):
    player = p.pawn()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    mine = p.component(player, HEALTH_CLASS_PATH)
    held = p.get(wc, "Held")
    p.check("the player is alive, holding a loaded gun",
            held is not None and p.get(held, "Loaded") > 1
            and p.get(mine, "Health") > 0.0 and not p.get(wc, OWNER_DEAD_VAR),
            f"{held.get_class().get_name() if held else None}, "
            f"{p.get(mine, 'Health'):.0f} HP")
    if held is None:
        return
    loaded = p.get(held, "Loaded")
    p.set(wc, FIRE_FORCED_VAR, True)
    yield lambda: p.get(held, "Loaded") < loaded
    p.set(wc, FIRE_FORCED_VAR, False)
    p.check("alive, the forced trigger fires a round",
            p.get(held, "Loaded") < loaded, f"{loaded} -> {p.get(held, 'Loaded')}")
    # Past the gun's cooldown, so the trigger below could fire if anything ran.
    now = lambda: unreal.GameplayStatics.get_time_seconds(p.world())
    yield lambda: now() > p.get(held, "NextFireTime") + 0.05

    loaded = p.get(held, "Loaded")
    carried = len(p.get(wc, "Inventory"))
    p.set(mine, "Health", 0.0)
    p.set(wc, FIRE_FORCED_VAR, True)
    yield 0.3
    p.check("killed with the trigger down, the player is Dead",
            p.get(mine, "Dead") and p.get(wc, OWNER_DEAD_VAR))
    p.check("...and fires nothing through the collapse",
            p.get(held, "Loaded") == loaded, f"{loaded} -> {p.get(held, 'Loaded')}")
    p.set(wc, FIRE_FORCED_VAR, False)
    p.set(wc, THROW_FORCED_VAR, True)
    yield 0.1
    p.set(wc, THROW_CLICK_FORCED_VAR, True)
    yield 0.2
    p.check("...and throws nothing",
            p.get(wc, THROWN_VAR) is None and p.get(wc, THROW_WINDING_VAR) is None
            and len(p.get(wc, "Inventory")) == carried
            and p.get(wc, "Held") == held, f"{len(p.get(wc, 'Inventory'))} carried")
    held_on = [v for v in LET_GO_VARS if p.get(wc, v)]
    p.check("...and holds no aim, sprint or guard", not held_on, str(held_on))
    # The HUD forgets the profile on death, once. Let that pass before the
    # real one is put back.
    yield lambda: p.get(p.hud(), PROFILE_FORGOTTEN_VAR)
