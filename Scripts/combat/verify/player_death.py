"""verify.player_death -- a player's death on a server: the gear shed onto
the body (weapon_component/shed.py) and the respawn (player_respawn.py),
both out of standalone's way, whose death is the end of the game.
"""

from combat import health_vars as HV
from combat.death import PLAYER_RESPAWN_SECONDS, PLAYER_RESPAWN_WAIT
from combat.paths import HEALTH_BP_PATH, WEAPON_COMP_BP_PATH
from combat.player_respawn import PLAYER_START_CLASS_PATH
from combat.slot_tuning import SLOT_ITEMS_VAR
from combat.verify.common import BEL, PIN, by_pins, cdo, check, graph, load, pin_value
from combat.wear_tuning import WORN_VAR
from combat.weapon_component import vars as WV
from combat.weapon_component.dead import OWNER_DEAD_VAR
from loot.consts import BODY_ARRAYS
from uebp import net


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _feeders(n, pin):
    p = BEL.find_input_pin(n, pin)
    return [PIN.get_owning_node(q) for q in (p.list_connected_pins() if p else [])]


LIMIT = 3000


def _upstream(n, limit=LIMIT):
    """Every node whose exec reaches ``n``, walking execute pins backwards."""
    seen, todo = set(), [n]
    while todo and len(seen) < limit:
        cur = todo.pop()
        for pin in ("execute", "Exec"):
            for f in _feeders(cur, pin):
                if f not in seen:
                    seen.add(f)
                    todo.append(f)
    return seen


def _standalone_gates(nodes):
    """The Branches whose condition is IsStandalone."""
    return [n for n in nodes
            if any("Standalone" in _title(f) for f in _feeders(n, "Condition"))]


def _off_false_arm(node, gate):
    """``node``'s exec comes down ``gate``'s false arm and never its true one."""
    arms, seen, todo = set(), set(), [node]
    while todo and len(seen) < LIMIT:
        cur = todo.pop()
        for name in ("execute", "Exec"):
            pin = BEL.find_input_pin(cur, name)
            for q in (pin.list_connected_pins() if pin else []):
                src = PIN.get_owning_node(q)
                if src == gate:
                    arms.add(str(PIN.get_pin_name(q)))
                elif src not in seen:
                    seen.add(src)
                    todo.append(src)
    return arms == {"else"}


def check_gear_shed():
    bp = load(WEAPON_COMP_BP_PATH)
    nodes = graph(bp).list_all_nodes()
    adds = [n for n in by_pins(nodes, "TargetArray", "NewItem")
            if any(_title(f) in [f"Get {v}" for v in BODY_ARRAYS]
                   for f in _feeders(n, "TargetArray"))]
    check("a dead player's gear goes onto the body: one Add to each of its Loot arrays "
          "for the bag's items, one for the worn ones",
          sorted(_title(f) for n in adds for f in _feeders(n, "TargetArray"))
          == sorted(f"Get {v}" for v in BODY_ARRAYS for _ in range(2)), str(len(adds)))
    first = adds[0] if adds else None
    before = _upstream(first) if first else set()
    alone = [n for n in _standalone_gates(nodes) if n in before]
    check("...never in standalone: behind one Branch on IsStandalone, off its false arm",
          len(alone) == 1 and _off_false_arm(first, alone[0]), str(len(alone)))
    once = [n for n in before
            if any(_title(f) == f"Get {OWNER_DEAD_VAR}" for f in _feeders(n, "Condition"))]
    check(f"...once per death: behind a Branch on {OWNER_DEAD_VAR}, read before it is set",
          len(once) == 1, str(len(once)))
    server = [n for n in nodes
              if any("HasAuthority" in _title(f).replace(" ", "")
                     for f in _feeders(n, "Condition"))]
    check("...the record is the server's: each Add behind HasAuthority",
          bool(adds) and all(any(s in _upstream(a) for s in server) for a in adds),
          str(len(server)))
    emptied = sorted(_title(f) for n in by_pins(nodes, "TargetArray")
                     if "Clear" in _title(n) and alone and alone[0] in _upstream(n)
                     for f in _feeders(n, "TargetArray"))
    check("...and every copy empties what it held: Inventory, Worn and SlotItems cleared",
          emptied == sorted(f"Get {v}" for v in (WV.Inventory, WORN_VAR, SLOT_ITEMS_VAR)),
          str(emptied))


def check_player_respawn():
    bp = load(HEALTH_BP_PATH)
    nodes = graph(bp).list_all_nodes()
    check(f"a dead player respawns {PLAYER_RESPAWN_SECONDS:.0f} s after the death: "
          f"{HV.PlayerRespawnWait} is the rest of it after the settle",
          abs(cdo(bp).get_editor_property(HV.PlayerRespawnWait) - PLAYER_RESPAWN_WAIT) < 1e-4,
          str(cdo(bp).get_editor_property(HV.PlayerRespawnWait)))
    restarts = by_pins(nodes, "NewPlayer", "StartSpot")
    check("the respawn is the GameMode's RestartPlayerAtPlayerStart, once",
          len(restarts) == 1, str(len(restarts)))
    restart = restarts[0] if restarts else None
    before = _upstream(restart) if restart else set()
    starts = [n for n in by_pins(before, "ActorClass")
              if "PlayerStart" in pin_value(n, "ActorClass")]
    drawn = [r for g in (_feeders(restart, "StartSpot") if restart else ())
             for i in _feeders(g, "Index") if "Random" in _title(i) for r in [i]]
    check("...at a random one of the level's PlayerStarts: GetAllActorsOfClass, and one "
          "random index into it", len(starts) == 1 and len(drawn) == 1
          and PLAYER_START_CLASS_PATH in pin_value(starts[0], "ActorClass"),
          f"{len(starts)} {len(drawn)}")
    freed = [n for n in before if "unpossess" in _title(n).replace(" ", "").lower()]
    kept = [f for n in freed for f in _feeders(n, "self")]
    check(f"...after the controller, kept in {HV.RespawnFor}, lets go of the body",
          len(freed) == 1 and [_title(k) for k in kept] == [f"Get {HV.RespawnFor}"]
          and all(_title(f) == f"Get {HV.RespawnFor}" for f in _feeders(restart, "NewPlayer")),
          str([_title(k) for k in kept]))
    waits = [n for n in before
             if any(_title(f) == f"Get {HV.PlayerRespawnWait}" for f in _feeders(n, "Duration"))]
    check("...after the wait, on the server (behind the GameMode's switch)",
          len(waits) == 1 and any("Authority" in _title(n) for n in _upstream(waits[0])),
          str(len(waits)))
    alone = [n for n in _standalone_gates(nodes) if n in before]
    check("...and never in standalone: off the false arm of the death pause's Branch",
          len(alone) == 1 and _off_false_arm(restart, alone[0]), str(len(alone)))
    for var in BODY_ARRAYS:
        got = net.variable_replication(bp, var)
        check(f"{var} is Replicated: every machine's loot window reads the server's body",
              got == (net.REPLICATED, "None", "COND_NONE"), str(got))


def run():
    check_gear_shed()
    check_player_respawn()
