"""devteam -- the pieces of Scripts/dev/dev-team, one concern each.

dev-team itself is the thin CLI (argument parsing and the per-task loop):

  tasks       the task file: parsing items and their effort:/model: hints, ticking
  session     one headless ``claude -p`` session: prompt, command, env, live output
  gate        the verifier sweep run before and after each task, and the comparison
  accounting  tokens, cost and time; the Time:/Tokens: commit trailers
  fab         Fab assets: fab: hints and FAB-REQUIRED reports, asked of the user

Unit-tested in Scripts/dev/tests (everything but the process launching).
"""
