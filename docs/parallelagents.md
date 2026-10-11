# Parallel agents: running several dev-team tasks at once

**Status: not implemented.** dev-team runs one task at a time in one
checkout, and nothing described under "What would have to exist" has been
built. There is no seat command, no claimed queue, no machine-wide lock,
no merge step and no concurrency cap. Running two dev-team processes today,
in one checkout or in two worktrees, is unsupported and will go wrong in the
ways listed under "What dev-team assumes today".

This is an assessment made 11 Oct 2026, after the overnight run of 10/11 Oct
lost its night to idle sleep and the probes were made opt-in. It records
what is true of the tooling today, what the machine allows, and what would
have to exist before two dev-team seats run side by side.

## What already works in favour of it

- **A checkout is self-contained.** Every path dev-team uses is derived
  from where its own `Scripts/dev/dev-team` lives: the project root, the
  warm editor's inbox (`Saved/uepy/devteam`), the baseline cache, the probe
  record, the run logs and the task file. A git worktree's dev-team sees
  that worktree as its project and nothing else.
- **Editor closing is scoped to the `.uproject` path** on the process's
  command line (`uepylib/editors.py`), so a run in one worktree does not
  close another worktree's editor.
- **Worktrees share one `.git` and one LFS object store.** A new worktree
  is a checkout, not a download. Each has its own index lock and commits
  on its own branch. Three worktrees already exist under
  `../Otherworld-worktrees/` (content-lfs, fab-intake, mannequin-bind),
  all without Content or Binaries checked out.
- **The derived data cache is shared**, under
  `~/Library/Application Support/Epic/UnrealEngine/Common/DerivedDataCache`,
  so a second editor does not recompile the shaders the first one did.
- **Probes are opt-in**, so a seat's steady state is one headless editor,
  plus one cold editor for each gate sweep, not a server and two clients.

## What a seat costs

Measured on the development Mac (16 GB RAM, 10 cores, 51 GB free on disk)
on 11 Oct 2026.

| Resource | Per seat | On this machine | Ceiling |
|---|---|---|---|
| RAM | 4-6 GB for a headless editor; 13 GB for a net probe (server + 2 clients) | 16 GB | 2 seats, and no net probe while another editor is up |
| Disk | ~12 GB: Content 6.3 GB (LFS), Binaries 2.9 GB, Intermediate 1.8 GB | 51 GB free | 2-3 worktrees |
| CPU | a sweep or build uses several cores | 10 cores | 2 seats |

Almost nothing runs without an editor. A task in this project is a Python
builder that runs inside `UnrealEditor-Cmd` to write Blueprints, levels,
data tables and widgets, and the verifier gate reads the built assets the
same way. `-NoUI` is already the lightest form of that editor (no window,
no Slate, the full engine). Editor-free work is limited to dev tooling,
docs, server scripts, the unit tests, the C++ compile (Unreal Build Tool
alone), and the text of a builder before it is run. Every task in the
current queue builds or verifies content. `-nullrhi` might trim an editor
by skipping the GPU and most shader work, but some builders make materials
and widgets that may refuse to compile without a renderer; it needs a test
run before anyone relies on it, and would not bring an editor under 2-3 GB.

## What dev-team assumes today that breaks with two runs

- **One working tree, one branch.** The gate fingerprints the whole tree
  and sends a session back when the tree has uncommitted changes after its
  turn. A second agent's half-written files look like the first's leftovers
  and are swept into its commits. (Two runs in one checkout are out; this
  is why worktrees are the unit.)
- **No task claiming.** The task file is re-read after each task and the
  first unticked item runs. Two runs on the same file both take it.
- **Per-worktree "one at a time" rules.** `uepylib/detach.py` serializes
  detached runs within a checkout; `uepylib/server.py` boots one warm
  editor per inbox. Neither knows about another worktree, so two sweeps,
  or a sweep next to a net probe, would swap or crash an editor. A
  half-killed editor is what made warm boots hang in the overnight run.
- **The gate is per branch.** A task passes its gate on its own branch,
  not on main after the other task lands. Without a post-merge sweep, main
  can regress although every task passed.
- **Built assets do not merge.** Independent tasks still touch the same
  `.uasset` files. The rule has to be: merge the Python, rebuild the
  content the merged diff reaches, sweep the gate on the merged tree,
  then fast-forward main. Two tasks that edit the same builder script
  conflict as text and need a hand.
- **Binaries must match Source.** A task that edits C++ rebuilds in its
  own worktree. Copying main's Binaries only works while Source is
  unchanged.
- **Shared by every seat:** the five-hour session window (parallelism
  only pays if that is not the bottleneck), Fab asset requests at the
  terminal (one interactive run), the user's own editor if one is open on
  main, and the Mac's memory.

## What would have to exist (none of it built yet)

1. **A seat command.** `dev-team seat new <name>`: make a worktree and a
   branch, pull Content through LFS, copy or build Binaries, and run
   dev-team in it. `dev-team seat drop <name>` removes the worktree once
   its branch is merged.
2. **A shared queue with claims.** One task list; a claim file per task
   under a shared directory, taken atomically, so N runs pull from it.
   The task file's ticks move to the merge step.
3. **A machine-wide lock for heavy steps.** Sweeps, cold builds and probe
   launches take one lock across all worktrees, so at most one editor
   boots at a time and a net probe never overlaps another editor. This
   is what keeps two seats from being slower than one.
4. **A merge step.** Rebase the branch on main, rebuild the content the
   diff reaches, sweep the gate on the merged tree, fast-forward main.
   Serialized through the same lock.
5. **A concurrency cap.** Default 2 on this Mac; 1 whenever a task's probe
   set includes a net probe.

## Recommendation

Two seats on this Mac is the ceiling and the gain is modest, because the
heavy steps serialize anyway. Real parallelism comes from a second
machine: the GCP build VM as the second seat, each machine running an
ordinary single-seat dev-team on its own clone, with only the queue (2)
and the merge step (4) shared. That path needs neither the machine-wide
lock (3) nor the cap (5).

Until then, the cheaper win is serial runs with less wasted wall time per
task: the Mac held awake (`devteam/awake.py`), detached-only builds, no
orphaned editors on resume, and sessions told that Monitors never fire in
print mode.
