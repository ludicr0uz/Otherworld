"""hip-bloom: an automatic fired from the hip grows less accurate with each
round of a burst, and settles smoothly soon after the trigger is let go
(combat/bloom_tuning.py, weapon_component/bloom.py).

FireForced stands in for the fire key (held True it fires every cooldown).
The player stands still, so the gun's own cloud does not move under the
burst.

  - the pistol (not automatic), fired from the hip, adds nothing;
  - the SMG at the hip, before a round: Bloom is 0, AimSpread the gun's own;
  - held for BURST_S: Bloom climbs round by round (never falls mid-burst)
    to BLOOM_MAX, and AimSpread to (1 + BLOOM_MAX) times the gun's own;
  - let go: Bloom holds while the hold lasts, then falls every frame, never
    rises, and is under SETTLED of the cap within SETTLE_S;
  - down the sights (SightsForced for the key, until SightAiming, what the
    bloom reads), a burst adds nothing.

The level's creatures are taken away before each burst: gunfire draws
them, and a player they kill stops ticking, the bloom with it.

Any profile on disk is set aside first, so the game starts on the issued
loadout, and put back at the end.
"""

SYSTEMS = ('weapons',)

import os
import shutil
import time

import unreal

from combat.bloom_tuning import BLOOM_HOLD_S, BLOOM_MAX, Bloom, BloomShotTime
from combat.seat_tuning import SIGHTS_FORCED_VAR
from combat.paths import ITEM_BP_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat import item_vars as IV
from combat.weapon_component import vars as WV
from combat.weapon_component.accuracy import AIM_SPREAD_VAR
from combat.weapon_component.dead import OWNER_DEAD_VAR
from combat.weapon_component.tick import FIRE_FORCED_VAR
from graphics_menu.dev_consts import DEV_GUNS_REQUEST_VAR
from graphics_menu.profile_consts import PROFILE_CHECKED_VAR, PROFILE_SLOT

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = [(HUD_BP_PATH, DEV_GUNS_REQUEST_VAR), (ITEM_BP_PATH, IV.Loaded)] + [
    (WEAPON_COMP_BP_PATH, v) for v in (FIRE_FORCED_VAR, SIGHTS_FORCED_VAR, WV.EquippedIndex,
                                    WV.NeedsRefresh)]

SETTLE_EQUIP_S = 0.8    # the equip, the gun coming up
BURST_S = 2.0           # game seconds of fire: the SMG is capped in 1.2
SETTLE_S = 1.0          # after the hold, the bloom is all but gone within this
SETTLED = 0.1           # ...under this fraction of the cap
SPREAD_TOL = 0.05       # AimSpread against (1 + Bloom) x the gun's own
WALL_WAIT_S = 30.0      # a headless game's clock is slow: bound waits by the wall
TIMEOUT = 150.0         # wall seconds: three bursts sampled once a frame


def _file():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames",
                        f"{PROFILE_SLOT}.sav")


def _live_hud(p):
    try:
        hud = p.hud()
    except Exception:
        return None
    return hud if hud is not None and p.get(hud, PROFILE_CHECKED_VAR) else None


def _until(cond):
    end = time.time() + WALL_WAIT_S
    return lambda: cond() or time.time() > end


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _held_name(p, wc):
    held = p.get(wc, "Held")
    return held.get_class().get_name() if held else None


def _equip(p, wc, cls):
    bag = [i.get_class().get_name() for i in p.get(wc, "Inventory")]
    if cls not in bag:
        p.check(f"{cls} is in the bag", False, str(bag))
        return False
    p.set(wc, str(WV.EquippedIndex), bag.index(cls))
    p.set(wc, str(WV.NeedsRefresh), True)
    yield _until(lambda: _held_name(p, wc) == cls)
    yield SETTLE_EQUIP_S
    p.check(f"{cls} is held", _held_name(p, wc) == cls,
            f"{_held_name(p, wc)}, at {time.time() - _T0[0]:.0f} s wall")
    return _held_name(p, wc) == cls


def _clear_creatures(p):
    """Take the level's creatures away: gunfire draws them, and a player
    they kill stops ticking (the bloom with it)."""
    ctrls = unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.AIController)
    pawns = [c.get_controlled_pawn() for c in ctrls]
    for pawn in pawns:
        if pawn is not None:
            pawn.destroy_actor()
    for c in ctrls:
        c.destroy_actor()
    return sum(1 for pawn in pawns if pawn is not None)


def _burst(p, wc, seconds, samples):
    """Hold the trigger for ``seconds`` of game time, sampling once a frame
    (game time, Bloom, AimSpread); the magazine kept full."""
    _clear_creatures(p)
    gun = p.get(wc, "Held")
    p.set(wc, FIRE_FORCED_VAR, True)
    end = p.time() + seconds
    wall = time.time() + WALL_WAIT_S
    rounds = 0
    while p.time() < end and time.time() < wall:
        full = p.get(gun, IV.MagazineSize)
        rounds += full - p.get(gun, IV.Loaded)
        p.set(gun, IV.Loaded, full)
        samples.append((p.time(), p.get(wc, str(Bloom)), p.get(wc, AIM_SPREAD_VAR)))
        yield 0.0
    p.set(wc, FIRE_FORCED_VAR, False)
    return rounds


_T0 = [0.0]


def _run(p):
    _T0[0] = time.time()
    yield _until(lambda: _live_hud(p) is not None)
    hud = _live_hud(p)
    p.check("the HUD is up", hud is not None)
    if hud is None:
        return
    p.note(f"took away {_clear_creatures(p)} creature(s)")
    wc = p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)
    p.set(hud, DEV_GUNS_REQUEST_VAR, True)
    yield _until(lambda: not p.get(hud, DEV_GUNS_REQUEST_VAR))
    yield 0.3

    if (yield from _equip(p, wc, "BP_Pistol_C")):
        samples = []
        rounds = yield from _burst(p, wc, 1.0, samples)
        top = max(s[1] for s in samples) if samples else None
        p.check("the pistol (semi-automatic) fired from the hip adds no bloom",
                rounds > 0 and top == 0.0, f"{rounds} round(s), max Bloom {top}")
    if (yield from _equip(p, wc, "BP_SMG_C")):
        yield from _hip_burst(p, wc)
        yield from _sights_burst(p, wc)

def _hip_burst(p, wc):
    bloom0 = p.get(wc, str(Bloom))
    own = p.get(wc, AIM_SPREAD_VAR)
    p.check("the player is alive", not p.get(wc, OWNER_DEAD_VAR))
    p.check("before a round, Bloom is 0 and the cloud is the gun's own",
            bloom0 == 0.0 and own > 0.0, f"Bloom {bloom0}, AimSpread {own:.4f}")
    samples = []
    rounds = yield from _burst(p, wc, BURST_S, samples)
    blooms = [s[1] for s in samples]
    falls = [(a, b) for a, b in zip(blooms, blooms[1:]) if b < a - 1e-6]
    rises = sum(1 for a, b in zip(blooms, blooms[1:]) if b > a + 1e-6)
    p.check("held, Bloom climbs round by round and never falls mid-burst",
            rises >= 5 and not falls,
            f"{rounds} rounds, {rises} rises, falls {falls[:3]}, {len(samples)} frames")
    top, spread = samples[-1][1], samples[-1][2]
    p.check(f"...to the cap, {BLOOM_MAX:g}", abs(top - BLOOM_MAX) < 1e-3,
            f"Bloom {top:.3f}")
    want = own * (1.0 + top)
    p.check("...and AimSpread is (1 + Bloom) times the gun's own",
            abs(spread - want) <= SPREAD_TOL * want,
            f"{own:.4f} -> {spread:.4f}, want {want:.4f}")

    # Let go: hold, then a smooth fall.
    t0 = p.time()
    gun = p.get(wc, "Held")
    loaded0 = p.get(gun, IV.Loaded)
    trail = []
    wall = time.time() + WALL_WAIT_S
    while p.time() < t0 + BLOOM_HOLD_S + SETTLE_S and time.time() < wall:
        trail.append((p.time() - t0, p.get(wc, str(Bloom))))
        yield 0.0
    held = [b for t, b in trail if t < BLOOM_HOLD_S * 0.5]
    p.check(f"let go, Bloom holds for the first part of the {BLOOM_HOLD_S:g} s hold",
            bool(held) and min(held) >= top - 1e-3, f"{held[:4]}")
    up = [(a, b) for a, b in zip(trail, trail[1:]) if b[1] > a[1] + 1e-6]
    p.check("...then falls without ever rising", not up, str(up[:3]))
    steps = [a[1] - b[1] for a, b in zip(trail, trail[1:]) if a[1] > b[1]]
    p.check("...smoothly, over many frames, no step more than a third of the cap",
            len(steps) >= 5 and max(steps) < BLOOM_MAX / 3,
            f"{len(steps)} steps, largest {max(steps) if steps else None}")
    p.note(f"after the release: Loaded {loaded0} -> {p.get(gun, IV.Loaded)}, "
           f"BloomShotTime {p.get(wc, str(BloomShotTime)):.2f}, now {p.time():.2f}, "
           f"OwnerDead {p.get(wc, OWNER_DEAD_VAR)}")
    last = trail[-1][1] if trail else None
    p.check(f"...and is under {SETTLED:g} of the cap {SETTLE_S:g} s after the hold",
            last is not None and last < SETTLED * BLOOM_MAX,
            f"Bloom {last}, {len(trail)} frames over {trail[-1][0] if trail else 0:.2f} s")


def _sights_burst(p, wc):
    yield 0.5
    p.set(wc, SIGHTS_FORCED_VAR, True)
    yield _until(lambda: p.get(wc, str(WV.SightAiming)))
    yield 0.3
    p.check("down the sights (SightAiming)", p.get(wc, str(WV.SightAiming)))
    start = p.get(wc, str(Bloom))
    samples = []
    rounds = yield from _burst(p, wc, 1.0, samples)
    top = max(s[1] for s in samples) if samples else None
    p.check("a burst down the sights adds no bloom",
            rounds > 1 and start < 0.01 and top <= start,
            f"{rounds} round(s), from {start:.4f}, max {top}")
    p.set(wc, SIGHTS_FORCED_VAR, False)
