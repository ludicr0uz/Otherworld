# uebp — authoring Blueprints from Python

`__init__.py` maps the modules; the root `CLAUDE.md` ("Authoring Blueprint graphs from
Python") holds the traps of graphs, pins, variables and components. This file is the guide to
**networked** Blueprints: `net.py`.

## Networked Blueprints (`uebp/net.py`)

An RPC is a custom event with net flags; a replicated variable is a member variable with
property flags. Neither is reachable from Python (`K2Node_Event.FunctionFlags` is a bare
`UPROPERTY()`), so `net.py` calls `UOtherworldBlueprintNetLibrary`, in the editor-only C++
module `Source/OtherworldEditor` (`Source/CLAUDE.md`: compile it before the editor opens). It
writes exactly what the Blueprint editor's details panel writes.

```python
from uebp import net
from uebp.vars import FLOAT, VECTOR

fire = net.server_event(ed, "Server_Fire", [("Origin", VECTOR), ("Spread", FLOAT)])
origin = out(fire, "Origin")                    # a parameter is an output pin of the event
call = _node(ed, "Server_Fire")                 # the call: a local event, by its bare name

declare(ed, WV.TABLE)                           # first: re-declaring drops replication
net.replicate(bp, WV.Loaded, unreal.LifetimeCondition.COND_OWNER_ONLY)
on_rep = net.rep_notify(bp, WV.Held)            # the graph editor of OnRep_Held
BEL.compile_blueprint(bp)
net.replicate_actor(bp)                         # class defaults: after the compile
net.replicate_component(bp, "Weapon")           # a component of an actor Blueprint
net.replicate_component(component_bp)           # a component Blueprint's own default
```

| helper | does |
|---|---|
| `custom_event(ed, name, params=())` | a plain custom event; `params` are `(name, pin type)` pairs, the type a `uebp.vars` spec |
| `server_event` / `client_event` / `multicast_event(ed, name, params=(), reliable=…)` | the event, set Run on Server / on Owning Client / Multicast. Server and client are reliable by default, a multicast is not |
| `set_rpc(event, kind, reliable)` | the same on an event that exists; `net.LOCAL` clears it |
| `event_rpc(event)`, `compiled_rpc(bp, name)` | `(kind, reliable)` read off the node, and off the compiled function |
| `replicate(bp, var, condition=None)` | Replicated |
| `rep_notify(bp, var, condition=None)` | RepNotify; creates `OnRep_<var>` if missing and returns its graph editor |
| `unreplicate(bp, var)` | neither (the OnRep graph stays) |
| `variable_replication(bp, var)`, `compiled_replication(bp, var)` | `(kind, OnRep name[, condition])` as declared, and as compiled |
| `replicate_actor(bp, on=True)`, `replicate_component(bp, component=None, on=True)` | the `bReplicates` default |
| `replicates(bp, component=None)` | reads it back |

Kinds are `net.SERVER`, `CLIENT`, `MULTICAST`, `LOCAL`, and `net.REPLICATED`, `REP_NOTIFY`,
`NONE`. Every setter reads its own write back and raises.

**The check:** `python3 Scripts/dev/uepy.py --summary Scripts/dev/check_net_authoring.py`
builds a scratch actor and a scratch component with all of the above and reads each flag back
off the graph, off the compiled class and after a reload from disk. Run it after changing
`net.py` or the C++ library. A system's own verifier asserts its RPCs with `compiled_rpc` and
`compiled_replication`: the compiled class is what the game runs.

### The mode questions (`uebp.nodes`)

Single player and multiplayer are one graph (`serversupportsysdesign.md` 4.8): standalone
is a net mode in which the one machine has authority, is locally controlled, and runs a
Server or Multicast event as a plain local call. So ask the question; never author an
offline copy of a graph.

| question | node |
|---|---|
| does this machine own the state? (server, and single player) | `FN_HAS_AUTHORITY` (pure; self is an actor), or the exec switch `MACRO_SWITCH_AUTHORITY` (an actor graph) / `MACRO_SWITCH_AUTHORITY_COMP` (a component graph): outs `Authority`, `Remote` |
| is this pawn driven by this machine's player? (input, camera, HUD, own sounds) | `FN_IS_LOCALLY_CONTROLLED` (a pawn), `FN_IS_LOCAL_CONTROLLER` (a controller) |
| is there no network at all? | `FN_IS_STANDALONE` |
| is there no screen or speaker here? | `FN_IS_DEDICATED_SERVER` |
| is this the server, of either kind, or single player? | `FN_IS_SERVER` |
| whose pawn does this widget / HUD belong to? | `FN_GET_OWNING_PLAYER_PAWN` (a widget), `FN_GET_OWNING_PAWN` (the HUD): never `GetPlayerPawn(0)` on a server, where index 0 is whoever joined first |

### Traps

- **Declare, then replicate.** `declare(ed, TABLE)` removes and re-adds each variable, which
  resets its replication. Call `net.replicate` / `rep_notify` after it, on every build. The
  `OnRep_` graph survives the re-declare, with whatever was authored in it: a builder that
  authors it wipes its nodes first (not the entry node), as `_events` does for the event graph.
- **An event's name must be free.** The engine does not fail on a taken or invalid name: it
  keeps a generated one. `custom_event` raises instead, so a rebuild wipes the graph first.
- **`K2Node_CustomEvent.CustomFunctionName` is not exposed either.** Find an event with
  `ed.find_event_node(name)`.
- **Class defaults are written after a compile and need another.** `replicate_actor` and
  `replicate_component` write the CDO or the component template, like `_apply_defaults`:
  compile first (a stale class loses the write), then compile again and save.
- **A replicated component needs a replicating owner,** and a Server event runs only when
  called on an actor (or a component of one) that the calling client owns: its pawn, its
  controller, its player state. Called on anything else, the engine drops it with a log line.
- **Blueprint calls the OnRep on the server too** when a graph sets the variable (the set node
  does it), so in single player the OnRep runs as well. C++ would not.
- **A Client or Multicast event called on a client runs only there**, with no error. Call
  them behind the authority switch.
- **Reliable is for what must arrive** (a shot fired, a death). An effect that repeats goes
  unreliable: a full reliable buffer disconnects the client.
- **Flags that hold in the authoring editor prove nothing about the wire.** This check
  proves the flags are compiled and saved; whether an RPC arrives takes two processes.
