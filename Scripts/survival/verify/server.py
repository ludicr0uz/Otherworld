"""Survival is the server's (task M26): what replicates, to whom, and that
nothing a client's copy runs writes a stat or the ability system."""

import unreal

from combat.paths import CHARACTER_BP_PATH
from combat.verify.common import BEL, PIN, by_pins, cdo, check, graph, in_pins, load
from survival.consume_ability import NET_POLICY
from survival.install import PLAYER_REPLICATED
from survival.paths import CONSUME_ABILITY_PATH, SURVIVAL_BP_PATH
from survival.survival_component import REPLICATED
from uebp import net

SWITCH = "Switch Has Authority"
OWNER_ONLY = "COND_OWNER_ONLY"


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _execs_into(node):
    """The (node, output pin name) pairs wired into ``node``'s execute pin."""
    pin = BEL.find_input_pin(node, "execute")
    return [(PIN.get_owning_node(q), str(PIN.get_pin_name(q)))
            for q in PIN.list_connected_pins(pin)] if pin else []


def _behind_authority(node, limit=400):
    """True when every exec path into ``node`` comes off a Switch Has
    Authority's Authority pin, and at least one does."""
    seen, todo, found = set(), [node], False
    while todo and len(seen) < limit:
        cur = todo.pop()
        if cur.get_path_name() in seen:
            continue
        seen.add(cur.get_path_name())
        into = _execs_into(cur)
        if not into and cur is not node and SWITCH not in _title(cur):
            return False        # reached an event without passing a switch
        for src, pin in into:
            if SWITCH in _title(src):
                if pin != "Authority":
                    return False
                found = True
            else:
                todo.append(src)
    return found


def check_stats_replicate(bp):
    declared = {str(v): net.variable_replication(bp, str(v)) for v in REPLICATED}
    check("Hunger, Thirst and Temperature replicate to the owning client alone",
          all(kind == net.REPLICATED and cond.upper() == OWNER_ONLY
              for kind, _rep, cond in declared.values()), str(declared))
    compiled = {str(v): net.compiled_replication(bp, str(v)) for v in REPLICATED}
    check("...and compiled so", all(kind == net.REPLICATED for kind, _rep in compiled.values()),
          str(compiled))
    check("BP_SurvivalComponent replicates by default", net.replicates(bp))


def check_server_writes(bp):
    nodes = graph(bp).list_all_nodes()
    switches = [n for n in nodes if SWITCH in _title(n)]
    check("two authority switches: BeginPlay's grant and the Tick",
          len(switches) == 2, str(len(switches)))
    writes = [n for n in nodes if _title(n) in ("Set Hunger", "Set Thirst", "Set Temperature")]
    check("the decay writes Hunger and Thirst only with authority",
          sorted(_title(n) for n in writes) == ["Set Hunger", "Set Thirst"]
          and all(_behind_authority(n) for n in writes),
          str([(_title(n), _behind_authority(n)) for n in writes]))
    asc_writes = (by_pins(nodes, "AbilityClass", "InputID")
                  + [n for n in by_pins(nodes, "SpecHandle")
                     if "NewGameplayTag" not in in_pins(n)]
                  + by_pins(nodes, "GameplayEffect", "StacksToRemove"))
    check("the grant, and every debuff's apply and remove, are behind authority too",
          len(asc_writes) == 5 and all(_behind_authority(n) for n in asc_writes),
          str([(_title(n), _behind_authority(n)) for n in asc_writes]))


def check_install():
    player = load(CHARACTER_BP_PATH)
    got = {name: net.replicates(player, name) for name in PLAYER_REPLICATED}
    check("on the player the ability system and the survival component replicate",
          all(got.values()) and len(got) == 2, str(got))


def check_ability():
    bp = load(CONSUME_ABILITY_PATH)
    policy = cdo(bp).get_editor_property("net_execution_policy") if bp else None
    check("GA_ConsumeItem runs on the server only", policy == NET_POLICY
          and NET_POLICY == unreal.GameplayAbilityNetExecutionPolicy.SERVER_ONLY, str(policy))


def run():
    bp = load(SURVIVAL_BP_PATH)
    if bp:
        check_stats_replicate(bp)
        check_server_writes(bp)
    check_install()
    check_ability()
