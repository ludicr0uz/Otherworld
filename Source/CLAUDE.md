# Source — the C++ module

Two modules and four targets. The runtime module, `Otherworld`, holds what multiplayer
needs and a Blueprint cannot do (`serversupportsysdesign.md` 4.3): the player's
predicted movement states (M12), the lag compensation of shots (M22), the server's
replication graph (A2), how often a dedicated server poses a body (A4), the record of
what a player carries (A3a, A3b) and what a Server event checks before it runs (A5). The editor-only
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
| `Otherworld/Public/OtherworldHitHistory.h`, `Private/….cpp` | `UOtherworldHitHistory`, a world subsystem: on a server with clients, where every character's capsule and physics bodies were, a second back, in two rings of fixed capacity per character (the frames, at most 30 a second; the poses, one per frame that posed the mesh anew), and the rewound trace against them (M22 and A4, below) |
| `Otherworld/Public/OtherworldServerPose.h`, `Private/….cpp` | `UOtherworldServerPose`, a world subsystem, and `UOtherworldPoseLibrary` (Python: `unreal.OtherworldPoseLibrary`): on a dedicated server alone, how often a body's mesh is posed (every frame near another player, a few times a second further off, twice with nobody near or as a ragdoll: the engine's Update Rate Optimization, whose not-rendered rate it rewrites per body), and every other skinned mesh on the body stopped from ticking (A4; `Scripts/combat/server_pose.py` calls `ThrottleServerPose`, `Scripts/combat/pose_tuning.py` has the numbers, `Scripts/net/CLAUDE.md` the measurements) |
| `Otherworld/Public/OtherworldShotLibrary.h`, `Private/….cpp` | `UOtherworldShotLibrary` (Python: `unreal.OtherworldShotLibrary`): `ShotTrace`, the pellet's one trace node (`Scripts/uebp/nodes/shot.py`), the rewind a shooter gets, and what the history did, for the probes |
| `Otherworld/Public/OtherworldInventoryRecord.h`, `Private/….cpp` | What a player carries, as one record (A3a, A3b; `Scripts/net/CLAUDE.md`, "The inventory"): `FOtherworldInventoryRecord` (a row per item, a class per worn slot; its own `NetSerialize`, so it travels whole), `UOtherworldInventoryRecordComponent` (holds it on the character: `COND_OwnerOnly`, push-based, one RepNotify; `HandClass`, `HandLit`, `HandHot` `COND_SkipOwner`; reads the weapon component's Blueprint arrays and each item's variables by name, through reflection, and on a client raises that component's `ViewDirty`, by name, when a record or a hand arrives), `UOtherworldInventoryRecords` (a world subsystem: each marked record written once, after the actors ticked) and `UOtherworldRecordSave` (a `USaveGame` with one byte array: the record as a save holds it) |
| `Otherworld/Private/OtherworldInventoryBytes.cpp` | The record's saved form: `FOtherworldInventoryRecord::ToBytes` and `FromBytes`, a version first, classes by path; the layout is the file's first comment |
| `Otherworld/Private/OtherworldInventoryLibrary.cpp` | `UOtherworldInventoryLibrary` (Python: `unreal.OtherworldInventoryLibrary`; declared in the record's header): `MarkInventoryDirty` and `MarkCarriedItemDirty` for the graphs (`Scripts/uebp/nodes/inventory.py`, placed by `Scripts/combat/dirty.py`), the view's reads of the record (`InventoryRow`, `WornRow`, `HandRow`, for `Scripts/combat/weapon_component/view.py`), the save's (`InventoryRecordOf`, `InventoryRecordToBytes`, `InventoryRecordFromBytes`), and the probes' reads and the audit's switch |
| `Otherworld/Public/OtherworldRpcGuard.h`, `Private/….cpp` | `UOtherworldRpcGuard` (A5; `Scripts/net/CLAUDE.md`, "Every Server event asks the guard first"): a component on the player with the two checks a Blueprint Server event has no `_Validate` for. `Allow(Name)`, a token bucket per event name per connection (the state is keyed by the `UNetConnection`, so it outlives a character), which logs `RPC-REFUSED` and past `KickRefusals` in `KickSeconds` closes the connection (`ENetCloseResult::Extended`, `ClosedByRpcGuard`); and `AimAllowed(AimPoint)`, the cone along `GetBaseAimRotation` a shot's point must lie in. Both pass uncounted unless the owner's controller is a remote player's. Its numbers are `EditAnywhere`, written by `combat/install.py` from `Scripts/net/guard_consts.py`; `Counted`, `Refused`, `AimRefused` and `bKicked` (Python: `kicked`) are for the probes |
| `OtherworldEditor/OtherworldEditor.Build.cs` | the editor module's dependencies (adds `UnrealEd`, `BlueprintGraph`); only the Editor target lists it, so no game or server build carries it |
| `Otherworld/Public/OtherworldLoadLibrary.h`, `Private/….cpp` | `UOtherworldLoadLibrary` (Python: `unreal.OtherworldLoadLibrary`): what the load test reads off a server or a client (A1, `Scripts/probes/probe_net_load.py`): each connection's bytes and packets in and out, open actor channels and lag (`FOtherworldConnectionStats`, read with `get_editor_property`), the frame and world-tick times sampled between `StartFrameTiming` and `StopFrameTiming`, and the hit history's characters and samples; and `SpawnActorAt`, a spawn for a probe that needs a thing the level lacks (Python has none in a game; `probe_gas_traversal.py`'s block) |
| `Otherworld/Public/OtherworldReplicationGraph.h`, `Private/….cpp` | `UOtherworldReplicationGraph` (A2, `Scripts/net/CLAUDE.md` "Relevancy, update rates and dormancy"): the server's replication driver, named for the `IpNetDriver` in `Config/DefaultEngine.ini`. A grid-spatialisation node for everything with a place in the world, an always-relevant list for `bAlwaysRelevant` actors, and `UOtherworldReplicationGraphNode_ForConnection` per connection (the engine's viewer and view target, plus the viewer's PlayerState). Each class's cull distance and period are read off its CDO, which the builders write from `Scripts/net/relevancy_consts.py`; `CellSizeCm` is its one config value |
| `Otherworld/Public/OtherworldNetLibrary.h`, `Private/….cpp` | `UOtherworldNetLibrary` (Python: `unreal.OtherworldNetLibrary`): `IsLevelActor`, whether an actor was placed in the level (`AActor::IsNetStartupActor`, not Blueprint-callable), which the take asks before destroying one (`Scripts/uebp/nodes/level.py`); and `SendServerEvent(Target, Event, Arguments)` for the probes (A5): a Blueprint Server event sent from a client as the VM sends one (`CallRemoteFunction`), each parameter from its text, which Python's `call_method` cannot do |
| `OtherworldEditor/Public/OtherworldBlueprintNetLibrary.h`, `Private/….cpp` | `UOtherworldBlueprintNetLibrary` (Python: `unreal.OtherworldBlueprintNetLibrary`): a custom event's net flags and parameters, a variable's replication and OnRep graph, and the same read back off a compiled class. Wrapped by `Scripts/uebp/net.py`; checked by `Scripts/dev/check_net_authoring.py` |

They began as the packaging step's generated files in `Intermediate/Source`; both modules
are listed under `Modules` in `Otherworld.uproject` (`OtherworldEditor` as type `Editor`).

## Compile

```bash
"/Users/Shared/Epic Games/UE_5.8/Engine/Build/BatchFiles/Mac/Build.sh" \
    OtherworldEditor Mac Development \
    -project="/Users/alexeysukhov/Documents/Unreal Projects/Otherworld/Otherworld.uproject" -waitmutex
```

- **One command:** `python3 Scripts/dev/uepy.py --compile` closes this project's editors, waits for them,
  runs the line above, rewrites `UnrealEditor.modules` if it names an older dylib, boots the serve
  editor (`$UEPY_SERVE`) and proves `unreal.OtherworldMovementLibrary` exists (`uepylib/compile.py`).
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
  `SetAimWalk`, `RequestSlide`, on the machine that reads the keys) and read what it made of that
  (`IsSprinting`, `GetStamina`, ...). A graph never writes `MaxWalkSpeed`, a crouched height or
  the stamina: a value written from a Blueprint exists on one machine, and the server pulls
  the client back to its own (the verifiers fail on such a write).
- **The slide is the fourth state** (G5; `FLAG_Custom_3`, the last free flag;
  `combat/gas_moves_tuning.py`). Its want is one press, not a held key: `RequestSlide`
  raises `bWantsSlide`, the next move starts a slide or does not, and `UpdateSlide`
  clears it (the server reads each move's own flag). It starts only from a move that was
  sprinting, on the ground, at `SlideMinStartSpeed` or more, and only with
  `bSlideEnabled` (off by default: the builder turns it on). While it lasts the velocity
  is written each step, along `SlideDirection` at `SlideSpeed()`, and the sprint is off.
  Its clock, speed and way are saved with each move (restored by `CombineWith`) and
  carried by a correction; another player's copy reads `AOtherworldCharacter::bSliding`
  (replicated to simulated copies, as `bProne`). `probes/probe_net_slide.py`: no
  correction through a slide at 200 ms.
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
- **Bodies by index:** a pose holds `Mesh->Bodies` by position, in the mesh's own frame
  (its component transform without the scale), so a pose kept from a frame the mesh was
  posed on still places the bodies where a later frame's capsule carried them. A mesh
  whose body count changes (collision toggled) starts its poses again and is judged by
  its capsule alone until it has one.
- **Which frames posed the mesh** (A4): `AnimUpdateRateParams->ShouldSkipEvaluation()`,
  read after the actors ticked. A skipped frame writes a frame (the capsule) and no pose.
  A corpse writes no pose at all: its capsule stops no pellet.
- **The engine's not-rendered rate is one integer, `BaseNonRenderedUpdateRate`,** frames
  between two evaluations of a mesh nothing renders (`AnimUpdateRateSetParams`), with no
  interpolation of the skipped frames there; a player-controlled body still updates its
  anim instance every frame and evaluates at that rate. `UOtherworldServerPose` writes it
  per body from the server's smoothed frame time, so a rate in Hz holds as the server
  slows.
- **For the probes:** `HitBoxThen(Character, Bone, SecondsAgo)` (where a rewound shot
  would find that bone's box), `HitHistoryPoses`, `LastShotLine`, and on the pose library
  `ServerPoseEveryFrames` and `TickingSkinnedMeshes`.
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
  - **With another editor of this project left open** (a person's, parked on a dialog),
    every build writes the next numbered copy and `UnrealEditor.modules` is updated only
    some of the time (seen 2026-10-08: twice not, once so). After each build compare the
    file with `ls -t Binaries/Mac/libUnrealEditor-Otherworld-*.dylib | head -1` and write
    the newest name into it by hand; the open editor keeps the copy it loaded.
- **Push Model needs four things, and a fifth to be safe** (A3a): the target compiled
  with it (`bWithPushModel`: an editor target has it, the Client and Server targets set
  it, the Game target is left at the engine's default, off), the property declared push-based
  (`DOREPLIFETIME_WITH_PARAMS_FAST`, `bIsPushBased`), `MARK_PROPERTY_DIRTY_FROM_NAME` at
  every write, and `net.IsPushModelEnabled=1` (`Config/DefaultEngine.ini`). The fifth:
  `Net.MakeBpPropertiesPushModel=0` beside it, or every Blueprint variable turns
  push-based and one written by reflection or from Python is never sent, with nothing
  logged (that emptied every client's inventory view here until it was set). Without the
  first or the fourth, a push-based property is still sent, by comparison.
- **A Blueprint variable read or written from C++ is found by name**
  (`FindFProperty<FArrayProperty>(Class, Name)`, `FScriptArrayHelper`): the record
  component's names are properties of its template, written by `combat/install.py` from
  the builders' own constants and checked by `combat/verify/record.py`.
- **A class out of C++ into a Blueprint-typed pin** (A3b): the record holds
  `TSubclassOf<AActor>`, and a graph may not wire that into a `BP_WeaponItem` class pin.
  The read takes the wanted class as an input and names it in its metadata
  (`DeterminesOutputType = "Kind", DynamicOutputParam = "Class"`): the node's `Class`
  output takes the type of the `Kind` pin's literal, which `_set` writes from Python as
  the class path. No cast node.
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
- **`GetFunctionCallspace` says a Blueprint Server event called from C++ on a client
  would run locally** (seen in `SendServerEvent`, A5), so it cannot be the test of
  "would this travel". Ask whether the owner lacks authority, call `CallRemoteFunction`
  and take its bool.
- **`FNetCloseResult` is `UE::Net::FNetCloseResult`** (`Net/Core/Connection/NetCloseResult.h`);
  a custom reason is `ENetCloseResult::Extended` with the reason as its error context.
  The server logs it; the client is told only `ConnectionLost`.
- **Editor-only code goes in `OtherworldEditor`, never the runtime module:** `UnrealEd` and
  `BlueprintGraph` do not exist in a game or server build.
- **New code keeps both modes:** single player is the standalone net mode of the same code
  (`serversupportsysdesign.md` 4.8). No `#if`-ed multiplayer copy of a system.
