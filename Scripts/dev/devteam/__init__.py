"""devteam -- the pieces of Scripts/dev/dev-team, one concern each.

dev-team itself is the thin CLI (argument parsing and the per-task loop):

  tasks       the task file: parsing items and their effort:/model: hints, ticking,
              and the queue when the file is read again after each task
  work        one task from start to finish: session, gate, write-up; pausing it
              and resuming it
  pause       the typed ``pause``: listening for it, the WIP branch, the session
              backup, the record ``dev-team resume`` reads; and the typed
              ``stop``, which ends the run once the task in hand is done
  session     one headless ``claude -p`` session: the rules as its system prompt, the
              task prompt, command, env, the compaction window, live output
  triage      one Haiku call before the run marks the small, obvious tasks low effort
  limits      the session limit: its latest reading, waited out when spent, and the
              session resumed
  gate        the verifier sweep run before and after each task, and the comparison
  accounting  tokens, cost and time; the Time:/Tokens: commit trailers
  fab         Fab assets: fab: hints and FAB-REQUIRED reports, asked of the user

Unit-tested in Scripts/dev/tests (everything but the process launching).

  baseline_cache  The before-sweep's result kept on disk, so it survives across dev-team runs
  probe_gate      The probe half of the gate: a named probe set (Scripts/probes/sets.py), run beside the verifier sweep

  final  The run's one probe sweep, when a run asks for probes (--probes): a
         probe set run after the last task, not after each
  nightly  A probe sweep on its own, apart from any run: ``dev-team probes run
           [SET]`` (FULL unless named), the nightly's command
  probe_record  The latest result of every probe (time, commit, pass/fail), kept
                across runs: the final sweep's "before" when the run has no
                baseline sweep of its own; ``dev-team probes`` lists it
  trace  Timestamped progress lines for the slow steps, and the run.log that
         keeps everything the terminal showed

  scope  What a change can move in the verifier sweep, and the tree snapshot that says what changed

  awake  Keep the Mac awake for the length of a run

  brief  What a session must still know once its context has been compacted: the
         prompts dev-team sent it and its own notes, kept in the run directory
         and printed back by a hook after each compaction

  tasklog  The task completion log, Saved/DevTeam/task_log.csv: a spreadsheet
           row per finished task (time by stage, tokens and cost by kind,
           effort, the session's summary, decisions and challenges), and the
           same breakdown as dev-team prints it
  timing   Where a task's time went: dev-team's own clock (sweeps, limit
           waits, sessions) and the transcript's (each tool call by what it
           ran), added up stage by stage
"""
