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
  net         a network run (--net): a dedicated server and N clients, started and killed
  net_plan    that run's processes: names, command lines, environments, argument checks
  net_report  that run's one report: joins and errors per process, every process's probes
  net_memory  that run's memory: each process's peak footprint and resident size, sampled
  detach      detached --game/--net runs: --detach, --wait, --status
  editors     finding and closing the project's running editors

The modules that do not start processes (summary, targets, net_plan,
net_report, and the parsing halves of net_memory, game, cold and editors) are unit-tested
in Scripts/dev/tests.
"""
