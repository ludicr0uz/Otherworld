# Source — the C++ module

Two modules and four targets. The runtime module, `Otherworld`, holds what multiplayer
needs and a Blueprint cannot do (`serversupportsysdesign.md` 4.3): the player's
predicted movement states (M12), the lag compensation of shots (M22) and the server's
replication graph (A2). The editor-only
module, `OtherworldEditor`, holds what the Python builders need and Python cannot reach.
Everything else stays in the Python builders.

| file | owns |
|---|---|
| `Otherworld.Target.cs` | the game target (single player and the listen side; what packaging builds) |
| `OtherworldEditor.Target.cs` | the editor target: the only one day-to-day work compiles |
| `OtherworldClient.Target.cs`, `OtherworldServer.Target.cs` | the client and dedicated-server targets: **source engine only** (below) |
| `Otherworld/Otherworld.Build.cs` | the module's dependencies (`Core`, `CoreUObject`, `Engine`, `NetCore`, `ReplicationGraph`: the engine plugin, enabled in `Otherworld.uproject`) |
| `Otherworld/Otherworld.cpp` | `IMPLEMENT_PRIMARY_GAME_MODULE`, nothing else |
| `Otherworld/Public/OtherworldCharacterMovement.h`, `Private/….cpp` | `UOtherworldCharacterMovement`: sprint, prone and the aim-walk as saved-move flags (`FLAG_Custom_0..2`), the speed of each state (`GetMaxSpeed`), the sprint's rules (the stamina latch, the forward cone) and the stamina, all stepped in `UpdateCharacterStateBeforeMovement` with the move's own delta time, so the owning client predicts them and the server makes the same ones. See "Predicted movement" below |
| `Otherworld/Public/OtherworldCharacter.h`, `Private/….cpp` | `AOtherworldCharacter`: a Character whose movement component is that class, and `bProne`, the one fact a simulated copy needs beside the engine's replicated crouch to stand as the server has it (M13, below). `BP_ThirdPersonCharacter` is reparented onto it by `Scripts/combat/player_move.py` |
| `Otherworld/Public/OtherworldMovementLibrary.h`, `Private/….cpp` | `UOtherworldMovementLibrary` (Python: `unreal.OtherworldMovementLibrary`): what the graphs and the probes say to the component and read off it, each a static taking the character's actor (`Scripts/uebp/nodes/move.py`) |
| `Otherworld/Public/OtherworldHitHistory.h`, `Private/….cpp` | `UOtherworldHitHistory`, a world subsystem: on a server with clients, one sample per frame of every character's capsule and physics-body transforms, a second back, and the rewound trace against them (M22, below) |
| `Otherworld/Public/OtherworldShotLibrary.h`, `Private/….cpp` | `UOtherworldShotLibrary` (Python: `unreal.OtherworldShotLibrary`): `ShotTrace`, the pellet's one trace node (`Scripts/uebp/nodes/shot.py`), the rewind a shooter gets, and what the history did, for the probes |
| `OtherworldEditor/OtherworldEditor.Build.cs` | the editor module's dependencies (adds `UnrealEd`, `BlueprintGraph`); only the Editor target lists it, so no game or server build carries it |
| `Otherworld/Public/OtherworldLoadLibrary.h`, `Private/….cpp` | `UOtherworldLoadLibrary` (Python: `unreal.OtherworldLoadLibrary`): what the load test reads off a server or a client (A1, `Scripts/probes/probe_net_load.py`): each connection's bytes and packets in and out, open actor channels and lag (`FOtherworldConnectionStats`, read with `get_editor_property`), the frame and world-tick times sampled between `StartFrameTiming` and `StopFrameTiming`, and the hit history's characters and samples |
| `Otherworld/Public/OtherworldReplicationGraph.h`, `Private/….cpp` | `UOtherworldReplicationGraph` (A2, `Scripts/net/CLAUDE.md` "Relevancy, update rates and dormancy"): the server's replication driver, named for the `IpNetDriver` in `Config/DefaultEngine.ini`. A grid-spatialisation node for everything with a place in the world, an always-relevant list for `bAlwaysRelevant` actors, and `UOtherworldReplicationGraphNode_ForConnection` per connection (the engine's viewer and view target, plus the viewer's PlayerState). Each class's cull distance and period are read off its CDO, which the builders write from `Scripts/net/relevancy_consts.py`; `CellSizeCm` is its one config value |
| `Otherworld/Public/OtherworldNetLibrary.h`, `Private/….cpp` | `UOtherworldNetLibrary` (Python: `unreal.OtherworldNetLibrary`): `IsLevelActor`, whether an actor was placed in the level (`AActor::IsNetStartupActor`, not Blueprint-callable), which the take asks before destroying one (`Scripts/uebp/nodes/level.py`) |
| `OtherworldEditor/Public/OtherworldBlueprintNetLibrary.h`, `Private/….cpp` | `UOtherworldBlueprintNetLibrary` (Python: `unreal.OtherworldBlueprintNetLibrary`): a custom event's net flags and parameters, a variable's replication and OnRep graph, and the same read back off a compiled class. Wrapped by `Scripts/uebp/net.py`; checked by `Scripts/dev/check_net_authoring.py` |

They began as the packaging step's generated files in `Intermediate/Source`; both modules
are listed under `Modules` in `Otherworld.uproject` (`OtherworldEditor` as type `Editor`).

## Compile

```bash
"/Users/Shared/Epic Games/UE_5.8/Engine/Build/BatchFiles/Mac/Build.sh" \
    OtherworldEditor Mac Development \
    -project="/Users/alexeysukhov/Documents/Unreal Projects/Otherworld/Otherworld.uproject" -waitmutex
```

- **Time** (M-series Mac, 10 cores, 16 GB): **27 s** from nothing for the runtime module alone (5 actions: the shared PCH,
  two sources, the link, the metadata), **12 s** to add the editor module to that (7 actions),
  **3 s** when nothing changed.
- **Toolchain:** **Xcode 16.2** (16C5032a; Apple clang 16.0.0, Mac SDK 15.2), on macOS 26.5.
  UE 5.8.3 accepts Xcode 15.2 to 27.9 (`Engine/Config/Apple/Apple_SDK.json`); do not upgrade
  Xcode for it.
- **Output:** `Binaries/Mac/libUnrealEditor-Otherworld*.dylib` (one per module), `UnrealEditor.modules` and
  `OtherworldEditor.target`, all git-ignored.

## Predicted movement (`UOtherworldCharacterMovement`, M12)

- **What a graph may do:** hand it what the player wants (`SetSprintHeld`, `SetStance`,
  `SetAimWalk`, on the machine that reads the keys) and read what it made of that
  (`IsSprinting`, `GetStamina`, ...). A graph never writes `MaxWalkSpeed`, a crouched height or
  the stamina: a value written from a Blueprint exists on one machine, and the server pulls
  the client back to its own (the verifiers fail on such a write).
- **The numbers are properties of the character's template**, written by
  `combat/player_move.py` from the tuning tables, so the server and every client read the
  same ones off the same asset. `SetPace`, `SetStamina` and `SpendStamina` do nothing
  without authority.
- **A new predicted state** needs all of: a want (a flag in `FOtherworldSavedMove`,
  `GetCompressedFlags`, `UpdateFromCompressedFlags`, `CanCombineWith`, and saved over the
  replay in `ClientUpdatePositionAfterServerUpdate`), and its effect computed only from the
  wants and the move (`UpdateCharacterStateBeforeMovement`, `GetMaxSpeed`). `FLAG_Custom_3`
  is the last free flag; after it a state travels in `FOtherworldNetworkMoveData`.
- **State the simulation carries from move to move** (the stamina, the sprint's latch, the
  aim's ease) is put back in `FOtherworldSavedMove::CombineWith` (the engine re-runs two moves
  as one, so their time would be spent twice) and sent with every correction
  (`FOtherworldMoveResponseDataContainer`), since the moves after a correction are replayed
  from it.
- **The client reports its stamina with each move** (a byte, `FOtherworldNetworkMoveData`),
  and `ServerCheckClientError` corrects a client more than `StaminaErrorTolerance` off. That
  is how stamina the server changes (a blocked blow) reaches the client: no RPC.
- **Every correction a client takes is one `MOVE-CORRECTION` log line** and a count
  (`CorrectionCount`). `uepy.py --net --lag 120` shows the count per process;
  `Scripts/probes/probe_net_move_states.py` is the check that the states take none.
- **Another player's copy of the character** (a simulated proxy) runs no moves, so it gets
  its stance by replication (M13): the engine's `bIsCrouched`, and
  `AOtherworldCharacter::bProne` (`COND_SimulatedOnly`), which the server writes in
  `UpdateCharacterStateBeforeMovement`. Both notifies call `ApplySimulatedStance`, which
  sizes the capsule to the stance the two flags make and is safe to run twice (they
  arrive in either order): the engine's own `OnRep_IsCrouched` crouches again whatever
  the capsule is, and a second crouch to the height it already has resets the mesh to its
  standing offset. `GetStance(actor)` answers 0/1/2 on any machine. The aim and the pose
  on that copy are the weapon component's (`Scripts/net/CLAUDE.md`, "Other players'
  characters").

## Lag compensation (`UOtherworldHitHistory`, `UOtherworldShotLibrary`, M22)

`Scripts/net/CLAUDE.md`, "Lag compensation", has the design; `combat/lag_tuning.py` the
numbers, which the fire graph hands `ShotTrace` as pin literals.

- **Record after the actors tick** (`FWorldDelegates::OnWorldPostActorTick`): the mesh
  component's tick poses the bones and the kinematic bodies follow in the same frame, so
  that is where the frame's bodies are. A tickable subsystem would read the frame before.
- **Only a server with clients records** (`GetNetMode()`), so single player pays nothing
  and `ShotTrace` with a rewind of 0 is the two engine traces the graph used to make
  (`LineTraceSingleByChannel` on Visibility, `USkeletalMeshComponent::LineTraceComponent`
  for the bone), parameter for parameter.
- **A rewound trace moves nothing.** `FBodyInstance::LineTrace` tests a body where it is
  now, so the line is taken from the body's then-frame into its now-frame
  (`Then.Inverse() * Now`: UE's `A * B` applies A first) and the hit back. The body's
  transforms carry no scale (`GetUnrealWorldTransform`), so the move is rigid.
- **Bodies by index:** a sample holds `Mesh->Bodies` by position. A mesh whose body count
  differs from a sample's (collision toggled) is judged by its capsule alone that frame.
- **The ping is a second old:** `UNetConnection::AvgLag` is averaged over its stat period
  and the PlayerState's over four seconds, so the first shot after a join is rewound by
  the join's inflated round trip (measured 90-250 ms on the loopback). The cap bounds it.

## Traps

- **`Binaries/` is not committed, so a fresh clone must compile before the editor opens.**
  With the module missing or built for another engine build, the editor asks to rebuild, and a
  headless `UnrealEditor-Cmd` (every `uepy.py` run) cannot answer. Run the command above first.
- **Close this project's editors before compiling** (`uepy.py --close-editors`): the editor
  holds the dylib. Built while *any* `UnrealEditor` is running, even another project's, UBT
  writes a numbered copy (`libUnrealEditor-Otherworld-0001.dylib`) and points
  `UnrealEditor.modules` at it. That loads fine; it is only untidy.
  - **Built while this project's editor is still exiting, the numbered copy is written and
    `UnrealEditor.modules` is not updated:** the next editor loads the old module and the
    new classes do not exist (`unreal.OtherworldMovementLibrary` is missing, every new node
    path "resolves nowhere"). Check `Binaries/Mac/UnrealEditor.modules` names the newest
    dylib; if not, wait for the editor to be gone, `touch` a source file and build again.
- **The installed engine compiles the Editor and Game targets only.** `OtherworldServer` (and
  the Client) stop in a second with "Server targets are not currently supported from this
  engine distribution". They need UE built from source, which is the GCP build machine's job
  (`Scripts/server/gcp/CLAUDE.md`). Locally a dedicated server is the editor binary with
  `-server` (`serversupportsysdesign.md` 4.4).
- **Proving the module is loaded:** `lsof -p <editor pid> | grep Otherworld.*dylib`, or
  `hasattr(unreal, "OtherworldMovementLibrary")` in the editor's Python.
- **A property for Python:** the component's state is `BlueprintReadOnly` (probes read it
  with `get_editor_property`), and its numbers are `EditAnywhere`, which the builder and a
  probe write.
- **A Character's movement component is a native subobject:** only a native class picks its
  class (`SetDefaultSubobjectClass` in the constructor), which is all `AOtherworldCharacter`
  is for. Reparenting a Blueprint onto it keeps the old component's settings (checked
  property by property in `player_move.reparent_player`).
- **Two engine virtuals have a deprecated overload of the same name** in 5.8
  (`ServerCheckClientError`, `OnClientCorrectionReceived`: the `UPrimitiveComponent*` ones).
  Override the `FMovementBaseInterfaceData*` one and add `using Super::<name>;`, or the
  override hides the other.
- **The replication graph class is not exposed to Python** (`hasattr(unreal,
  "OtherworldReplicationGraph")` is False): the net driver loads it by path. Prove it is
  in use from a server's log (`LogReplicationGraph`), not from Python.
- **A function for Python is a `BlueprintCallable` static of a `UBlueprintFunctionLibrary`.**
  Python names it in snake case, turns `bool` plus out-parameters into a return of `None` or
  the tuple of outs, and an `enum class` into `unreal.<Enum>.<UPPER_SNAKE>`. Change one and
  the running editor still has the old: close it, compile, and let `uepy.py` boot a new one.
- **Editor-only code goes in `OtherworldEditor`, never the runtime module:** `UnrealEd` and
  `BlueprintGraph` do not exist in a game or server build.
- **New code keeps both modes:** single player is the standalone net mode of the same code
  (`serversupportsysdesign.md` 4.8). No `#if`-ed multiplayer copy of a system.
