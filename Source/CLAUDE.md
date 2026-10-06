# Source — the C++ module

Two modules and four targets. The runtime module, `Otherworld`, **holds no gameplay yet**: it
exists so that the multiplayer tasks that need C++ (predicted movement, lag compensation:
`serversupportsysdesign.md` 4.3) start from a module that already compiles. The editor-only
module, `OtherworldEditor`, holds what the Python builders need and Python cannot reach.
Everything else stays in the Python builders.

| file | owns |
|---|---|
| `Otherworld.Target.cs` | the game target (single player and the listen side; what packaging builds) |
| `OtherworldEditor.Target.cs` | the editor target: the only one day-to-day work compiles |
| `OtherworldClient.Target.cs`, `OtherworldServer.Target.cs` | the client and dedicated-server targets: **source engine only** (below) |
| `Otherworld/Otherworld.Build.cs` | the module's dependencies (`Core`, `CoreUObject`, `Engine`) |
| `Otherworld/Otherworld.cpp` | `IMPLEMENT_PRIMARY_GAME_MODULE`, nothing else |
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

## Traps

- **`Binaries/` is not committed, so a fresh clone must compile before the editor opens.**
  With the module missing or built for another engine build, the editor asks to rebuild, and a
  headless `UnrealEditor-Cmd` (every `uepy.py` run) cannot answer. Run the command above first.
- **Close this project's editors before compiling** (`uepy.py --close-editors`): the editor
  holds the dylib. Built while *any* `UnrealEditor` is running, even another project's, UBT
  writes a numbered copy (`libUnrealEditor-Otherworld-0001.dylib`) and points
  `UnrealEditor.modules` at it. That loads fine; it is only untidy.
- **The installed engine compiles the Editor and Game targets only.** `OtherworldServer` (and
  the Client) stop in a second with "Server targets are not currently supported from this
  engine distribution". They need UE built from source, which is the GCP build machine's job
  (`Scripts/server/gcp/CLAUDE.md`). Locally a dedicated server is the editor binary with
  `-server` (`serversupportsysdesign.md` 4.4).
- **Proving the module is loaded:** `lsof -p <editor pid> | grep Otherworld.*dylib`. A clean
  boot proves nothing by itself, as an empty module logs nothing.
- **A function for Python is a `BlueprintCallable` static of a `UBlueprintFunctionLibrary`.**
  Python names it in snake case, turns `bool` plus out-parameters into a return of `None` or
  the tuple of outs, and an `enum class` into `unreal.<Enum>.<UPPER_SNAKE>`. Change one and
  the running editor still has the old: close it, compile, and let `uepy.py` boot a new one.
- **Editor-only code goes in `OtherworldEditor`, never the runtime module:** `UnrealEd` and
  `BlueprintGraph` do not exist in a game or server build.
- **New code keeps both modes:** single player is the standalone net mode of the same code
  (`serversupportsysdesign.md` 4.8). No `#if`-ed multiplayer copy of a system.
