"""Death in each mode (M16): on a server a dead player's gear goes onto a
lootable corpse and the player is given a new body; in single player nothing
of that happens and the death is the end of the game, as before.

    python3 Scripts/dev/uepy.py --net --clients 2 --probe-timeout 240 --probe Scripts/probes/probe_net_death.py
    python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_net_death.py    # single player

combat/weapon_component/shed.py (the gear), combat/player_respawn.py (the new
body), graphics_menu/menu_screens.py (the death screen). The server kills
client 1, step by step, and the three machines compare:

    "killed"     client 1 taken to 0 HP with a garment worn. Every machine's
                 copy of the body is a ragdoll and its weapon component is
                 behind the dead gate, with nothing left in its slots
    "loot"       the server's record of what the body carries: every item the
                 player held, and the garment. Client 2 reads the same list
    "moved"      client 2 stood beside the body: its loot window finds it and
                 shows it, and a take puts an item in client 2's bag
    "respawned"  PLAYER_RESPAWN_SECONDS after the death client 1 has a new,
                 living character at a PlayerStart with the starting
                 inventory, on every machine; the body still lies there

Client 1's own screen: the death menu with the server's hint, a click on it
restarting nothing, no pause; then the HUD again.

Single player: the body keeps what it held, carries no loot, the world pauses
and no new body comes. (The profile's delete is probe_profile's.)

Join order varies, so a player is known by its player id, never by index.
"""

import time

import unreal

from combat import health_vars as HV
from combat.damage import TAKE_HIT
from combat.death import CORPSE_SECONDS, PLAYER_RESPAWN_SECONDS
from combat.game_state import PLAYER_DEAD_VAR
from combat.paths import (
    HEALTH_CLASS_PATH, ITEM_CLASS_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH)
from combat.wear_tuning import CLOTHING_SLOT_VAR, NOT_CLOTHING, WORN_VAR
from combat.weapon_component import vars as WV
from combat.weapon_component.dead import OWNER_DEAD_VAR
from graphics_menu import umg_consts as C
from graphics_menu.cursor_consts import CURSOR_ACCEPT_VAR
from graphics_menu.loot_consts import (
    LOOT_OPEN_VAR, LOOT_PANEL, LOOT_TAKE_VAR, LOOT_TARGET_VAR)
from loot.consts import LOOT_NAMES_VAR, LOOT_VAR

RUNS_ON = ("server", "client", "standalone")

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = [(WEAPON_COMP_BP_PATH, WORN_VAR), (HUD_BP_PATH, LOOT_OPEN_VAR),
            (HUD_BP_PATH, LOOT_TAKE_VAR), (HUD_BP_PATH, CURSOR_ACCEPT_VAR)]

WAIT = 40.0             # wall seconds any one step may take
VICTIM, LOOTER = "client 1", "client 2"
FATAL = 1000.0
AHEAD = unreal.Vector(1.0, 0.0, 0.0)
BESIDE_CM = 90.0        # where the looter is stood: beside the body
START_NEAR_CM = 300.0   # a respawn is "at" a PlayerStart within this
CLOCK_SLACK = 1.5       # game seconds either side of the respawn's wait
SHOWN = unreal.SlateVisibility.HIT_TEST_INVISIBLE


def _await(ready, seconds=WAIT):
    until = time.time() + seconds
    yield lambda: ready() or time.time() > until


def _now(p):
    return unreal.GameplayStatics.get_time_seconds(p.world())


def _health(p, actor):
    return p.component(actor, HEALTH_CLASS_PATH)


def _wc(p, actor):
    return p.component(actor, WEAPON_COMP_CLASS_PATH)


def _alive(obj):
    return obj is not None and unreal.SystemLibrary.is_valid(obj)


def _carried(p, actor):
    """The class names of what a character's Inventory holds, sorted."""
    return sorted(i.get_class().get_name() for i in p.get(_wc(p, actor), WV.Inventory)
                  if _alive(i))


def _loot(p, body):
    return sorted(c.get_name() for c in p.get(_health(p, body), LOOT_VAR) if c)


def _limp(body):
    """The body is a ragdoll: its mesh simulates and its capsule is off."""
    mesh = body.get_component_by_class(unreal.SkeletalMeshComponent)
    capsule = body.get_component_by_class(unreal.CapsuleComponent)
    return (mesh.is_any_simulating_physics()
            and capsule.get_collision_enabled() == unreal.CollisionEnabled.NO_COLLISION)


def _shed(p, body):
    """The body's weapon component is behind the dead gate, holding nothing."""
    wc = _wc(p, body)
    return (p.get(wc, OWNER_DEAD_VAR) and len(p.get(wc, WV.Inventory)) == 0
            and p.get(wc, WV.Held) is None
            and not any(_alive(i) for i in p.get(wc, WORN_VAR)))


def _characters_of(p, player_id):
    """Every character in this world that is, or was, that player's: the
    living one has the PlayerState, a body left behind has none, so a body is
    told by the caller, who kept it."""
    out = []
    for c in unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.Character):
        state = c.player_state
        if state and state.player_id == player_id:
            out.append(c)
    return out


def _draw(hud):
    """One HUD frame by hand: a -nullrhi process draws none of its own."""
    if "-nullrhi" in unreal.SystemLibrary.get_command_line().lower():
        hud.call_method("ReceiveDrawHUD", (1920, 1080))


def _death_screen(p, hud):
    death = p.get(hud, "UiDeath")
    up = death.get_visibility() == SHOWN
    hint = str(death.get_editor_property(C.DEATH_HINT_LINE).get_text())
    return up, hint


# ─── The server ──────────────────────────────────────────────────────────────

def probe_server(p):
    world = p.world()
    yield from _await(lambda: len(p.players()) >= p.clients
                      and all(p.posted(n, "id") is not None for n in (VICTIM, LOOTER)))
    by_id = {c.player_state.player_id: c for c in p.players() if c.player_state}
    victim, looter = by_id.get(p.posted(VICTIM, "id")), by_id.get(p.posted(LOOTER, "id"))
    p.check("the server has both players' controllers, each with a character",
            bool(victim and looter and victim.get_controlled_pawn()
                 and looter.get_controlled_pawn()), str(sorted(by_id)))
    if not (victim and looter):
        return
    body, other = victim.get_controlled_pawn(), looter.get_controlled_pawn()
    yield from _await(lambda: len(_carried(p, body)) > 0 and len(_carried(p, other)) > 0)
    issued = _carried(p, body)
    p.check("the server's copy of client 1's character holds the starting inventory",
            len(issued) > 0, str(issued))

    # Something worn: a garment lying in the level, put in the server's Worn.
    items = unreal.GameplayStatics.get_all_actors_of_class(world, p.load_class(ITEM_CLASS_PATH))
    garments = [i for i in items if p.get(i, CLOTHING_SLOT_VAR) != NOT_CLOTHING]
    worn = garments[0] if garments else None
    p.check("a garment lies in the level for client 1 to wear", worn is not None)
    wanted = list(issued)
    if worn:
        p.set(_wc(p, body), WORN_VAR, [worn])
        wanted = sorted(issued + [worn.get_class().get_name()])

    # --- the death ------------------------------------------------------------
    died = _now(p)
    _health(p, body).call_method(TAKE_HIT, (FATAL, AHEAD, None, None))
    p.post("killed")
    yield from _await(lambda: p.get(_health(p, body), HV.Dead) and _shed(p, body))
    p.check("the server's copy of the body is a ragdoll", _limp(body))
    p.check("...behind the dead gate, with nothing left in its slots, hand or worn "
            "slots, and the actors destroyed", _shed(p, body) and not _alive(worn),
            f"{_carried(p, body)}, garment alive {_alive(worn)}")
    carried = _loot(p, body)
    names = [str(n) for n in p.get(_health(p, body), LOOT_NAMES_VAR)]
    p.check("the body carries everything the player held and wore, one row each",
            carried == wanted and len(names) == len(wanted), f"{carried} / wanted {wanted}")
    p.post("loot", carried)

    yield from _await(lambda: p.get(victim.player_state, PLAYER_DEAD_VAR))
    p.check("client 1's PlayerState says dead, the server's world runs on and the "
            "other player lives",
            p.get(victim.player_state, PLAYER_DEAD_VAR)
            and not unreal.GameplayStatics.is_game_paused(world)
            and not p.get(looter.player_state, PLAYER_DEAD_VAR)
            and p.get(_health(p, other), HV.Health) > 0.0)

    # --- the looter, stood where its own copy of the ragdoll lies --------------
    yield from _await(lambda: p.posted(LOOTER, "rest") is not None)
    rest = p.posted(LOOTER, "rest")
    if rest:
        other.set_actor_location(unreal.Vector(rest[0] - BESIDE_CM, rest[1], rest[2] + 100.0),
                                 False, True)
    p.post("moved")

    # --- the respawn ------------------------------------------------------------
    yield from _await(lambda: victim.get_controlled_pawn() not in (None, body))
    waited = _now(p) - died
    fresh = victim.get_controlled_pawn()
    p.check("client 1's controller has a new character, and the body is still there",
            fresh is not None and fresh != body and _alive(body),
            f"{fresh.get_name() if fresh else None}, body {body.get_name()}")
    if not fresh or fresh == body:
        p.post("respawned", False)
        return
    p.check(f"...{PLAYER_RESPAWN_SECONDS:.0f} s after the death",
            abs(waited - PLAYER_RESPAWN_SECONDS) <= CLOCK_SLACK, f"{waited:.2f} game s")
    starts = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.PlayerStart)
    at = fresh.get_actor_location()
    near = min((((s.get_actor_location().x - at.x) ** 2
                 + (s.get_actor_location().y - at.y) ** 2) ** 0.5 for s in starts),
               default=1e9)
    p.check("...at one of the level's PlayerStarts", near <= START_NEAR_CM,
            f"{near:.0f} cm from the nearest of {len(starts)}")
    yield from _await(lambda: _carried(p, fresh) == issued)
    hp = _health(p, fresh)
    p.check("...alive at full health, with the starting inventory again",
            p.get(hp, HV.Health) == p.get(hp, HV.MaxHealth) and not p.get(hp, HV.Dead)
            and _carried(p, fresh) == issued, f"{p.get(hp, HV.Health)} HP, {_carried(p, fresh)}")
    p.check("...and client 1's PlayerState no longer says dead",
            not p.get(victim.player_state, PLAYER_DEAD_VAR))
    p.check(f"the body keeps its loot and has {CORPSE_SECONDS:.0f} s left to lie there",
            _loot(p, body) == wanted and 0.0 < body.get_life_span() <= CORPSE_SECONDS,
            f"{_loot(p, body)}, {body.get_life_span():.1f} s")
    p.post("respawned")
    yield from _await(lambda: all(p.posted(n, "done") is not None for n in (VICTIM, LOOTER)))
    p.check("both clients finished",
            all(p.posted(n, "done") is not None for n in (VICTIM, LOOTER)))


# ─── The clients ─────────────────────────────────────────────────────────────

def probe_client(p):
    yield from _await(lambda: p.hud() is not None and p.get(p.hud(), "UiHud") is not None
                      and p.player_state() is not None and p.pawn() is not None)
    yield from _await(lambda: p.get(p.hud(), C.GAME_STARTED_VAR))
    p.post("id", p.player_state().player_id)
    if p.where == VICTIM:
        yield from _victim(p)
    elif p.where == LOOTER:
        yield from _looter(p)
    p.post("done")


def _victim(p):
    hud, mine, world = p.hud(), p.player_state(), p.world()
    body = p.pawn()
    yield from _await(lambda: len(_carried(p, body)) > 0)
    issued = _carried(p, body)
    level = unreal.GameplayStatics.get_current_level_name(world)

    yield from _await(lambda: p.posted("server", "killed") is not None
                      and p.get(_health(p, body), HV.Dead) and _shed(p, body))
    p.check("client 1's own body is a ragdoll, behind the dead gate, and holds nothing",
            _limp(body) and _shed(p, body), f"{_carried(p, body)}")

    yield from _await(lambda: p.get(mine, PLAYER_DEAD_VAR))
    _draw(hud)
    yield 0.3
    up, hint = _death_screen(p, hud)
    p.check("client 1's HUD draws the death menu, and its hint says a respawn is coming",
            p.get(mine, PLAYER_DEAD_VAR) and up and hint == C.DEATH_HINT_SERVER,
            f"PlayerDead {p.get(mine, PLAYER_DEAD_VAR)}, up {up}, '{hint}'")
    if p.pawn() == body:
        # A click on the hint line, which in single player restarts the level.
        p.set(hud, CURSOR_ACCEPT_VAR, True)
        _draw(hud)
        yield 0.5
        p.check("...a click on it restarts nothing: the same level, still a client, "
                "not paused, and the click is not left raised",
                unreal.GameplayStatics.get_current_level_name(world) == level
                and not unreal.SystemLibrary.is_standalone(world)
                and not unreal.GameplayStatics.is_game_paused(world)
                and not p.get(hud, CURSOR_ACCEPT_VAR),
                f"accept {p.get(hud, CURSOR_ACCEPT_VAR)}")

    yield from _await(lambda: p.pawn() not in (None, body)
                      and not p.get(mine, PLAYER_DEAD_VAR))
    fresh = p.pawn()
    p.check("client 1 has a new character of its own, and the body is still there",
            fresh is not None and fresh != body and _alive(body),
            f"{fresh.get_name() if fresh else None}")
    if not fresh or fresh == body:
        return
    yield from _await(lambda: _carried(p, fresh) == issued
                      and p.get(_wc(p, fresh), WV.LocalReady))
    hp, wc = _health(p, fresh), _wc(p, fresh)
    p.check("...alive at full health with the starting inventory, and its keys are "
            "this machine's (LocalReady, not OwnerDead)",
            p.get(hp, HV.Health) == p.get(hp, HV.MaxHealth) and _carried(p, fresh) == issued
            and p.get(wc, WV.LocalReady) and not p.get(wc, OWNER_DEAD_VAR)
            and fresh.is_locally_controlled(),
            f"{p.get(hp, HV.Health)} HP, {_carried(p, fresh)}")
    _draw(hud)
    yield 0.3
    up, _hint = _death_screen(p, hud)
    shown = p.get(hud, "UiHud").get_editor_property(C.HUD_BODY).get_visibility()
    p.check("...and its HUD is back: the death menu down, the HUD's body up",
            not up and shown == SHOWN and not p.get(mine, PLAYER_DEAD_VAR),
            f"menu up {up}, body {shown}")


def _looter(p):
    hud, mine = p.hud(), p.player_state()
    me = p.pawn()
    their_id = None
    yield from _await(lambda: p.posted(VICTIM, "id") is not None
                      and len(_characters_of(p, p.posted(VICTIM, "id"))) == 1
                      and len(_carried(p, me)) > 0)
    their_id = p.posted(VICTIM, "id")
    found = _characters_of(p, their_id)
    p.check("client 2 sees client 1's character", len(found) == 1, str(len(found)))
    if not found:
        return
    body = found[0]
    held = _carried(p, me)

    yield from _await(lambda: p.posted("server", "loot") is not None
                      and p.get(_health(p, body), HV.Dead) and _shed(p, body)
                      and _loot(p, body) == p.posted("server", "loot"))
    p.check("client 2's copy of the body is a ragdoll too, holding nothing",
            _limp(body) and _shed(p, body))
    p.check("client 2 reads the loot the server put on the body",
            _loot(p, body) == p.posted("server", "loot") and len(_loot(p, body)) > 0,
            f"{_loot(p, body)}")
    p.check("another player's death is not client 2's: alive, its inventory its own",
            not p.get(mine, PLAYER_DEAD_VAR) and p.get(_health(p, me), HV.Health) > 0.0
            and _carried(p, me) == held)

    # --- the loot window, on a player's body -----------------------------------
    yield 1.0           # the ragdoll comes to rest
    at = body.get_component_by_class(unreal.SkeletalMeshComponent).get_world_location()
    p.post("rest", [at.x, at.y, at.z])
    yield from _await(lambda: p.posted("server", "moved") is not None
                      and p.get(hud, LOOT_TARGET_VAR) == _health(p, body))
    p.check("stood beside it, client 2's loot window finds the dead player's body",
            p.get(hud, LOOT_TARGET_VAR) == _health(p, body),
            f"{p.get(hud, LOOT_TARGET_VAR)}")
    if p.get(hud, LOOT_TARGET_VAR) == _health(p, body):
        rows = len(_loot(p, body))
        p.set(hud, LOOT_OPEN_VAR, True)
        yield 0.3
        _draw(hud)
        panel = p.get(hud, "UiHud").get_editor_property(LOOT_PANEL)
        p.check("...and opens on it", panel.get_visibility() == SHOWN
                and p.get(hud, LOOT_OPEN_VAR), f"{panel.get_visibility()}")
        p.set(hud, LOOT_TAKE_VAR, True)
        yield from _await(lambda: len(_carried(p, me)) == len(held) + 1, 10.0)
        p.check("...a take puts one of its items in client 2's bag (its own copy's: "
                "the take is not the server's until M23)",
                len(_carried(p, me)) == len(held) + 1 and len(_loot(p, body)) == rows - 1,
                f"{_carried(p, me)}")
        p.set(hud, LOOT_OPEN_VAR, False)
        yield 0.3

    yield from _await(lambda: p.posted("server", "respawned") is not None
                      and any(c != body for c in _characters_of(p, their_id)))
    fresh = [c for c in _characters_of(p, their_id) if c != body]
    p.check("client 2 sees client 1's new, living character, and the body still lying there",
            len(fresh) == 1 and not p.get(_health(p, fresh[0]), HV.Dead)
            and _alive(body) and p.get(_health(p, body), HV.Dead),
            f"{[c.get_name() for c in fresh]}")


# ─── Single player ───────────────────────────────────────────────────────────

def probe_standalone(p):
    world = p.world()
    body, mine = p.pawn(), p.player_state()
    yield from _await(lambda: len(_carried(p, body)) > 0)
    issued = _carried(p, body)
    _health(p, body).call_method(TAKE_HIT, (FATAL, AHEAD, None, None))
    yield from _await(lambda: unreal.GameplayStatics.is_game_paused(world), 60.0)
    p.check("single player: the death sets PlayerDead and pauses the world",
            p.get(mine, PLAYER_DEAD_VAR) and unreal.GameplayStatics.is_game_paused(world))
    wc = _wc(p, body)
    p.check("...the body is a ragdoll behind the dead gate, and keeps what it held: "
            "nothing is shed and it carries no loot",
            _limp(body) and p.get(wc, OWNER_DEAD_VAR) and _carried(p, body) == issued
            and len(_loot(p, body)) == 0, f"{_carried(p, body)}, loot {_loot(p, body)}")
    hud = p.hud()
    _draw(hud)
    up, hint = _death_screen(p, hud)
    p.check("...the death menu offers the restart, as before",
            up and hint == C.DEATH_HINT, f"up {up}, '{hint}'")
    yield from _await(lambda: False, 1.0)       # wall time: a paused world's clock stands
    p.check("...and no new body comes: the same pawn, no lifespan on it",
            p.pawn() == body and body.get_life_span() == 0.0,
            f"{p.pawn().get_name()}, {body.get_life_span()}")
