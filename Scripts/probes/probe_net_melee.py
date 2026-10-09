"""Melee, the guard and the fire held out are the server's (task M20): the
owning client asks, and the server swings, sweeps, hurts and decides.

    server     keeps one mindless zombie, tagged afraid of fire, 90 cm in
               front of client 1, and judges each step client 1 posts
    client 1   brings the knife to hand and queues a slash (the press gate's
               own write): the server's blow takes the knife's damage, by
               client 1's hand, with the server's knife
    server     heats ITS copy of the knife
    client 1   slashes again: twice the damage. The double is read off the
               server's item, not off anything the client says
    server     three Server_Slash in one frame land one blow: the cooldown
               is the server's
    client 1   puts the knife away and queues a punch: the fist's damage
    client 1   holds the guard: the server's copy is Blocking, and so is
               client 2's copy of client 1 (it replicates); let go, both drop
    client 1   brings the stick to hand and holds the use key: no FireWard on
               the server while its stick is not burning there; the server
               lights ITS stick and FireWard rises; the key let go, it falls

KnifeQueued, PunchQueued, BlockForced and SightsForced stand in for the keys.
Single player's checks are probes/probe_knife.py, probe_punch.py,
probe_hot_blade.py and probe_wendigo_ward.py, through the same events.
"""

SYSTEMS = ('net', 'melee')

import time

import unreal

from combat import health_vars as HV
from combat.heat_tuning import COOL_VAR, FIRE_FEAR_TAG, HOT_BLOW_SCALE, HOT_VAR
from combat.paths import (
    FIRE_WARD_VAR, HEALTH_BP_PATH, HEALTH_CLASS_PATH, ITEM_BP_PATH, WEAPON_COMP_BP_PATH,
    WEAPON_COMP_CLASS_PATH)
from combat.seat_tuning import SIGHTS_FORCED_VAR
from combat.slot_tuning import MELEE_SLOT
from combat.strike_vars import SERVER_SLASH, BlockForced
from combat.torch_tuning import BURN_OUT_VAR, LIT_VAR
from combat.tuning import COMBAT
from combat.weapon_component import vars as WV
from combat.weapon_component.knife import KNIFE_QUEUED_VAR, NEXT_KNIFE_VAR
from combat.weapon_component.punch import NEXT_PUNCH_VAR, PUNCH_QUEUED_VAR
from probes.probe_hot_blade import _of, _wanderers

RUNS_ON = ("server", "client")
WRITABLE = ([(WEAPON_COMP_BP_PATH, v) for v in
             (KNIFE_QUEUED_VAR, PUNCH_QUEUED_VAR, BlockForced, SIGHTS_FORCED_VAR,
              WV.EquippedIndex)]
            + [(ITEM_BP_PATH, v) for v in (HOT_VAR, COOL_VAR, LIT_VAR, BURN_OUT_VAR)]
            + [(HEALTH_BP_PATH, HV.Health)])

WAIT = 30.0
IN_FRONT_CM = 90.0
BODY_HP = 100000.0
KNIFE, STICK = "BP_Knife_C", "BP_Stick_C"


def _await(ready, seconds=WAIT):
    until = time.time() + seconds
    return lambda: ready() or time.time() > until


def _vec(v):
    return [v.x, v.y, v.z]


def _now(p):
    return unreal.GameplayStatics.get_time_seconds(p.world())


def _bodies(p):
    """(players', wanderers'): every character with a health component."""
    cls = p.load_class(HEALTH_CLASS_PATH)
    found = [a for a in unreal.GameplayStatics.get_all_actors_of_class(
        p.world(), unreal.Character) if a.get_component_by_class(cls)]
    mine = [a for a in found
            if not p.get(a.get_component_by_class(cls), HV.DespawnOnDeath)]
    return mine, [a for a in found if a not in mine]


def _nearest(actors, point):
    at = unreal.Vector(*point)
    return min(actors, key=lambda a: (a.get_actor_location() - at).length(), default=None)


def _name(item):
    return item.get_class().get_name() if item is not None else None


# ─── the server ──────────────────────────────────────────────────────────────

def probe_server(p):
    yield _await(lambda: p.posted("client 1", "pos"))
    if not p.posted("client 1", "pos"):
        p.check("client 1 said where it stands", False, "no post")
        return
    players, _npcs = _bodies(p)
    one = _nearest(players, p.posted("client 1", "pos"))
    wc = p.component(one, WEAPON_COMP_CLASS_PATH)
    # One zombie, left its mind and held in front of client 1; the rest are
    # gone, and the players have health to spare for its swings.
    body = _of(p, "Zombie").get_controlled_pawn()
    for other in _wanderers(p):
        pawn = other.get_controlled_pawn()
        if pawn and pawn != body:
            pawn.destroy_actor()
    for player in players:
        p.set(p.component(player, HEALTH_CLASS_PATH), HV.Health, BODY_HP)
    # p.set: without the edit notification, which re-runs the body's
    # construction script and loses the client its health component.
    p.set(body, "tags", list(body.get_editor_property("tags")) + [FIRE_FEAR_TAG])
    health = p.component(body, HEALTH_CLASS_PATH)
    p.set(health, HV.Health, BODY_HP)
    hp = lambda: float(p.get(health, HV.Health))

    def stand():
        body.set_actor_location(
            one.get_actor_location() + one.get_actor_forward_vector() * IN_FRONT_CM,
            False, True)
        return False

    def step(key, seconds=60.0):
        """Hold the body in front of client 1 until it posts ``key``; what
        the body lost meanwhile, or None with no post."""
        was = hp()
        ready = _await(lambda: stand() or p.posted("client 1", key), seconds)
        return was, ready

    stand()
    p.post("target", _vec(body.get_actor_location()))

    # --- a slash: the server's sweep, the server's damage ----------------------
    was, ready = step("slash")
    yield ready
    yield 0.2
    knife = p.get(wc, "Held")
    p.check("client 1's slash takes the knife's damage off the body on the server",
            abs((was - hp()) - COMBAT.knife_damage) < 1e-3 and _name(knife) == KNIFE,
            f"{was - hp():.0f} HP, with {_name(knife)} in the server's hand")
    p.check("...by client 1's hand, with the server's knife",
            p.get(health, HV.LastInstigator) == one.get_controller()
            and p.get(health, HV.LastCause) == knife,
            f"{p.get(health, HV.LastInstigator)}, {p.get(health, HV.LastCause)}")

    # --- the hot blade's double is read off the server's item --------------------
    p.set(knife, COOL_VAR, _now(p) + 300.0)
    p.set(knife, HOT_VAR, True)
    p.post("hot")
    was, ready = step("slash hot")
    yield ready
    yield 0.2
    p.check(f"with the server's knife hot, the next slash takes {HOT_BLOW_SCALE:g} times "
            "that off a body afraid of fire: the double is the server's",
            abs((was - hp()) - COMBAT.knife_damage * HOT_BLOW_SCALE) < 1e-3,
            f"{was - hp():.0f} HP")
    p.set(knife, HOT_VAR, False)

    # --- the cooldown is the server's ------------------------------------------
    yield _await(lambda: stand() or _now(p) > p.get(wc, NEXT_KNIFE_VAR) + 0.2, 5.0)
    was = hp()
    for _ in range(3):
        wc.call_method(SERVER_SLASH)
    yield _await(lambda: stand() or _now(p) > p.get(wc, NEXT_KNIFE_VAR) + 0.2, 5.0)
    p.check("three Server_Slash in one frame land one blow: the server keeps the "
            "knife's own rate", abs((was - hp()) - COMBAT.knife_damage) < 1e-3,
            f"{was - hp():.0f} HP")
    p.post("cooled")

    # --- a punch -----------------------------------------------------------------
    was, ready = step("punch")
    yield ready
    yield 0.2
    p.check("client 1's punch, with its hands empty on the server too, takes the "
            "fist's damage", abs((was - hp()) - COMBAT.punch_damage) < 1e-3
            and p.get(wc, "Held") is None, f"{was - hp():.0f} HP, {_name(p.get(wc, 'Held'))} in hand")

    # --- the guard ---------------------------------------------------------------
    yield _await(lambda: p.posted("client 1", "guard up"))
    yield _await(lambda: bool(p.get(wc, WV.Blocking)), 5.0)
    p.check("client 1 holds its guard: the server's copy is Blocking, by the "
            "server's own stamina", bool(p.get(wc, WV.Blocking)))
    p.post("guarding")
    yield _await(lambda: p.posted("client 1", "guard down"))
    yield _await(lambda: not p.get(wc, WV.Blocking), 5.0)
    p.check("...and lets it go: the server's copy drops it", not p.get(wc, WV.Blocking))
    p.post("lowered")

    # --- the fire held out ---------------------------------------------------------
    yield _await(lambda: p.posted("client 1", "use down"))
    yield 0.5
    stick = p.get(wc, "Held")
    p.check("client 1 holds the use key on a stick that is not burning on the "
            "server: no FireWard there", _name(stick) == STICK and not p.get(wc, FIRE_WARD_VAR),
            f"{_name(stick)} in hand, FireWard {p.get(wc, FIRE_WARD_VAR)}")
    if _name(stick) == STICK:
        p.set(stick, BURN_OUT_VAR, _now(p) + 300.0)
        p.set(stick, LIT_VAR, True)
        yield _await(lambda: bool(p.get(wc, FIRE_WARD_VAR)), 5.0)
        p.check("the server's stick burning, FireWard rises on the server: a wendigo "
                "reads the server's", bool(p.get(wc, FIRE_WARD_VAR)))
    p.post("warded")
    yield _await(lambda: p.posted("client 1", "use up"))
    yield _await(lambda: not p.get(wc, FIRE_WARD_VAR), 5.0)
    p.check("...and falls when client 1 lets the key go", not p.get(wc, FIRE_WARD_VAR))
    p.post("judged")


# ─── the clients ─────────────────────────────────────────────────────────────

def _hold(p, wc, name):
    bag = [_name(i) for i in p.get(wc, "Inventory")]
    p.hold(wc, bag.index(name))
    yield _await(lambda: _name(p.get(wc, "Held")) == name, 10.0)
    yield 0.3


def probe_client(p):
    mine = p.pawn()
    wc = p.component(mine, WEAPON_COMP_CLASS_PATH)
    yield _await(lambda: p.get(wc, "Held") is not None)
    yield 0.5
    if p.client == 1:
        p.post("pos", _vec(mine.get_actor_location()))
    yield _await(lambda: p.posted("server", "target"), 60.0)
    if not p.posted("server", "target"):
        return

    if p.client != 1:
        # Client 2 watches client 1's guard on its own copy of that character.
        yield _await(lambda: p.posted("server", "guarding"), 120.0)
        others = [a for a in _bodies(p)[0] if a != mine]
        theirs = p.component(others[0], WEAPON_COMP_CLASS_PATH) if others else None
        yield _await(lambda: theirs is not None and bool(p.get(theirs, WV.Blocking)), 5.0)
        p.check("client 2's copy of client 1 is Blocking: the guard replicates to "
                "the other players", theirs is not None and bool(p.get(theirs, WV.Blocking)))
        p.check("...and client 2's own character is not", not p.get(wc, WV.Blocking))
        yield _await(lambda: p.posted("server", "lowered"), 60.0)
        yield _await(lambda: theirs is not None and not p.get(theirs, WV.Blocking), 5.0)
        p.check("...and drops it when client 1 does",
                theirs is not None and not p.get(theirs, WV.Blocking))
        yield _await(lambda: p.posted("server", "judged"), 120.0)
        return

    p.posted("server", "target")
    # The body the server stands in front of this client, once it is seen there
    # (the others go as the server's destroys arrive).
    front = lambda: _nearest(_bodies(p)[1], _vec(
        mine.get_actor_location() + mine.get_actor_forward_vector() * IN_FRONT_CM))
    near = lambda: front() is not None and (
        front().get_actor_location() - mine.get_actor_location()).length() < 150.0
    yield _await(near)
    yield 0.5
    body = front()
    if not near():
        gaps = sorted((a.get_actor_location() - mine.get_actor_location()).length()
                      for a in _bodies(p)[1])
        p.check("client 1 sees the body the server stood in front of it", False,
                f"{len(gaps)} wanderer(s), the nearest {gaps[:3]} cm off; "
                f"{len(_bodies(p)[0])} player(s)")
        return
    health = p.component(body, HEALTH_CLASS_PATH)
    hp = lambda: float(p.get(health, HV.Health))

    def swing(queued_var, next_var):
        """Queue a swing off cooldown; what this client saw the body lose."""
        yield _await(lambda: _now(p) >= p.get(wc, next_var), 5.0)
        was = hp()
        p.set(wc, queued_var, True)
        yield _await(lambda: hp() < was, 5.0)
        return was - hp()

    # --- the knife: cold, then hot on the server ---------------------------------
    yield from _hold(p, wc, KNIFE)
    lost = yield from swing(KNIFE_QUEUED_VAR, NEXT_KNIFE_VAR)
    p.check("client 1 sees its slash land: the body's health, replicated, is down "
            "by the knife's damage", abs(lost - COMBAT.knife_damage) < 1e-3, f"{lost:.0f} HP")
    p.post("slash")
    yield _await(lambda: p.posted("server", "hot"))
    lost = yield from swing(KNIFE_QUEUED_VAR, NEXT_KNIFE_VAR)
    p.check("...and the next, with the server's knife hot, by twice that",
            abs(lost - COMBAT.knife_damage * HOT_BLOW_SCALE) < 1e-3, f"{lost:.0f} HP")
    p.post("slash hot")
    yield _await(lambda: p.posted("server", "cooled"))

    # --- the fist ------------------------------------------------------------------
    # The melee slot's key again puts the knife away (HandFrom is the server's).
    p.ask_slot(wc, MELEE_SLOT)
    yield _await(lambda: p.get(wc, "Held") is None, 10.0)
    yield 0.5
    lost = yield from swing(PUNCH_QUEUED_VAR, NEXT_PUNCH_VAR)
    p.check("client 1's punch lands: the fist's damage",
            abs(lost - COMBAT.punch_damage) < 1e-3, f"{lost:.0f} HP")
    p.post("punch")

    # --- the guard -----------------------------------------------------------------
    yield 0.5
    p.set(wc, BlockForced, True)
    yield _await(lambda: bool(p.get(wc, WV.Blocking)), 5.0)
    p.check("client 1's guard is up on its own copy at once, off its own key",
            bool(p.get(wc, WV.Blocking)))
    p.post("guard up")
    yield _await(lambda: p.posted("server", "guarding"))
    yield 1.0
    p.set(wc, BlockForced, False)
    p.post("guard down")
    yield _await(lambda: p.posted("server", "lowered"))

    # --- the fire held out -----------------------------------------------------------
    yield from _hold(p, wc, STICK)
    p.set(wc, SIGHTS_FORCED_VAR, True)
    yield 0.5
    p.post("use down")
    yield _await(lambda: p.posted("server", "warded"))
    p.set(wc, SIGHTS_FORCED_VAR, False)
    p.post("use up")
    yield _await(lambda: p.posted("server", "judged"))
