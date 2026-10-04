# Scripts/server/gcp — the GCP build VM

Shell scripts that create the Linux build machine on GCP and build Unreal Engine from
source on it. They cover task 5 of `serversupportsysdesign.md`; the content sync (task 6)
and the server package (task 7) are not written yet and belong here when they are.

These run on the Mac with `gcloud`, not inside the editor: `uepy.py` is not involved.

## From nothing to a built engine

```
Scripts/server/gcp/vm_create.sh      # create the VM, install build tools, stop it
Scripts/server/gcp/engine_clone.sh   # start it, clone UE at the clients' tag, stamp the version
Scripts/server/gcp/engine_build.sh   # build detached; the VM powers itself off at the end
Scripts/server/gcp/vm.sh status      # state, and the build's progress while it runs
```

`vm.sh start | stop | ssh | status` is the day-to-day control.

## Modules

| File | Runs on | Does |
|---|---|---|
| `config.sh` | Mac (sourced) | every name and size: project, zone, machine, disk, engine tag and changelist |
| `vm_create.sh` | Mac | creates the VM; does nothing if it exists |
| `remote/vm_startup.sh` | VM, as root, at boot | one-time package install and `/opt/otherworld/{engine,project,out}` |
| `engine_clone.sh` | Mac | shallow clone of the engine tag over a forwarded SSH agent; writes `Build.version` |
| `engine_build.sh` | Mac | copies `remote/build_engine.sh` over and starts it in tmux session `build` |
| `remote/build_engine.sh` | VM | `Setup.sh`, project files, ShaderCompileWorker, UnrealPak, UnrealEditor; then shutdown |
| `vm.sh` | Mac | start, stop, ssh, status |

## Rules

- **The VM is stopped unless it is building.** Running, it bills by the hour; stopped, only
  its disk bills. `remote/build_engine.sh` shuts the VM down itself, pass or fail.
  `NO_SHUTDOWN=1 engine_build.sh` keeps it up.
- **No credential lives on the VM.** The engine clone forwards the Mac's SSH agent
  (`ssh -A`); the VM has no service account. Keep it that way: a secret on a build box in
  the same GCP project as the live service is the risk to avoid.
- **The engine version must match the clients'.** `OW_ENGINE_TAG`, `OW_ENGINE_CHANGELIST`
  and `OW_ENGINE_BRANCH` in `config.sh` mirror the installed engine's
  `Engine/Build/Build.version`. A source checkout stamps itself changelist 0, so
  `engine_clone.sh` rewrites it. Update all three together when the engine is upgraded;
  changing `Build.version` after a build recompiles most of the engine.
- **Never delete the VM or its disk from a script.** The built engine is hours of compute.
  Deleting is done by hand, by the owner.
- **Spot preemption** stops the VM mid-build. Rerun `engine_build.sh`; the build resumes.
- **The build status is on the VM's disk**, so `vm.sh status` can only show it while the VM
  runs. After a build has shut the VM down, `vm.sh start`, `vm.sh status`, `vm.sh stop`.

## Facts measured here

- Quota: `CPUS_ALL_REGIONS` is 32 in `play-history-service`, 2 in use, so 30 vCPUs is the
  most one VM can have without a quota increase.
- The shallow clone plus `Setup.sh` dependencies is about 31 GB of download; the disk held
  143 GB a fifth of the way through the editor build.
