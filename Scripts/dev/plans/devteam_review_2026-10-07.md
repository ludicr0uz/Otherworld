# dev-team review, 2 to 7 October 2026

A review of the dev-team logs under `Saved/DevTeam/` for the last few days, with the
changes that would most accelerate the work without lowering its quality.

## Status of the last run (20261006-081136)

It is no longer running. It stopped at 01:38 on 7 October when the Claude five-hour
session limit hit 100%; task 9 (M23) failed after 12 seconds with "You've hit your
session limit, resets 11:50pm". Before that:

- M15 done and committed.
- M21 marked done, but its session never committed. It ended twice "waiting for the
  background probe run to finish". The verifier gate also sent it back once for two new
  weapon-check failures, which it fixed. Cost 1 h 10 min and $47.20, the most expensive
  task so far.
- M22 found M21's work staged, committed it as its own commit, then finished lag
  compensation and committed.
- Left in the queue: M23 to M26. `dev-team` from `Scripts/dev` picks up where it stopped.

## Where the time went

77 task sessions, about 23.5 hours of session wall time, roughly $360.

| | hours |
|---|---|
| model thinking and output | 10.7 |
| waiting on `--game` probe launches (256, about 86 s each) | 6.1 |
| waiting on `--net` runs (137) | 3.0 |
| warm verifier runs inside sessions (277) | 2.8 |
| builders, mostly the 100 to 110 s weapons build (87) | 1.7 |
| gate sweeps between tasks | 1.2 |

Fast mode was requested on 60 tasks but ran on 6. The other init events say
"off: extra_usage_disabled". Every "fast mode" label in progress.md is therefore wrong.

Other patterns from the transcripts and the commits' "Issues encountered" sections:

- 6 of 77 sessions ended without committing, each waiting on a background run.
- 34 of 77 sessions spent turns on failures that predated them; 12 used stash or checkout
  to prove it.
- 32 sessions ran shell loops launching single-player probes one game boot each.
- Every multiplayer session partial-staged its own hunks out of files holding the user's
  uncommitted work.
- Every task reworded 5 to 15 existing whole-graph count checks.

## Highest-leverage changes

1. **Catch sessions that end while waiting on a background command.** Six of 77 sessions
   ended with uncommitted, verified work because a headless session never gets the
   notification for a background Bash run, and the runner blocks `sleep`. M9 and M21 both
   landed only because the next session noticed. Cheap fix in the runner: if the session
   result mentions no commit and the tree has changes beyond what it started with, resume
   the session once with "your run finished, here is its output, commit". Also tell the
   prompt plainly: run probes in the foreground with a timeout, never `run_in_background`.

2. **Pace the run against the session limit instead of dying on it.** The runner already
   streams `rate_limit_event`. When utilisation passes about 95%, sleep until `resetsAt`
   and continue, and treat a "session limit" result as not-started rather than FAILED.
   Last night this cost six idle hours and one failed task. Separately, decide whether to
   turn extra usage on so fast mode actually engages, or drop the label.

3. **Fix or quarantine the standing failures once.** Six weapon pose checks have failed in
   every sweep for days, plus `probe_throw_stick`, `probe_throw_head`,
   `probe_bullet_impact`, `probe_carry`, `probe_hit_bodies` and a flaky `probe_headshot`.
   34 of 77 sessions spent turns on them, 12 did stash or checkout gymnastics to prove a
   failure predates them, M22 rebuilt the weapons four times for that, and M19's stash
   mishap came from it. One dedicated task to fix or mark them, then a known-failures file
   the prompt points at, with a rule: never rebuild HEAD to prove a baseline, report
   against the recorded one.

4. **Run the single-player probes as one suite in the gate, batched per boot.** 32
   sessions ran shell loops launching 10 to 20 probes one game boot each. `uepy.py`
   already takes several `--probe` per launch. A named probe set run once by the gate,
   before and after, gives sessions a probe baseline for free and would remove most of
   the 6 hours of probe boots.

5. **Start runs from a clean tree.** Every multiplayer session's "Issues encountered"
   lists partial-staging its own hunks out of `CLAUDE.md`, the design doc and the menu
   files that hold the user's uncommitted work. That is slow and risky: M14 unstaged 33
   staged files, and a wrong split loses work silently. Commit or stash WIP before a run,
   and have the runner refuse or warn when the tree is dirty beyond the task file.

6. **Make the weapons build incremental.** At 100 to 110 s per run it is the inner loop
   of every combat task. Rebuilding only the Blueprints a change touches would roughly
   halve iteration time on this phase. Larger piece of work, medium term.

7. **Stop writing whole-graph count checks.** Every task reworded 5 to 15 existing checks
   like "X is written exactly once" that broke on legitimate new nodes. Anchor new checks
   to a named node or use the fixture approach the M13 session introduced. Small per-task
   saving, and less pressure on sessions to loosen checks.

Items 1, 2 and 3 are a few hours of work in `devteam/` and one queued task, and together
they address the two outright failures and the biggest cost overrun of the week.
