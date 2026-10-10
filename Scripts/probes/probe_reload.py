"""The reload's arithmetic, which is the native base's since W2 (C++,
OtherworldWeaponComponentBase::ReloadNow and its ReloadTake).

In the graph the number of rounds a reload moves was a pure node, stored in a
variable because a second read of it after Loaded rose charged the reserve
less than the magazine gained: free ammunition. This holds the C++ to the
same sums, single player, through the reload key's stand-in (ReloadForced),
so the whole path is run: the Tick's key, Server_Reload, ReloadNow.

    a short reserve     the magazine gains what the reserve holds and no more,
                        and the reserve loses exactly that
    an empty reserve    nothing moves: no round, no pause, no reload counted
    a full magazine     the same
    a full reload       the magazine's gap, out of the reserve
    the pistol          an endless reserve fills the whole gap, even from a
                        count below zero, and is not charged

The key is held for several frames each time, so a reload is also asked for
again straight after it filled the magazine: one reload counted, not several.
"""

SYSTEMS = ('weapons',)

import unreal

from combat import item_vars as IV
from combat.paths import ITEM_BP_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.shot_vars import ReloadForced
from combat.slot_tuning import NO_REQUEST, PISTOL_SLOT, SLOT_REQUEST_VAR

WRITABLE = [(WEAPON_COMP_BP_PATH, ReloadForced), (WEAPON_COMP_BP_PATH, SLOT_REQUEST_VAR),
            (ITEM_BP_PATH, IV.Loaded), (ITEM_BP_PATH, IV.Reserve)]
HOLD = 0.4       # game seconds the key is held: many frames
SPARE = 50


def _rounds(p, gun):
    return int(p.get(gun, IV.Loaded)), int(p.get(gun, IV.Reserve))


def _press(p, wc, gun, loaded, reserve):
    """Give the gun these rounds, hold the reload key, and return what came of
    it: (rounds after, reloads counted, the deadline before, after, the clock
    when the key went down)."""
    p.set(gun, IV.Loaded, loaded)
    p.set(gun, IV.Reserve, reserve)
    yield 0.1
    count = int(p.get(wc, "Reloads"))
    deadline = float(p.get(gun, IV.NextFireTime))
    now = unreal.GameplayStatics.get_time_seconds(p.world())
    p.set(wc, ReloadForced, True)
    yield HOLD
    p.set(wc, ReloadForced, False)
    yield 0.1
    return (_rounds(p, gun), int(p.get(wc, "Reloads")) - count, deadline,
            float(p.get(gun, IV.NextFireTime)), now)


def probe(p):
    yield 0.5
    wc = p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)
    yield lambda: p.get(wc, "Held") is not None
    gun = p.get(wc, "Held")
    mag = int(p.get(gun, IV.MagazineSize))
    pause = float(p.get(gun, IV.ReloadSeconds))
    if not p.check("the player holds a gun with a magazine of four or more and a "
                   "reserve that ends", p.get(gun, IV.UsesAmmo) and mag >= 4
                   and not p.get(gun, IV.InfiniteReserve),
                   f"{gun.get_class().get_name()}, magazine {mag}"):
        return

    got, count, _was, deadline, now = yield from _press(p, wc, gun, mag - 4, 1)
    p.check("a reserve of one tops a magazine that is four short up by one, and is "
            "charged that one", got == (mag - 3, 0) and count == 1,
            f"({mag - 4}, 1) -> {got}, {count} reload(s)")
    p.check(f"...and the gun pauses its ReloadSeconds ({pause:g} s) on NextFireTime",
            abs(deadline - (now + pause)) < 0.25, f"{deadline - now:.2f} s from the key")

    got, count, was, deadline, _now = yield from _press(p, wc, gun, mag - 3, 0)
    p.check("with nothing in reserve the key moves nothing: no round, no pause, no "
            "reload", got == (mag - 3, 0) and count == 0 and deadline == was,
            f"{got}, {count} reload(s), the deadline moved {deadline - was:.2f} s")

    got, count, was, deadline, _now = yield from _press(p, wc, gun, mag, SPARE)
    p.check("...nor with a full magazine", got == (mag, SPARE) and count == 0
            and deadline == was, f"{got}, {count} reload(s)")

    got, count, _was, _deadline, _now = yield from _press(p, wc, gun, 0, SPARE)
    p.check("an empty magazine is filled out of the reserve, which loses exactly what "
            "the magazine gained, once however long the key is held",
            got == (mag, SPARE - mag) and count == 1, f"(0, {SPARE}) -> {got}, {count} reload(s)")

    # --- the pistol: an endless reserve ---------------------------------------
    p.set(wc, SLOT_REQUEST_VAR, PISTOL_SLOT)
    yield lambda: p.get(wc, SLOT_REQUEST_VAR) == NO_REQUEST
    yield lambda: p.get(wc, "Held") not in (None, gun)
    pistol = p.get(wc, "Held")
    mag = int(p.get(pistol, IV.MagazineSize))
    if not p.check("the pistol comes to hand, its reserve endless",
                   bool(p.get(pistol, IV.InfiniteReserve)), pistol.get_class().get_name()):
        return
    got, count, _was, _deadline, _now = yield from _press(p, wc, pistol, 2, 0)
    p.check("the pistol fills its whole gap with nothing in reserve, and is not charged",
            got == (mag, 0) and count == 1, f"(2, 0) -> {got}, {count} reload(s)")
    got, count, _was, _deadline, _now = yield from _press(p, wc, pistol, -3, 7)
    p.check("...even from a count below zero (an older save's), its reserve as it was",
            got == (mag, 7) and count == 1, f"(-3, 7) -> {got}, {count} reload(s)")
