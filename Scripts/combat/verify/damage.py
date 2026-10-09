"""verify.damage -- health is the server's (combat/damage.py): the TakeHit
event every blow calls and what it writes, behind the authority switch; what
of the component replicates and what does not; OnRep_Health, a client's side
of a change; the Tick's server-only parts (the world-floor net, the drain,
Dead, the replacement) and its own death latch; the kill credited to the
blow's instigator; and that no blow writes a target's health itself.

That a client's bar falls is two processes' to prove: probes/probe_net_health.py.
"""

from combat import health_vars as HV
from combat.damage import REPLICATED, TAKE_HIT, TAKE_HIT_PARAMS
from combat.game_state import DAMAGED_BY_PLAYER_VAR, KILL_COUNT_VAR, LAST_DAMAGE_VAR
from combat.hit_reaction import LAST_HIT_FROM_VAR, PREV_HEALTH_VAR
from combat.verify.common import (
    BEL, HEALTH_SETS, PIN, check, graph, in_pins, take_hits, titled)
from combat.verify.fixtures import _wg_all, char, drain_writes, health_bp, hg, npc
from combat.verify.sights import _feeds, _title
from net.state_consts import PLAYER_KILL_COUNT_VAR
from uebp import net
from uebp.graph import BGE

# Stamps only TakeHit may write, wherever the blow is struck from.
STAMPS = (LAST_DAMAGE_VAR, DAMAGED_BY_PLAYER_VAR, LAST_HIT_FROM_VAR)


def _ran_by(node):
    pin = BEL.find_input_pin(node, "execute")
    return [PIN.get_owning_node(q) for q in PIN.list_connected_pins(pin)] if pin else []


def _upstream(node):
    """Every node an exec path can come through to reach ``node``."""
    seen, todo = {}, _ran_by(node)
    while todo:
        n = todo.pop()
        if n.get_path_name() not in seen:
            seen[n.get_path_name()] = n
            todo += _ran_by(n)
    return list(seen.values())


def _arm_into(node):
    """The names of the exec output pins wired straight into ``node``."""
    pin = BEL.find_input_pin(node, "execute")
    return sorted(str(PIN.get_pin_name(q)) for q in PIN.list_connected_pins(pin))


def _switches(nodes):
    return [n for n in nodes if "Switch Has Authority" in _title(n)]


def _behind_authority(node):
    """``node`` runs only down the Authority arm of a switch: no exec path
    reaches it that does not come out of one."""
    todo, seen = [node], set()
    while todo:
        n = todo.pop()
        if n.get_path_name() in seen:
            continue
        seen.add(n.get_path_name())
        pin = BEL.find_input_pin(n, "execute")
        links = PIN.list_connected_pins(pin) if pin else []
        if not links:
            return False                    # an event: reached with no switch
        for q in links:
            src = PIN.get_owning_node(q)
            if "Switch Has Authority" in _title(src):
                if str(PIN.get_pin_name(q)) != "Authority":
                    return False
            else:
                todo.append(src)
    return True


def _sets(nodes, var):
    return [n for n in nodes if _title(n) in (f"Set {var}", f"Set with Notify {var}")]


def check_take_hit():
    ed = graph(health_bp)
    event = ed.find_event_node(TAKE_HIT)
    check(f"BP_HealthComponent has a {TAKE_HIT} event", bool(event))
    if not event:
        return
    outs = {str(PIN.get_pin_name(p)) for p in BEL.list_output_pins(event)}
    check("...told how much, which way it came, who struck it and with what",
          {name for name, _ in TAKE_HIT_PARAMS} <= outs, str(sorted(outs)))
    check("...a plain event, not an RPC: only the server's call does anything, and "
          "nothing a client sends reaches it",
          net.compiled_rpc(health_bp, TAKE_HIT) == (net.LOCAL, False),
          str(net.compiled_rpc(health_bp, TAKE_HIT)))
    first = [PIN.get_owning_node(q) for q in
             PIN.list_connected_pins(BEL.find_then_pin(event))]
    check("...whose first step is Switch Has Authority",
          len(first) == 1 and "Switch Has Authority" in _title(first[0]),
          str([_title(n) for n in first]))
    mine = [n for n in hg if event in _upstream(n)]
    writes = [n for n in mine if _title(n) in HEALTH_SETS]
    fed = {_title(f) for w in writes for f in _feeds(BEL.find_input_pin(w, "Health"))}
    check("it takes Amount off Health, floored at zero, once",
          len(writes) == 1 and "Get Health" in fed and any("Clamp" in t for t in fed)
          and TAKE_HIT in {_title(f).replace(" ", "") for f in
                           _feeds(BEL.find_input_pin(writes[0], "Health"))},
          f"{len(writes)} write(s), fed by {sorted(fed)}")
    for var, source in ((LAST_HIT_FROM_VAR, "From"), (HV.LastInstigator, "InstigatedBy"),
                        (HV.LastCause, "Cause")):
        sets = _sets(mine, var)
        links = [str(PIN.get_pin_name(q)) for s in sets
                 for q in PIN.list_connected_pins(BEL.find_input_pin(s, str(var)))]
        check(f"...and keeps {source} as {var}", len(sets) == 1 and links == [source],
              f"{len(sets)} write(s), off {links}")
    stamps = _sets(mine, LAST_DAMAGE_VAR)
    check(f"...and stamps {LAST_DAMAGE_VAR} with the game time",
          len(stamps) == 1 and any("Time" in _title(f) for f in
                                   _feeds(BEL.find_input_pin(stamps[0], LAST_DAMAGE_VAR))))
    blames = _sets(mine, DAMAGED_BY_PLAYER_VAR)
    check(f"{DAMAGED_BY_PLAYER_VAR} is set only where the instigator is a "
          "PlayerController (a wanderer's blow blames no player)",
          len(blames) == 1
          and ["CastToPlayerController"] == [_title(n).replace(" ", "") for n in
                                             _ran_by(blames[0])]
          and _arm_into(blames[0]) == ["then"], str([_title(n) for b in blames
                                                     for n in _ran_by(b)]))
    counts = _sets(mine, HV.HitCount)
    gate = [g for c in counts for g in _ran_by(c)]
    asked = {_title(f) for g in gate for f in _feeds(BEL.find_input_pin(g, "Condition"))}
    check(f"{HV.HitCount} rises once, before the write, and only where the blow takes "
          "health (Health and Amount above 0): what a client tells a blow by",
          len(counts) == 1 and len(gate) == 1 and _title(gate[0]) == "Branch"
          and "Get Health" in asked and writes and counts[0] in _ran_by(writes[0]),
          f"{len(counts)} write(s), behind {sorted(asked)}")
    check("every write of the event is behind its authority switch",
          all(_behind_authority(n) for n in mine if _title(n).startswith("Set")),
          str([_title(n) for n in mine if _title(n).startswith("Set")
               and not _behind_authority(n)]))


def check_replication():
    got = net.variable_replication(health_bp, HV.Health)
    check("Health is a RepNotify, to everyone", got == (net.REP_NOTIFY, "OnRep_Health",
                                                        "COND_NONE"), str(got))
    for var in REPLICATED:
        got = net.variable_replication(health_bp, var)
        check(f"{var} is Replicated", got == (net.REPLICATED, "None", "COND_NONE")
              and net.compiled_replication(health_bp, var)[0] == net.REPLICATED, str(got))
    check("BP_HealthComponent replicates by default", net.replicates(health_bp))
    check("...and on the player's character and on the wanderer, which replicate",
          net.replicates(char, "HealthComponent") and net.replicates(char)
          and net.replicates(npc, "HealthComponent") and net.replicates(npc))


def check_on_rep():
    ed = BGE.get_graph_editor_by_name(health_bp, "OnRep_Health")
    check("OnRep_Health has a graph", bool(ed))
    if not ed:
        return
    nodes = ed.list_all_nodes()
    sets = [n for n in nodes if _title(n).startswith("Set")]
    check("it runs on a client only: every write is down a switch's Remote arm (the "
          "machine that set Health has done all of it)",
          len(_switches(nodes)) == 1 and sets
          and all(_switches(nodes)[0] in _upstream(s) for s in sets)
          and "Remote" in _arm_into([n for n in nodes if _title(n) == "Branch"][0]),
          str([_title(s) for s in sets]))
    gate = [n for n in nodes if _title(n) == "Branch"]
    asked = {_title(f) for g in gate for f in _feeds(BEL.find_input_pin(g, "Condition"))}
    check(f"it tells a blow from a drain by {HV.HitCount} against {HV.SeenHits}",
          len(gate) == 1 and {f"Get {HV.HitCount}", f"Get {HV.SeenHits}"} <= asked,
          str(sorted(asked)))
    blow = {_title(s) for s in sets if _arm_into(s) == ["then"]
            or (_ran_by(s) and _title(_ran_by(s)[0]).startswith("Set"))}
    other = {_title(s) for s in sets if _arm_into(s) == ["else"]}
    check(f"a blow: {HV.SeenHits} catches up and {LAST_DAMAGE_VAR} is stamped with this "
          f"machine's clock; {PREV_HEALTH_VAR} is left for the Tick's flinch",
          blow == {f"Set {HV.SeenHits}", f"Set {LAST_DAMAGE_VAR}"}, str(sorted(blow)))
    check(f"anything else: {PREV_HEALTH_VAR} follows Health, so nothing flinches",
          other == {f"Set {PREV_HEALTH_VAR}"}, str(sorted(other)))
    check("it writes no Health", not [n for n in nodes if _title(n) in HEALTH_SETS])


def check_tick_authority():
    tick = [n for n in hg if _title(n) == "Event Tick"]
    first = ([PIN.get_owning_node(q) for q in PIN.list_connected_pins(BEL.find_then_pin(tick[0]))]
             if tick else [])
    check("the Tick's first step is Switch Has Authority",
          len(first) == 1 and "Switch Has Authority" in _title(first[0]),
          str([_title(n) for n in first]))
    own = [n for n in hg if _title(n) in HEALTH_SETS]
    check("every write of Health in the component is the server's: the world-floor "
          "net's, the drain's and TakeHit's are each behind an authority switch",
          len(own) == 3 and all(_behind_authority(n) for n in own),
          str([_behind_authority(n) for n in own]))
    check("...and the drain's own PrevHealth with it",
          all(_behind_authority(n) for n in drain_writes), str(len(drain_writes)))
    dead = _sets(hg, HV.Dead)
    check("Dead is set once, by the server (it replicates)",
          len(dead) == 1 and _arm_into(dead[0]) == ["Authority"],
          str([_arm_into(d) for d in dead]))
    played = _sets(hg, HV.DeathPlayed)
    gate = [g for p in played for g in _ran_by(p)]
    check(f"the death path runs once on each machine, on its own {HV.DeathPlayed}: "
          "Dead can arrive before a client's Tick has seen Health at 0",
          len(played) == 1 and len(gate) == 1 and _arm_into(played[0]) == ["else"]
          and {_title(f) for f in _feeds(BEL.find_input_pin(gate[0], "Condition"))}
          == {f"Get {HV.DeathPlayed}"} and dead and _ran_by(_ran_by(dead[0])[0]) == played,
          str([_title(g) for g in gate]))
    spawns = [n for n in hg if "SpawnActor" in _title(n).replace(" ", "")
              and "Class" in in_pins(n)
              and any(_title(f) == f"Get {HV.RespawnClass}"
                      for f in _feeds(BEL.find_input_pin(n, "Class")))]
    check("the replacement is spawned by the server alone",
          len(spawns) == 1 and _behind_authority(spawns[0]), f"{len(spawns)} spawn(s)")


def check_kill_credit():
    tallies = _sets(hg, KILL_COUNT_VAR)
    whose = {_title(f) for t in tallies for f in _feeds(BEL.find_input_pin(t, "self"))}
    check(f"a kill goes on the PlayerState of the last blow's instigator "
          f"({HV.LastInstigator}), and nobody's by index",
          len(tallies) == 1 and f"Get {HV.LastInstigator}" in whose
          and not [n for n in hg if "PlayerStateIndex" in in_pins(n)], str(sorted(whose)))
    valid = [n for n in _upstream(tallies[0]) if _title(n) == "Branch"
             and any("Valid" in _title(f) for f in _feeds(BEL.find_input_pin(n, "Condition")))
             ] if tallies else []
    check("...read behind an IsValid Branch of its own: a death nobody struck has none",
          bool(valid), str(len(valid)))


def check_player_kill_credit():
    """A player killed by a player (player_kill.py): the count of its own."""
    tallies = _sets(hg, PLAYER_KILL_COUNT_VAR)
    check(f"a player's death is credited once, on a PlayerState's {PLAYER_KILL_COUNT_VAR}, "
          "by the server alone",
          len(tallies) == 1 and _behind_authority(tallies[0]), f"{len(tallies)} write(s)")
    if not tallies:
        return
    above = _upstream(tallies[0])
    whose = [n for n in above if "PlayerController" in _title(n).replace(" ", "")
             and any(_title(f) == f"Get {HV.LastInstigator}"
                     for f in _feeds(BEL.find_input_pin(n, "Object")))]
    check(f"...to the last blow's instigator ({HV.LastInstigator}) where it is a player's "
          "controller: a wanderer's blow and the world-floor net are nobody's kill",
          len(whose) == 1, str(len(whose)))
    own = [n for n in above if _title(n) == "Branch" and any(
        "Not Equal" in _title(f) or "!=" in _title(f)
        for f in _feeds(BEL.find_input_pin(n, "Condition")))]
    check("...and not to the body's own controller", len(own) == 1 and
          _arm_into(tallies[0]) != ["else"], str(len(own)))
    # The fragment's head is its own authority switch, straight off the False
    # arm of the Branch that tells a player's body from a wanderer's.
    heads = [n for n in _switches(above) if _arm_into(n) == ["else"] and any(
        _title(f) == f"Get {HV.DespawnOnDeath}"
        for b in _ran_by(n) for f in _feeds(BEL.find_input_pin(b, "Condition")))]
    check("...on the player's arm of the death path alone (DespawnOnDeath false): a "
          "wanderer's death is no player kill", len(heads) == 1
          and all(heads[0] in _upstream(t) for t in tallies), str(len(heads)))


def check_blows():
    calls = take_hits(_wg_all)
    check("the weapon component's blows each call the target's TakeHit: the fist, the "
          "blade and the thrown blade (the pellet's is the native base's FirePellets, "
          "by name: verify/shot.py)", len(calls) == 3, str(len(calls)))
    fed = [{pin: bool(PIN.list_connected_pins(BEL.find_input_pin(c, pin)))
            for pin in ("self", "From", "InstigatedBy", "Cause")} for c in calls]
    check("...each on the target's health component, with a direction, an instigator "
          "and a cause", all(all(f.values()) for f in fed), str(fed))
    loose = [_title(n) for n in _wg_all if _title(n) in HEALTH_SETS
             or any(_title(n) == f"Set {v}" for v in STAMPS)]
    check("...and the weapon component writes no Health and no stamp of a blow itself",
          not loose, str(loose))
    check("the events of the component's graph are still found by title",
          bool(titled(hg, "Event Tick")))


def run():
    check_take_hit()
    check_replication()
    check_on_rep()
    check_tick_authority()
    check_kill_credit()
    check_player_kill_credit()
    check_blows()
