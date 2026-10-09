"""Input belongs to the locally controlled pawn (task M10).

A weapon component ticks on every machine that has its character. Only the
machine whose player controls that character may read keys for it
(combat/weapon_component/local.py): before, a client polled its own
controller for every character it could see, so one press of fire fired them
all, each on that client's copy.

    client 1   forces the fire key on BOTH characters' components. Its own
               fires (a round is spent); the other player's does nothing.
    client 2   watches its own character through client 1's press: no shot.
    everyone   LocalInput and LocalPC say whose keys each copy reads: a
               client's own character alone, and none on the server, which
               also has no HUD and no widgets.

Single player (`--game`) runs the standalone arm: the one character is local.
"""

SYSTEMS = ('net',)

import time

import unreal

from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.weapon_component.tick import FIRE_FORCED_VAR

WRITABLE = [(WEAPON_COMP_BP_PATH, FIRE_FORCED_VAR)]
WAIT_S = 20.0


def _await(cond, seconds=WAIT_S):
    end = time.time() + seconds
    return lambda: cond() or time.time() > end


def _characters(p):
    """(mine, others): every character of my pawn's class in this world."""
    mine = p.pawn()
    cls = mine.get_class() if mine else None
    world = mine.get_world() if mine else None
    found = unreal.GameplayStatics.get_all_actors_of_class(world, cls) if cls else []
    return mine, [a for a in found if a != mine]


def _comp(p, actor):
    return p.component(actor, WEAPON_COMP_CLASS_PATH)


def _loaded(p, comp):
    held = p.get(comp, "Held")
    return p.get(held, "Loaded") if held else None


def _local(p, comp):
    return bool(p.get(comp, "LocalInput")), p.get(comp, "LocalPC") is not None


def probe_server(p):
    yield 1.0
    world = p.players()[0].get_world()
    pawns = [pc.get_controlled_pawn() for pc in p.players()]
    comps = [_comp(p, a) for a in pawns if a]
    states = [_local(p, c) for c in comps]
    p.check("the server reads no player's keys: LocalInput is false and "
            "LocalPC none on every character", len(comps) == p.clients
            and all(s == (False, False) for s in states), f"{states}")
    huds = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.HUD)
    widgets = unreal.WidgetLibrary.get_all_widgets_of_class(
        world, unreal.UserWidget, False)
    p.check("a dedicated server has no HUD and no widgets",
            not huds and not widgets, f"{len(huds)} HUDs, {len(widgets)} widgets")
    before = [_loaded(p, c) for c in comps]
    p.post("ready")
    yield _await(lambda: p.posted("client 1", "fired"))
    yield 0.5
    after = [_loaded(p, c) for c in comps]
    spent = sorted(b - a for b, a in zip(before, after))
    p.check("client 1's press fired one character on the server, its own (the "
            "shot is a server request: M19), and not the other player's",
            spent == [0] * (len(spent) - 1) + [1], f"{before} -> {after}")


def probe_client(p):
    yield _await(lambda: len(_characters(p)[1]) >= p.clients - 1)
    mine, others = _characters(p)
    own = _comp(p, mine)
    yield 0.5
    p.check("this client reads its own character's keys: LocalInput, and "
            "LocalPC its own controller", _local(p, own) == (True, True)
            and p.get(own, "LocalPC") == mine.get_controller(),
            f"{_local(p, own)}")
    theirs = [_comp(p, a) for a in others]
    p.check("and no other player's: LocalInput false and LocalPC none on "
            "their characters here", len(theirs) == p.clients - 1
            and all(_local(p, c) == (False, False) for c in theirs),
            f"{[_local(p, c) for c in theirs]}")
    start = _loaded(p, own)
    if p.client != 1:
        p.post("watching", start)
        yield _await(lambda: p.posted("client 1", "fired"))
        yield 0.5
        p.check("client 1's press of fire did nothing to this client's "
                "character", _loaded(p, own) == start, f"{start} -> {_loaded(p, own)}")
        return
    yield _await(lambda: p.posted("server", "ready")
                 and all(p.posted(f"client {i}", "watching")
                         for i in range(2, p.clients + 1)))
    their_start = [_loaded(p, c) for c in theirs]
    never = unreal.PropertyAccessChangeNotifyMode.NEVER
    for c in [own] + theirs:
        c.set_editor_property(FIRE_FORCED_VAR, True, never)
    yield _await(lambda: _loaded(p, own) != start, 5.0)
    yield 0.3
    for c in [own] + theirs:
        c.set_editor_property(FIRE_FORCED_VAR, False, never)
    p.check("the fire key fires this client's own character (a round is "
            "spent)", start is not None and _loaded(p, own) < start,
            f"{start} -> {_loaded(p, own)}")
    their_end = [_loaded(p, c) for c in theirs]
    p.check("and not the other player's character, whose trigger this "
            "client pressed just the same", their_end == their_start,
            f"{their_start} -> {their_end}")
    p.post("fired")


def probe(p):
    """Single player: the one character is the local player's."""
    yield 0.3
    own = _comp(p, p.pawn())
    p.check("standalone: the player's character reads the keys (LocalInput, "
            "LocalPC its controller)", _local(p, own) == (True, True)
            and p.get(own, "LocalPC") == p.pawn().get_controller(), f"{_local(p, own)}")
    start = _loaded(p, own)
    p.set(own, FIRE_FORCED_VAR, True)
    yield _await(lambda: _loaded(p, own) != start, 5.0)
    p.set(own, FIRE_FORCED_VAR, False)
    p.check("and the fire key fires", start is not None and _loaded(p, own) < start,
            f"{start} -> {_loaded(p, own)}")
