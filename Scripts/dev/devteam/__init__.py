"""devteam -- the pieces of Scripts/dev/dev-team, one concern each.

dev-team itself is the thin CLI (argument parsing and the per-task loop):

  tasks       the task file: parsing items and their effort:/model: hints, ticking,
              and the queue when the file is read again after each task
  work        one task from start to finish: session, gate, write-up; pausing it
              and resuming it
  pause       the typed ``pause``: listening for it, the WIP branch, the session
              backup, the record ``dev-team resume`` reads
  session     one headless ``claude -p`` session: prompt, command, env, live output
  triage      one Haiku call before the run marks the small, obvious tasks low effort
  fast        fast mode for a task while the five-hour session limit is under half used
  limits      the session limit when it is spent: waited out, and the session resumed
  gate        the verifier sweep run before and after each task, and the comparison
  accounting  tokens, cost and time; the Time:/Tokens: commit trailers
  fab         Fab assets: fab: hints and FAB-REQUIRED reports, asked of the user

Unit-tested in Scripts/dev/tests (everything but the process launching).

  baseline_cache  The before-sweep's result kept on disk, so it survives across dev-team runs
  probe_gate      The probe half of the gate: a named probe set (Scripts/probes/sets.py), run beside the verifier sweep

  final  The run's one probe sweep: a probe set run after the last task, not after each
"""
