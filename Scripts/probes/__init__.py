"""probes -- scripted checks that run inside a headless -game, on live objects.

A verifier reads the saved assets; a probe watches the game play them. Run one
with

    python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_consume_heal.py

which boots the level, runs every probe in order once the player exists, prints
each check, and kills the game as soon as the last probe finishes.

A probe file defines ``probe(p)``, a generator. ``p`` is a Probe (context.py);
``yield 0.3`` waits 0.3 s of game time, ``yield lambda: cond()`` waits until
cond is true, and ``p.check(label, ok, detail)`` records a result. A file may
also set ``WRITABLE = [(blueprint_path, variable), ...]``: the variables it
writes on live instances, which boot.py makes Instance Editable in memory for
this run only -- nothing on disk changes and no builder has to be re-run.

A network run (``uepy.py --net --clients 2 --probe ...``) runs the same file in
a dedicated server and in each client; net.py says how a probe names where it
runs and reads where it is, and probe_net_join.py is the model
(probe_net_see_each_other.py for one where a client waits on another);
Scripts/net/CLAUDE.md has the conventions and the traps.

  runner      the pure driver: advances probe generators on a clock, records checks
  context     Probe, the object a probe is handed: checks plus the game helpers
  boot        in-game entry (init_unreal.py calls it when UEPY_PROBES is set);
              switches on the inventory record's audit for every run, so a
              change to what a player carries that nothing marked fails it
              (INVENTORY-RECORD-STALE: Scripts/combat/dirty.py)
  kept_slots  the tuning tabs' save slots, set aside for a run and put back
  net         a network run: which process this is (Where), RUNS_ON, the shared board
  bots        the load test's bots (uepy.py --net --bots N): the server's stand-ins for
              players, spawned once its level is up and driven from the ticker
  load_stats  the load test's arithmetic: percentiles, rates per connection (pure)
  title       working the real title menu (uepy.py --title): its rows and mode
              pages taken, the session read, what the menu shows; shared by
              probe_title_single, probe_join_dead_address and probe_net_title
  probe_*     the probes themselves, one behaviour each
"""
