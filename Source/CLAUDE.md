# Source — the C++ module

Two modules and four targets. The runtime module, `Otherworld`, holds what multiplayer
needs and a Blueprint cannot do (`serversupportsysdesign.md` 4.3): so far the player's
predicted movement states (M12); lag compensation comes later. The editor-only
module, `OtherworldEditor`, holds what the Python builders need and Python cannot reach.
Everything else stays in the Python builders.

| file | owns |
|---|---|
| `Otherworld.Target.cs` | the game target (single player and the listen side; what packaging builds) |
| `OtherworldEditor.Target.cs` | the editor target: the only one day-to-day work compiles |
| `OtherworldClient.Target.cs`, `OtherworldServer.Target.cs` | the client and dedicated-server targets: **source engine only** (below) |
| `Otherworld/Otherworld.Build.cs` | the module's dependencies (`Core`, `CoreUObject`, `Engine`) |
| `Otherworld/Otherworld.cpp` | `IMPLEMENT_PRIMARY_GAME_MODULE`, nothing else |
| `Otherworld/Public/OtherworldCharacterMovement.h`, `Private/….cpp` | `UOtherworldCharacterMovement`: sprint, prone and the aim-walk as saved-move flags (`FLAG_Custom_0..2`), the speed of each state (`GetMaxSpeed`), the sprint's rules (the stamina latch, the forward cone) and the stamina, all stepped in `UpdateCharacterStateBeforeMovement` with the move's own delta time, so the owning client predicts them and the server makes the same ones. See "Predicted movement" below |
| `Otherworld/Public/OtherworldCharacter.h`, `Private/….cpp` | `AOtherworldCharacter`: a Character whose movement component is that class, and `bProne`, the one fact a simulated copy needs beside the engine's replicated crouch to stand as the server has it (M13, below). `BP_ThirdPersonCharacter` is reparented onto it by `Scripts/combat/player_move.py` |
| `Otherworld/Public/OtherworldMovementLibrary.h`, `Private/….cpp` | `UOtherworldMovementLibrary` (Python: `unreal.OtherworldMovementLibrary`): what the graphs and the probes say to the component and read off it, each a static taking the character's actor (`Scripts/uebp/nodes/move.py`) |
| `OtherworldEditor/OtherworldEditor.Build.cs` | the editor module's dependencies (adds `UnrealEd`, `BlueprintGraph`); only the Editor target lists it, so no game or server build carries it |
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
- **A function for Python is a `BlueprintCallable` static of a `UBlueprintFunctionLibrary`.**
  Python names it in snake case, turns `bool` plus out-parameters into a return of `None` or
  the tuple of outs, and an `enum class` into `unreal.<Enum>.<UPPER_SNAKE>`. Change one and
  the running editor still has the old: close it, compile, and let `uepy.py` boot a new one.
- **Editor-only code goes in `OtherworldEditor`, never the runtime module:** `UnrealEd` and
  `BlueprintGraph` do not exist in a game or server build.
- **New code keeps both modes:** single player is the standalone net mode of the same code
  (`serversupportsysdesign.md` 4.8). No `#if`-ed multiplayer copy of a system.
