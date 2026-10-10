"""verify.damage -- health is the server's (combat/damage.py): TakeHit, which
every blow calls, is the native parent's (task W3), and the graph writes none
of what it writes; what of the component replicates and what does not;
OnHealthChanged, a client's side of a change; the Tick's server-only parts
(the world-floor net, the drain, Die, the replacement) and the death path's
own latch behind OnDied; the kill credited to the
blow's instigator; and that no blow writes a target's health itself.

That a client's bar falls is two processes' to prove: probes/probe_net_health.py.
"""

import unreal

from combat import health_vars as HV
from combat import health_native
from combat.damage import (
    DIE, NATIVE_REPLICATED, ON_DIED, ON_HEALTH_CHANGED, REPLICATED, TAKE_HIT)
from combat.game_state import DAMAGED_BY_PLAYER_VAR, KILL_COUNT_VAR, LAST_DAMAGE_VAR
from combat.hit_reaction import LAST_HIT_FROM_VAR, PREV_HEALTH_VAR
from combat.verify.common import (
    BEL, HEALTH_SETS, PIN, check, graph, in_pins, take_hits, titled)
from combat.verify.fixtures import _wg_all, char, drain_writes, health_bp, hg, npc
from combat.verify.sights import _feeds, _title
from net.state_consts import PLAYER_KILL_COUNT_VAR
from uebp import net
from uebp.nodes.health import HEALTH_BASE_CLASS

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


def _event(name):
    return graph(health_bp).find_event_node(name)


def _below(event):
    """Every node of the component's graph an exec path from ``event`` reaches."""
    return [n for n in hg if event in _upstream(n)]


def check_take_hit():
    check(f"BP_HealthComponent is a child of the native base ({HEALTH_BASE_CLASS})",
          health_native.is_native(health_bp), str(BEL.get_blueprint_parent_class(health_bp)))
    got = {name: net.compiled_rpc(health_bp, name) for name in (TAKE_HIT, DIE)}
    check(f"...which has {TAKE_HIT} and {DIE}, plain functions, not RPCs (only the "
          "server's call does anything, and nothing a client sends reaches either), and "
          "the graph has no event named as either",
          got == {TAKE_HIT: (net.LOCAL, False), DIE: (net.LOCAL, False)}
          and not [n for n in health_native.NATIVE_FUNCTIONS if _event(n)], str(got))
    own = {str(v) for v in BEL.list_member_variable_names(health_bp)}
    cdo = unreal.get_default_object(BEL.generated_class(health_bp))
    missing = []
    for var in HV.NATIVE:
        try:
            cdo.get_editor_property(str(var))
        except Exception:                                         # noqa: BLE001
            missing.append(str(var))
    check(f"...and holds what a blow writes ({', '.join(str(v) for v in HV.NATIVE)}): "
          "each a property of the class and none a variable of the Blueprint",
          not missing and not own & {str(v) for v in HV.NATIVE},
          f"missing {missing}, the Blueprint's own {sorted(own & {str(v) for v in HV.NATIVE})}")
    check("...and no graph of an earlier build's notify beside the base's",
          not [g for g in health_native.RETIRED_GRAPHS if BEL.find_graph(health_bp, g)])
    # What only TakeHit may write, the graph does not: the count a client
    # tells a blow by, who struck it and with what, which way it came.
    loose = [_title(n) for var in (HV.HitCount, HV.LastInstigator, HV.LastCause,
                                   LAST_HIT_FROM_VAR, DAMAGED_BY_PLAYER_VAR)
             for n in _sets(hg, var)]
    check("the graph writes none of a blow's stamps itself (the count, who, with what, "
          "which way, DamagedByPlayer)", not loose, str(loose))
    stamps = _sets(hg, LAST_DAMAGE_VAR)
    event = _event(ON_HEALTH_CHANGED)
    check(f"...and {LAST_DAMAGE_VAR} once, a client's own clock in {ON_HEALTH_CHANGED}",
          len(stamps) == 1 and event and event in _upstream(stamps[0]), str(len(stamps)))


def check_replication():
    for var, notify in NATIVE_REPLICATED.items():
        got = net.compiled_replication(health_bp, str(var))
        want = (net.REP_NOTIFY if notify != "None" else net.REPLICATED, notify)
        check(f"{var} is the base's, {'a RepNotify' if notify != 'None' else 'Replicated'}",
              got == want, str(got))
    for var in REPLICATED:
        got = net.variable_replication(health_bp, var)
        check(f"{var} is Replicated", got == (net.REPLICATED, "None", "COND_NONE")
              and net.compiled_replication(health_bp, var)[0] == net.REPLICATED, str(got))
    check("BP_HealthComponent replicates by default", net.replicates(health_bp))
    check("...and on the player's character and on the wanderer, which replicate",
          net.replicates(char, "HealthComponent") and net.replicates(char)
          and net.replicates(npc, "HealthComponent") and net.replicates(npc))


def check_on_rep():
    event = _event(ON_HEALTH_CHANGED)
    check(f"the graph has the base's {ON_HEALTH_CHANGED} event (a client's, told when "
          "a Health arrives)", bool(event))
    if not event:
        return
    nodes = _below(event)
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
          "net's and the drain's are each behind an authority switch (a blow's is "
          "TakeHit's, C++)",
          len(own) == 2 and all(_behind_authority(n) for n in own),
          str([_behind_authority(n) for n in own]))
    check("...and the drain's own PrevHealth with it",
          all(_behind_authority(n) for n in drain_writes), str(len(drain_writes)))
    tick_all = _below(tick[0]) if tick else []
    dies = [n for n in hg if _title(n) == DIE]
    gate = [g for d in dies for g in _ran_by(d)]
    check(f"Dead is the base's to set: the graph has no Set of it, and calls {DIE} once, "
          "from the Tick, where Health is at 0 and Dead not yet said",
          not _sets(hg, HV.Dead) and len(dies) == 1 and dies[0] in tick_all
          and len(gate) == 1 and _arm_into(dies[0]) == ["else"]
          and {_title(f) for f in _feeds(BEL.find_input_pin(gate[0], "Condition"))}
          == {f"Get {HV.Dead}"},
          f"{len(dies)} call(s), {len(_sets(hg, HV.Dead))} Set(s)")
    died = _event(ON_DIED)
    played = _sets(hg, HV.DeathPlayed)
    gate = [g for p in played for g in _ran_by(p)]
    check(f"the death path hangs on the base's {ON_DIED} (the server's from {DIE}, a "
          f"client's when Dead arrives) and runs once on each machine, on its own "
          f"{HV.DeathPlayed}",
          bool(died) and len(played) == 1 and len(gate) == 1
          and _arm_into(played[0]) == ["else"] and _ran_by(gate[0]) == [died]
          and {_title(f) for f in _feeds(BEL.find_input_pin(gate[0], "Condition"))}
          == {f"Get {HV.DeathPlayed}"}, str([_title(g) for g in gate]))
    check("...and nothing of it off the Tick: the corpse, the kill and the replacement "
          "are reached from the event alone", bool(died) and played
          and played[0] not in tick_all, str(len(tick_all)))
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
          "blade and the thrown blade (the pellet's is the native base's FirePellets: "
          "verify/shot.py)", len(calls) == 3, str(len(calls)))
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
