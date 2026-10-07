"""Survival is the server's, and a player's bars are their own (M26).

    python3 Scripts/dev/uepy.py --net --clients 2 --probe Scripts/probes/probe_net_survival.py

Hunger, Thirst and Temperature are BP_SurvivalComponent's, written only with
authority and replicated to the owning client alone
(survival/survival_component.py); eating is Server_Consume on the weapon
component (combat/weapon_component/consume.py), which sends GA_ConsumeItem its
event on the server; a debuff is an effect on the character's ability system,
which replicates (survival/install.py), so its tag reaches the owner's HUD.

    the server  sets both characters' Hunger to 50 and client 1's Temperature
                to 33, gives client 1's character one of the level's
                mushrooms (its own Server_Take), and later empties client 1's
                Thirst
    client 1    is sent its 50 and its 33; brings the mushroom to hand and
                presses the fire key: its own Hunger rises by the mushroom's
                25, and the mushroom leaves its bag; then is sent the
                dehydrated tag
    client 2    its own Hunger does not rise, it has no debuff, and its copy
                of client 1's character is told none of client 1's bars

Single player (`--game`) eats the same way on the one machine: Server_Consume
is a plain call there.

A client's key is FireForced, which the component's Tick turns into the
Server event where the key is read: a Blueprint Server event called from
Python is not sent.
"""

import time

import unreal

from combat import item_vars as IV
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.record_vars import FORCED
from combat.slot_tuning import SLOT_VAR
from combat.strike_vars import SERVER_TAKE
from combat.tuning import SERVER_CONSUME
from combat.weapon_component import vars as WV
from combat.weapon_component.tick import FIRE_FORCED_VAR
from probes.probe_chop_tree import _items
from survival import component_vars as UV
from survival.paths import SURVIVAL_BP_PATH, SURVIVAL_CLASS_PATH
from survival.tuning import DEHYDRATED_TAG, MUSHROOM_HUNGER, SURVIVAL

RUNS_ON = ("server", "client", "standalone")
WRITABLE = ([(WEAPON_COMP_BP_PATH, str(v)) for v in FORCED + (FIRE_FORCED_VAR,)]
            + [(SURVIVAL_BP_PATH, str(v)) for v in (UV.Hunger, UV.Thirst, UV.Temperature)])
WAIT = 20.0
HUNGRY = 50.0       # well under the cap, so a mushroom's 25 shows whole
CHILLY = 33.0
# A bar the server set is read back a little lower: it decays as it travels.
SLACK = 2.0


def _await(ready, seconds=WAIT):
    until = time.time() + seconds
    yield lambda: ready() or time.time() > until


def _wc(p, actor):
    return p.component(actor, WEAPON_COMP_CLASS_PATH)


def _stats(p, actor):
    return p.component(actor, SURVIVAL_CLASS_PATH)


def _bar(p, actor, var):
    return float(p.get(_stats(p, actor), str(var)))


def _near(value, want):
    return want - SLACK <= value <= want + 0.01


def _tags(p, actor, tag=DEHYDRATED_TAG):
    asc = unreal.AbilitySystemLibrary.get_ability_system_component(actor)
    return asc.get_gameplay_tag_count(p.tag(tag)) if asc else -1


def _mushrooms(p, wc):
    """{slot code} of the mushrooms in the bag, off the item actors."""
    return [p.get(i, SLOT_VAR) for i in p.get(wc, WV.Inventory)
            if i and unreal.SystemLibrary.is_valid(i)
            and i.get_class().get_name() == "BP_Mushroom_C"]


def _give_mushroom(p, pawn, wc):
    lying = [a for a in _items(p, "BP_Mushroom_C") if p.get(a, IV.Dropped)]
    if lying:
        lying[0].set_actor_location(pawn.get_actor_location(), False, True)
        wc.call_method(SERVER_TAKE, (lying[0],))
    yield 0.3
    return len(_mushrooms(p, wc))


def _eat(p, pawn, wc):
    """Bring the mushroom to hand and press the fire key. Returns the hunger
    before the press."""
    p.ask_slot(wc, _mushrooms(p, wc)[0])
    yield from _await(lambda: p.get(wc, WV.Held) is not None
                      and p.get(wc, WV.Held).get_class().get_name() == "BP_Mushroom_C", 8.0)
    before = _bar(p, pawn, UV.Hunger)
    p.set(wc, FIRE_FORCED_VAR, True)
    yield 0.15
    p.set(wc, FIRE_FORCED_VAR, False)
    yield from _await(lambda: _bar(p, pawn, UV.Hunger) > before + 1.0, 8.0)
    yield 0.3
    return before


# ─── the server ──────────────────────────────────────────────────────────────

def probe_server(p):
    yield from _await(lambda: all(p.posted(f"client {i}", "id") is not None
                                  for i in (1, 2)))
    by_id = {c.player_state.player_id: c.get_controlled_pawn()
             for c in p.players() if c.player_state}
    one, two = (by_id.get(p.posted(f"client {i}", "id")) for i in (1, 2))
    p.check("the server has both clients' characters", bool(one) and bool(two),
            str(sorted(by_id)))
    if not (one and two):
        return
    for pawn in (one, two):
        p.set(_stats(p, pawn), str(UV.Hunger), HUNGRY)
    p.set(_stats(p, one), str(UV.Temperature), CHILLY)
    held = yield from _give_mushroom(p, one, _wc(p, one))
    p.check("the server gave client 1's character a mushroom", held == 1, f"{held} in the bag")
    p.post("set")

    yield from _await(lambda: p.posted("client 1", "ate") is not None, 60.0)
    yield 0.3
    mine, theirs = _bar(p, one, UV.Hunger), _bar(p, two, UV.Hunger)
    p.check(f"after client 1's meal the server's copy of its Hunger is up by the "
            f"mushroom's {MUSHROOM_HUNGER:.0f}, and client 2's is not",
            _near(mine, HUNGRY + MUSHROOM_HUNGER) and _near(theirs, HUNGRY)
            and not _mushrooms(p, _wc(p, one)),
            f"client 1 {mine:.2f}, client 2 {theirs:.2f}")
    p.post("hunger", (mine, theirs))

    # A debuff: client 1's Thirst at zero, and the server's sync applies it.
    p.set(_stats(p, one), str(UV.Thirst), 0.0)
    yield from _await(lambda: _tags(p, one) > 0, 8.0)
    p.check(f"the server puts {DEHYDRATED_TAG} on client 1's ability system when its "
            "Thirst is 0, and not on client 2's",
            _tags(p, one) == 1 and _tags(p, two) == 0,
            f"client 1 {_tags(p, one)}, client 2 {_tags(p, two)}")
    p.post("thirsty")
    yield from _await(lambda: all(p.posted(f"client {i}", "done") is not None
                                  for i in (1, 2)), 60.0)


# ─── a client ────────────────────────────────────────────────────────────────

def probe_client(p):
    mine = p.pawn()
    wc = _wc(p, mine)
    yield from _await(lambda: p.get(wc, WV.Held) is not None
                      and p.player_state() is not None)
    p.post("id", p.player_state().player_id)
    yield from _await(lambda: p.posted("server", "set") is not None, 60.0)
    yield from _await(lambda: _near(_bar(p, mine, UV.Hunger), HUNGRY), 8.0)
    hunger = _bar(p, mine, UV.Hunger)
    p.check(f"client {p.client} is sent its own Hunger, the {HUNGRY:.0f} the server set, "
            "and has authority over none of it",
            _near(hunger, HUNGRY) and not mine.has_authority(), f"{hunger:.2f}")

    if p.client == 1:
        yield from _await(lambda: _near(_bar(p, mine, UV.Temperature), CHILLY)
                          and bool(_mushrooms(p, wc)), 8.0)
        temp = _bar(p, mine, UV.Temperature)
        p.check(f"client 1 is sent its Temperature, {CHILLY:.0f}, and the mushroom",
                _near(temp, CHILLY) and len(_mushrooms(p, wc)) == 1,
                f"{temp:.2f}, {len(_mushrooms(p, wc))} mushroom(s)")
        before = yield from _eat(p, mine, wc)
        after = _bar(p, mine, UV.Hunger)
        p.check(f"client 1 eats (the fire key, {SERVER_CONSUME}): its own Hunger rises "
                f"by the mushroom's {MUSHROOM_HUNGER:.0f}",
                _near(after, before + MUSHROOM_HUNGER), f"{before:.2f} -> {after:.2f}")
        yield from _await(lambda: not _mushrooms(p, wc), 8.0)
        p.check("...and the mushroom is out of its bag", not _mushrooms(p, wc),
                f"{len(_mushrooms(p, wc))} left")
        p.post("ate")
        yield from _await(lambda: p.posted("server", "hunger") is not None, 30.0)
        told = p.posted("server", "hunger") or (0.0, 0.0)
        p.check("...which is what the server says it is",
                abs(told[0] - _bar(p, mine, UV.Hunger)) <= SLACK,
                f"server {told[0]:.2f}, here {_bar(p, mine, UV.Hunger):.2f}")
        yield from _await(lambda: p.posted("server", "thirsty") is not None, 30.0)
        yield from _await(lambda: _tags(p, mine) > 0, 8.0)
        p.check(f"client 1's own ability system is sent {DEHYDRATED_TAG}, which its HUD "
                "names, and its Thirst is 0",
                _tags(p, mine) == 1 and _bar(p, mine, UV.Thirst) == 0.0,
                f"tag count {_tags(p, mine)}, thirst {_bar(p, mine, UV.Thirst):.2f}")
        p.post("done")
        return

    yield from _await(lambda: p.posted("server", "thirsty") is not None, 90.0)
    yield 0.5
    hunger = _bar(p, mine, UV.Hunger)
    p.check("client 2's own Hunger did not rise when client 1 ate",
            _near(hunger, HUNGRY), f"{hunger:.2f}")
    p.check("...and it has no debuff of client 1's", _tags(p, mine) == 0, str(_tags(p, mine)))
    others = [a for a in unreal.GameplayStatics.get_all_actors_of_class(
        p.world(), mine.get_class()) if a != mine]
    bars = [(_bar(p, a, UV.Hunger), _bar(p, a, UV.Thirst), _bar(p, a, UV.Temperature))
            for a in others]
    full = (SURVIVAL.max_hunger, SURVIVAL.max_thirst, SURVIVAL.start_temperature)
    p.check("client 2 is told none of client 1's bars (they are the owner's): its copy "
            "of that character still has the class defaults",
            len(others) == p.clients - 1 and all(b == full for b in bars), f"{bars}")
    p.post("done")


# ─── single player ───────────────────────────────────────────────────────────

def probe(p):
    mine = p.pawn()
    wc = _wc(p, mine)
    yield from _await(lambda: p.get(wc, WV.Held) is not None)
    p.set(_stats(p, mine), str(UV.Hunger), HUNGRY)
    held = yield from _give_mushroom(p, mine, wc)
    p.check("standalone: a mushroom is in the bag", held == 1, f"{held}")
    if not held:
        return
    before = yield from _eat(p, mine, wc)
    after = _bar(p, mine, UV.Hunger)
    p.check(f"standalone: the fire key eats it ({SERVER_CONSUME}, a plain call): Hunger "
            f"rises by {MUSHROOM_HUNGER:.0f} and the mushroom is gone",
            _near(after, before + MUSHROOM_HUNGER) and not _mushrooms(p, wc),
            f"{before:.2f} -> {after:.2f}, {len(_mushrooms(p, wc))} left")
