"""check_net_authoring.py -- uebp.net authors networked Blueprints that hold.

    python3 Scripts/dev/uepy.py --summary Scripts/dev/check_net_authoring.py

Builds two throwaway Blueprints under /Game/Tmp with uebp.net, an actor and a
component: a Server, a Client and a Multicast custom event (one with
parameters, called through the authority switch), a Replicated and a RepNotify
variable with its OnRep graph, the actor and one of its components
replicating. Then reads every flag back three ways: off the graph, off the
compiled class, and again after the package is reloaded from disk (a flag
that lives only in the editor that set it would build a game with no RPCs).
Deletes both. Exits non-zero on a failed check.

Run it after changing Source/OtherworldEditor or uebp/net.py.
"""

import os
import sys

import unreal

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPTS)
for _name in [m for m in sys.modules if m.split(".")[0] == "uebp"]:
    del sys.modules[_name]

from uebp import net                                              # noqa: E402
from uebp.graph import (                                          # noqa: E402
    BEL, BGE, _add_component, _connect, _create_blueprint, _events, _node, _pin,
    _pin_names, _root_handle, out, then)
from uebp.layout import arrange                                   # noqa: E402
from uebp.nodes.actor import FN_HAS_AUTHORITY                     # noqa: E402
from uebp.nodes.palette import (                                  # noqa: E402
    MACRO_SWITCH_AUTHORITY, MACRO_SWITCH_AUTHORITY_COMP)
from uebp.nodes.system import FN_PRINT                            # noqa: E402
from uebp.vars import FLOAT, INT, VECTOR, Var, declare            # noqa: E402

ACTOR = "/Game/Tmp/BP_NetCheck_Actor"
COMPONENT = "/Game/Tmp/BP_NetCheck_Component"

Health = Var("Health", FLOAT)
Ammo = Var("Ammo", INT)
Local = Var("Local", INT)
TABLE = (Health, Ammo, Local)
# event name -> (what it must read back as, its parameters)
EVENTS = {
    "Server_Fire": ((net.SERVER, True), (("Origin", VECTOR), ("Seed", INT))),
    "Client_Hit": ((net.CLIENT, True), (("Damage", FLOAT),)),
    "Multi_Shot": ((net.MULTICAST, False), ()),
    "Multi_Death": ((net.MULTICAST, True), ()),
    "Plain": ((net.LOCAL, False), ()),
}
MAKERS = {net.SERVER: net.server_event, net.CLIENT: net.client_event,
          net.MULTICAST: net.multicast_event}

PASS, FAIL = [], []


def check(label, ok, detail=""):
    (PASS if ok else FAIL).append(label)
    unreal.log_warning(f"[VERIFY] {'PASS' if ok else 'FAIL'}  {label}"
                       + (f" — {detail}" if detail and not ok else ""))


def _fresh(path, parent):
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)
    return _create_blueprint(path, parent)


def _author_events(ed, switch_macro):
    """One event of each kind; BeginPlay calls the server one behind the
    authority switch, and the server one calls the multicast."""
    _tick, begin = _events(ed, rebuild=True)
    made = {}
    for name, ((kind, reliable), params) in EVENTS.items():
        if kind == net.LOCAL:
            made[name] = net.custom_event(ed, name, params)
        else:
            made[name] = MAKERS[kind](ed, name, params, reliable=reliable)
    switch = ed.add_macro_node(switch_macro)
    _connect(then(begin), _pin(switch, "execute"))
    call = _node(ed, "Server_Fire")                 # a local event is called by its name
    _connect(out(switch, "Remote"), _pin(call, "execute"))
    shot = _node(ed, "Multi_Shot")
    _connect(then(made["Server_Fire"]), _pin(shot, "execute"))
    seed = ed.add_set_member_variable_node(Ammo)
    _connect(then(shot), _pin(seed, "execute"))
    _connect(out(made["Server_Fire"], "Seed"), _pin(seed, Ammo))
    return made


def build_actor():
    bp = _fresh(ACTOR, unreal.Actor)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    declare(ed, TABLE)
    _author_events(ed, MACRO_SWITCH_AUTHORITY)
    net.replicate(bp, Health, unreal.LifetimeCondition.COND_OWNER_ONLY)
    on_rep = net.rep_notify(bp, Ammo)
    said = _node(on_rep, FN_PRINT)
    _connect(on_rep.find_graph_entry_pin(), _pin(said, "execute"))
    auth = _node(ed, FN_HAS_AUTHORITY)              # the pure question, beside the switch
    assert out(auth)
    _add_component(bp, _root_handle(bp), unreal.SceneComponent, "Carried")
    _add_component(bp, _root_handle(bp), unreal.SceneComponent, "Still")
    arrange(ed)
    arrange(on_rep)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("the scratch actor did not compile")
    net.replicate_actor(bp)
    net.replicate_component(bp, "Carried")
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("the scratch actor did not recompile")
    unreal.EditorAssetLibrary.save_loaded_asset(bp)
    return bp


def build_component():
    bp = _fresh(COMPONENT, unreal.ActorComponent)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    declare(ed, TABLE)
    _author_events(ed, MACRO_SWITCH_AUTHORITY_COMP)
    net.rep_notify(bp, Ammo)
    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("the scratch component did not compile")
    net.replicate_component(bp)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("the scratch component did not recompile")
    unreal.EditorAssetLibrary.save_loaded_asset(bp)
    return bp


def _errors(ed):
    return [n.get_name() for n in ed.list_nodes_with_errors()]


def check_events(tag, bp):
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    check(f"{tag}: the event graph compiled with no node in error", not _errors(ed),
          str(_errors(ed)))
    for name, (want, params) in EVENTS.items():
        node = ed.find_event_node(name)
        check(f"{tag}: {name} is in the graph", bool(node))
        if not node:
            continue
        got = net.event_rpc(node)
        check(f"{tag}: {name}'s node reads {want}", got == want, repr(got))
        got = net.compiled_rpc(bp, name)
        check(f"{tag}: {name}'s compiled function reads {want}", got == want, repr(got))
        pins = _pin_names(node)[1]
        for param, _type in params:
            check(f"{tag}: {name} carries the parameter {param}", param in pins, str(pins))


def check_variables(tag, bp, health):
    want = (net.REP_NOTIFY, "OnRep_Ammo", "COND_NONE")
    got = net.variable_replication(bp, Ammo)
    check(f"{tag}: Ammo is declared RepNotify through OnRep_Ammo", got == want, repr(got))
    got = net.compiled_replication(bp, Ammo)
    check(f"{tag}: Ammo's compiled property is RepNotify through OnRep_Ammo",
          got == want[:2], repr(got))
    check(f"{tag}: the OnRep_Ammo function graph exists",
          bool(BGE.get_graph_editor_by_name(bp, "OnRep_Ammo")))
    got = net.variable_replication(bp, Health)
    check(f"{tag}: Health is declared {health}", got == health, repr(got))
    got = net.compiled_replication(bp, Health)
    check(f"{tag}: Health's compiled property is {health[0]}", got == (health[0], "None"),
          repr(got))
    got = net.compiled_replication(bp, Local)
    check(f"{tag}: Local, never marked, does not replicate", got == (net.NONE, "None"),
          repr(got))


def check_actor(tag, bp):
    check_events(tag, bp)
    check_variables(tag, bp, (net.REPLICATED, "None", "COND_OWNER_ONLY"))
    check(f"{tag}: the actor replicates", net.replicates(bp))
    check(f"{tag}: its component Carried replicates", net.replicates(bp, "Carried"))
    check(f"{tag}: its component Still does not", not net.replicates(bp, "Still"))


def check_component(tag, bp):
    check_events(tag, bp)
    check_variables(tag, bp, (net.NONE, "None", "COND_NONE"))
    check(f"{tag}: the component Blueprint replicates", net.replicates(bp))


def check_undo(bp):
    """The setters also clear: a rebuild that drops an RPC must not leave it."""
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    node = ed.find_event_node("Multi_Death")
    net.set_rpc(node, net.LOCAL, False)
    net.unreplicate(bp, Ammo)
    net.replicate_actor(bp, False)
    check("cleared: the scratch actor recompiles", bool(BEL.compile_blueprint(bp)))
    got = net.compiled_rpc(bp, "Multi_Death")
    check("cleared: Multi_Death compiles as a local event", got == (net.LOCAL, False), repr(got))
    got = net.compiled_replication(bp, Ammo)
    check("cleared: Ammo no longer replicates", got == (net.NONE, "None"), repr(got))
    check("cleared: the actor no longer replicates", not net.replicates(bp))


def reloaded(path):
    """The Blueprint as the next editor will load it: from its saved package."""
    package = unreal.load_package(path)
    unreal.EditorLoadingAndSavingUtils.reload_packages([package])
    return unreal.EditorAssetLibrary.load_asset(path)


def main():
    try:
        actor, component = build_actor(), build_component()
        check_actor("actor, as built", actor)
        check_component("component, as built", component)
        check_actor("actor, reloaded from disk", reloaded(ACTOR))
        check_component("component, reloaded from disk", reloaded(COMPONENT))
        check_undo(unreal.EditorAssetLibrary.load_asset(ACTOR))
    finally:
        for path in (ACTOR, COMPONENT):
            if unreal.EditorAssetLibrary.does_asset_exist(path):
                unreal.EditorAssetLibrary.delete_asset(path)
    unreal.log_warning(f"[VERIFY] {len(PASS)}/{len(PASS) + len(FAIL)} checks passed "
                       "(net authoring: RPC events, replicated variables, replicating "
                       "actors and components)")
    if FAIL:
        raise RuntimeError(f"{len(FAIL)} net authoring checks failed: {'; '.join(FAIL)}")


if __name__ == "__main__":
    main()
