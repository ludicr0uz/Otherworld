"""The matches and the campfire: a strike with wood in the bag lights a fire in
front of the player, and standing near it raises the player's Temperature.

The player must start carrying BP_Matches, fifth of the six issued items. A
strike is the fire key with the matches in hand; FireForced stands in for the
key (no key can be injected into a headless game).

  - with no wood in the bag, a strike lights nothing and spends nothing;
  - the wood is cut the way the game gives it: the player is stood at a tree
    and swings the axe (probe_chop_tree.py's steps), then takes the log up;
  - the bag is then turned round so the wood sits BEFORE the matches: spending
    it moves the matches down a slot, and EquippedIndex must follow;
  - a strike spends the wood, keeps the matches in hand, and leaves one
    BP_Campfire on the ground CAMPFIRE_AHEAD_CM in front of the player;
  - beside the fire the Temperature rises by the fire's rate x the game time
    that passed; out of its radius it holds; a huge rate stops at the maximum.

The fire's rate is raised for the run (a headless game's time moves in tiny
steps, and the built 1 a second would not show in a probe's fraction of a
second), and the night's cold is switched off so the level's random hour
cannot take back what the fire gives. Any profile on disk is set aside first,
so the game starts on the issued loadout, and put back at the end.
"""

import os
import shutil

import unreal

from combat.chop_tuning import CHOPS_PER_WOOD
from combat.light_tuning import CAMPFIRE_AHEAD_CM, CAMPFIRE_CLASS_VAR, LIGHTS_VAR
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.weapon_component.knife import KNIFE_QUEUED_VAR
from combat.weapon_component.interact import INTERACT_FORCED_VAR
from combat.weapon_component.tick import FIRE_FORCED_VAR
from probes.probe_chop_tree import (
    AXE, CLEAR_CM, WOOD, _equip, _flat, _items, _stand, _swing, _trace, _trees,
)
from probes.probe_knife import _file, _held_name
from survival.campfire import WARM_RADIUS_VAR, WARM_RATE_VAR
from survival.paths import (
    CAMPFIRE_BP_PATH, CAMPFIRE_CLASS_PATH, SURVIVAL_BP_PATH, SURVIVAL_CLASS_PATH,
)
from survival.tuning import (
    CAMPFIRE_WARM_PER_S, CAMPFIRE_WARM_RADIUS_CM, SURVIVAL,
)
from world.day_night_blueprint import NIGHT_COLD_VAR
from world.paths import DAY_NIGHT_BP_PATH, DAY_NIGHT_CLASS_PATH

WRITABLE = ([(WEAPON_COMP_BP_PATH, v) for v in
             ("EquippedIndex", "NeedsRefresh", "Inventory", KNIFE_QUEUED_VAR,
              INTERACT_FORCED_VAR, FIRE_FORCED_VAR)]
            + [(SURVIVAL_BP_PATH, "Temperature"), (CAMPFIRE_BP_PATH, WARM_RATE_VAR),
               (DAY_NIGHT_BP_PATH, NIGHT_COLD_VAR)])

MATCHES = "BP_Matches_C"
STARTERS = ["BP_Shotgun_C", "BP_Pistol_C", "BP_Knife_C", AXE, MATCHES]
ISSUED = STARTERS + ["BP_Stick_C"]   # the stick is issued after them (probe_lit_stick.py)
RATE = 20.0
COOL = 50.0               # a Temperature with room to rise
WATCH = 0.3
AWAY_CM = 1500.0          # well outside the fire's radius


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _bag(p, wc):
    return [i.get_class().get_name() for i in p.get(wc, "Inventory")]


def _fires(p):
    return list(unreal.GameplayStatics.get_all_actors_of_class(
        p.world(), p.load_class(CAMPFIRE_CLASS_PATH)))


def _strike(p, wc):
    p.set(wc, FIRE_FORCED_VAR, True)
    yield 0.1
    p.set(wc, FIRE_FORCED_VAR, False)
    yield 0.1


def _watch(p, survival):
    """(Temperature gained, game seconds passed) over WATCH, from COOL."""
    p.set(survival, "Temperature", COOL)
    t0 = unreal.GameplayStatics.get_time_seconds(p.world())
    yield WATCH
    return (p.get(survival, "Temperature") - COOL,
            unreal.GameplayStatics.get_time_seconds(p.world()) - t0)


def _cut_wood(p, player, wc):
    """Stand at a tree, cut one piece of wood and take it up. True if the bag
    then holds it."""
    lying = [a.get_actor_location() for a in _items(p) if p.get(a, "Dropped")]
    here = player.get_actor_location()
    spot = None
    for _comp, _index, base in sorted(_trees(p), key=lambda t: (t[2] - here).length()):
        if any(_flat(at - base) < CLEAR_CM for at in lying):
            continue
        spot = _stand(p, player, base)
        if spot:
            break
    if spot is None:
        return False
    at, yaw = spot[0], spot[1]
    turn = unreal.Rotator(pitch=0.0, yaw=yaw, roll=0.0)
    player.set_actor_location_and_rotation(at, turn, False, True)
    player.get_controller().set_control_rotation(turn)
    yield 0.3
    player.set_actor_location_and_rotation(at, turn, False, True)
    yield from _equip(p, wc, AXE)
    for _ in range(CHOPS_PER_WOOD):
        yield from _swing(p, wc)
    p.set(wc, INTERACT_FORCED_VAR, True)
    yield lambda: not p.get(wc, INTERACT_FORCED_VAR)
    yield 0.05
    return _bag(p, wc).count(WOOD) == 1


def _run(p):
    yield lambda: p.pawn() is not None
    yield 0.5
    player = p.pawn()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    survival = p.component(player, SURVIVAL_CLASS_PATH)
    p.check("the player has a weapon component and a survival component",
            wc is not None and survival is not None)
    if wc is None or survival is None:
        return
    cycle = p.actor_of(DAY_NIGHT_CLASS_PATH)
    if cycle is not None:
        p.set(cycle, NIGHT_COLD_VAR, 0.0)

    bag = _bag(p, wc)
    p.check("the matches are issued, after the shotgun, the pistol, the knife and the axe",
            bag == ISSUED, str(bag))
    if MATCHES not in bag:
        return
    matches = list(p.get(wc, "Inventory"))[bag.index(MATCHES)]
    p.check("...carried, named for the HUD, with their icon, and the one item that Lights",
            not p.get(matches, "Dropped") and str(p.get(matches, "DisplayName")) == "Matches"
            and p.get(matches, "Icon") is not None
            and [n for n, i in zip(bag, p.get(wc, "Inventory")) if p.get(i, LIGHTS_VAR)]
            == [MATCHES], f"{p.get(matches, 'DisplayName')} {p.get(matches, 'Icon')}")
    cls = p.get(wc, CAMPFIRE_CLASS_VAR)
    p.check("the weapon component knows what to light (BP_Campfire)",
            cls is not None and cls.get_name() == "BP_Campfire_C", str(cls))

    yield from _equip(p, wc, MATCHES)
    p.check("equipped like any item, the matches are in hand",
            p.get(wc, "Held") == matches and matches.get_attach_parent_actor() == player
            and not matches.get_editor_property("hidden"), _held_name(p, wc))
    yield from _strike(p, wc)
    p.check("a strike with no wood in the bag lights nothing and spends nothing",
            not _fires(p) and _bag(p, wc) == ISSUED and p.get(wc, "Held") == matches,
            f"fires {len(_fires(p))}, bag {_bag(p, wc)}")

    got = yield from _cut_wood(p, player, wc)
    p.check("the axe cuts a piece of wood and E takes it into the bag", got,
            str(_bag(p, wc)))
    if not got:
        return
    items = list(p.get(wc, "Inventory"))
    log = next(i for i in items if i.get_class().get_name() == WOOD)
    # The wood before the matches: spending it moves the matches down a slot.
    p.set(wc, "Inventory", [log] + [i for i in items if i != log])
    yield from _equip(p, wc, MATCHES)
    p.check("the bag turned round: the wood first, the matches last and in hand",
            _bag(p, wc) == [WOOD] + ISSUED and p.get(wc, "Held") == matches
            and p.get(wc, "EquippedIndex") == len(STARTERS),
            f"{_bag(p, wc)} index {p.get(wc, 'EquippedIndex')}")

    here, ahead = player.get_actor_location(), player.get_actor_forward_vector()
    yield from _strike(p, wc)
    fires = _fires(p)
    p.check("a strike with wood in the bag lights one campfire", len(fires) == 1,
            str(len(fires)))
    p.check("...spends the wood: out of the bag and out of the world",
            _bag(p, wc) == ISSUED and not _items(p, WOOD),
            f"{_bag(p, wc)}, wood in the world {len(_items(p, WOOD))}")
    p.check("...keeps the matches, still in hand, EquippedIndex following them down a slot",
            p.get(wc, "Held") == matches and not matches.get_editor_property("hidden")
            and p.get(wc, "EquippedIndex") == STARTERS.index(MATCHES),
            f"held {_held_name(p, wc)} index {p.get(wc, 'EquippedIndex')}")
    if len(fires) != 1:
        return
    fire = fires[0]
    at = fire.get_actor_location()
    off = at - here
    floor = _trace(p, at + unreal.Vector(0, 0, 100.0), at - unreal.Vector(0, 0, 300.0),
                   [player])
    p.check(f"the fire is {CAMPFIRE_AHEAD_CM:.0f} cm in front of the player",
            abs(_flat(off) - CAMPFIRE_AHEAD_CM) < 5.0
            and (off.x * ahead.x + off.y * ahead.y) > 0.95 * _flat(off),
            f"{_flat(off):.1f} cm off, {off} against {ahead}")
    p.check("...standing on the ground there",
            floor is not None and abs(floor[4].z - at.z) < 2.0,
            f"fire z {at.z:.1f}, ground {floor[4].z if floor else None}")
    p.check("...and it blocks nothing: the trace that found the ground did not find it",
            floor is not None and floor[9] != fire, str(floor[9] if floor else None))
    yield from _strike(p, wc)
    p.check("another strike, the wood gone, lights no second fire", len(_fires(p)) == 1,
            str(len(_fires(p))))

    built = (p.get(fire, WARM_RATE_VAR), p.get(fire, WARM_RADIUS_VAR))
    p.check("the fire's warmth and radius are survival.tuning's",
            abs(built[0] - CAMPFIRE_WARM_PER_S) < 1e-6
            and abs(built[1] - CAMPFIRE_WARM_RADIUS_CM) < 1e-6, str(built))
    p.set(fire, WARM_RATE_VAR, RATE)
    gap = (player.get_actor_location() - at).length()
    gained, dt = yield from _watch(p, survival)
    p.check("beside the fire the Temperature rises by its rate x the game time that passed",
            gap < CAMPFIRE_WARM_RADIUS_CM and dt > 0 and gained > 0
            and abs(gained - RATE * dt) <= 0.25 * RATE * dt + 1e-3,
            f"{gap:.0f} cm away: +{gained:.4f} in {dt:.4f} s, {RATE} a second wants "
            f"{RATE * dt:.4f}")

    near = player.get_actor_location()
    far = near - ahead * AWAY_CM
    ground = _trace(p, far + unreal.Vector(0, 0, 1000.0), far - unreal.Vector(0, 0, 2000.0),
                    [player])
    if ground is not None:
        far.z = ground[4].z + (near.z - at.z)
    player.set_actor_location(far, False, True)
    yield 0.1
    gap = (player.get_actor_location() - at).length()
    gained, dt = yield from _watch(p, survival)
    p.check("out of its radius the Temperature holds",
            gap > CAMPFIRE_WARM_RADIUS_CM and gained == 0.0 and dt > 0,
            f"{gap:.0f} cm away: +{gained} in {dt:.3f} s")

    player.set_actor_location(near, False, True)
    p.set(fire, WARM_RATE_VAR, 1.0e7)
    yield lambda: p.get(survival, "Temperature") >= SURVIVAL.max_temperature
    yield 0.1
    p.check("a huge rate stops at the maximum, not above",
            p.get(survival, "Temperature") == SURVIVAL.max_temperature,
            repr(p.get(survival, "Temperature")))
