"""uepylib -- the pieces of Scripts/dev/uepy.py, one transport or concern each.

uepy.py is the thin CLI; everything it does lives here:

  paths       the engine, the .uproject, the Saved/uepy directories, log()
  targets     TargetResult: what running one script produced, whatever the transport
  summary     reads a script's output back: verifier counts, failures, tracebacks
  inbox       the file inbox a live editor (or a -game run) polls
  remote      the engine's own multicast remote execution (dead on this machine)
  cold        one UnrealEditor-Cmd boot for N scripts
  server      a warm headless editor of the caller's own ($UEPY_SERVE), booted once
  warm        running targets in that editor; a crash or hang is retried in a fresh one
  game        headless -game runs, with or without probes (Scripts/probes)
  editors     finding and closing the project's running editors

The modules that do not start processes (summary, targets, and the parsing
halves of game, cold and editors) are unit-tested in Scripts/dev/tests.
"""
