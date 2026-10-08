# dev-team queue: multiplayer, with single player kept working
Run: `Scripts/dev/dev-team -t Scripts/dev/plans/multiplayer_tasks.md`
Phases 0-4 (M1-M26) have moved to `Scripts/dev/tasks.md`; these are phases 5-8. Each task
assumes the ones above it are done.

Every task: read `serversupportsysdesign.md` sections 4.1, 4.2 and 4.8 first.

**The standing requirement, for every task in this file:** single player and multiplayer are
both shipped modes of one game, chosen from the title menu ("Single Player" and
"Multiplayer", task M6). Neither is a fork, a test mode or a fallback of the other.
  - Single player is the engine's standalone net mode and runs the same graphs as the server.
    Write each system once, server-authoritative; never add an "if multiplayer" copy.
  - A task is not done until it works in both modes. Its single-player check is the verifier
    sweep and the existing `--game` probes, which must pass unchanged; its multiplayer check
    is the `--net` probe named in the task.
  - Behaviour may differ by mode only where the table in section 4.8 says so. A new
    difference is added to that table in the same commit, with its reason, or not made.
  - A feature added later to one mode works in the other unless that table excludes it.
  - If a task cannot keep single player working, stop and report rather than break it.

Everything is local (the installed editor binary with `-server`, `Lvl_Forest_200m`); no
task needs GCP. Do not run two sessions at once: the machine has 16 GB.

## Phase 0: foundations

## Phase 5: wanderers and the world

- [ ] M27. Wanderers in a world with several players. Senses, aggro, the wendigo's stalk,
      charge, torch ward and "ran too far" rule, zombie attacks and the "Drawn" state each
      choose and keep a target among all living players, switch when the target dies or
      leaves, and never read player 0. All AI runs only on the server; clients get movement
      and animation by replication, and the roar and growl sounds by Multicast. Done when:
      the NPC verifier and probes pass and a 2-client probe has a wanderer aggro on the
      nearer client and switch when that client dies.
      Design goal: Monsters built to hunt one player must choose among many and stay coherent when
      a target dies or leaves, with all AI on the server.
      Big picture: this is task M27 of 36 in the multiplayer project, phase 5 of 0-8 (wanderers
      and the world). The project turns this single-player survival game into one that also runs
      as a PvP game on a dedicated server (32-64 players, teams or solo, characters that persist),
      with single player still shipping from the same code. Phases 0-7 are built and proved on
      this Mac; hosting on GCP comes after and is not part of any task here. This phase is done
      when the monsters and the world behave sensibly with many players spread over the map. The
      strategy is `serversupportsysdesign.md`: section 1 the target, 4.1 authority, 4.2 where
      state lives, 4.8 the two modes, 7 the whole task list; read it before designing, and build
      for the later phases rather than for this task alone. The tasks before this one are done or
      in the same queue; this run's progress file and the git log say what they built. Do not do
      later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
      effort: high
- [ ] M28. Noise for several players. The GameMode's single last-noise record becomes a short
      list of recent noises (place, loudness, time, who made it), written only on the
      server and queried by the senses. Done when: two clients firing far apart each draw
      the wanderers near them.
      Design goal: Sound-driven AI must work when several players make noise in different places
      at once.
      Big picture: this is task M28 of 36 in the multiplayer project, phase 5 of 0-8 (wanderers
      and the world). The project turns this single-player survival game into one that also runs
      as a PvP game on a dedicated server (32-64 players, teams or solo, characters that persist),
      with single player still shipping from the same code. Phases 0-7 are built and proved on
      this Mac; hosting on GCP comes after and is not part of any task here. This phase is done
      when the monsters and the world behave sensibly with many players spread over the map. The
      strategy is `serversupportsysdesign.md`: section 1 the target, 4.1 authority, 4.2 where
      state lives, 4.8 the two modes, 7 the whole task list; read it before designing, and build
      for the later phases rather than for this task alone. The tasks before this one are done or
      in the same queue; this run's progress file and the git log say what they built. Do not do
      later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
- [ ] M29. Wanderer population by mode. Standalone keeps the level's fixed count and the
      10-second respawn. On a server the count is a budget: wanderers spawn out of sight
      near players and are removed when no player is within a configurable range, with a
      cap per player and for the server. The settings join the monster tuning table. Done
      when: single-player spawn probes are unchanged and a `--net` probe shows the count
      following two clients standing far apart.
      Design goal: A fixed monster count cannot serve both one player and sixty-four. Make
      population follow the players on a server and leave single player as designed.
      Big picture: this is task M29 of 36 in the multiplayer project, phase 5 of 0-8 (wanderers
      and the world). The project turns this single-player survival game into one that also runs
      as a PvP game on a dedicated server (32-64 players, teams or solo, characters that persist),
      with single player still shipping from the same code. Phases 0-7 are built and proved on
      this Mac; hosting on GCP comes after and is not part of any task here. This phase is done
      when the monsters and the world behave sensibly with many players spread over the map. The
      strategy is `serversupportsysdesign.md`: section 1 the target, 4.1 authority, 4.2 where
      state lives, 4.8 the two modes, 7 the whole task list; read it before designing, and build
      for the later phases rather than for this task alone. The tasks before this one are done or
      in the same queue; this run's progress file and the git log say what they built. Do not do
      later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
- [ ] M30. One world clock. The time of day, the random start time, wind and the night cold
      are driven by the server and replicated through the GameState, so every client sees
      the same sun and moon. Done when: two clients report the same time of day within a
      second after a minute, and the day-night verifier passes.
      Design goal: Everyone on a server shares one sky, so the clock has a single owner.
      Big picture: this is task M30 of 36 in the multiplayer project, phase 5 of 0-8 (wanderers
      and the world). The project turns this single-player survival game into one that also runs
      as a PvP game on a dedicated server (32-64 players, teams or solo, characters that persist),
      with single player still shipping from the same code. Phases 0-7 are built and proved on
      this Mac; hosting on GCP comes after and is not part of any task here. This phase is done
      when the monsters and the world behave sensibly with many players spread over the map. The
      strategy is `serversupportsysdesign.md`: section 1 the target, 4.1 authority, 4.2 where
      state lives, 4.8 the two modes, 7 the whole task list; read it before designing, and build
      for the later phases rather than for this task alone. The tasks before this one are done or
      in the same queue; this run's progress file and the git log say what they built. Do not do
      later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
- [ ] M31. Things left in the world. (Reduced by A2, which gave every item and campfire a
      cull distance, dormancy and a late joiner who sees a placed item taken and a fire lit:
      `probe_net_late_join.py`.) What remains: corpses, stuck weapons and chopped trees are
      replicated to players who arrive later, and each thing left in the world has a cleanup
      rule on a server (a lifetime, and a cap on how many exist) so a long-running world does
      not fill up. Standalone keeps today's behaviour. Done when: client 2 joining after
      client 1 dropped an item, lodged a blade in a tree and killed a wanderer sees all three.
      Design goal: A server runs for days and players arrive at any time: what was left in the
      world must be there for latecomers, and must not pile up without limit.
      Big picture: this is task M31 of 36 in the multiplayer project, phase 5 of 0-8 (wanderers
      and the world). The project turns this single-player survival game into one that also runs
      as a PvP game on a dedicated server (32-64 players, teams or solo, characters that persist),
      with single player still shipping from the same code. Phases 0-7 are built and proved on
      this Mac; hosting on GCP comes after and is not part of any task here. This phase is done
      when the monsters and the world behave sensibly with many players spread over the map. The
      strategy is `serversupportsysdesign.md`: section 1 the target, 4.1 authority, 4.2 where
      state lives, 4.8 the two modes, 7 the whole task list; read it before designing, and build
      for the later phases rather than for this task alone. The tasks before this one are done or
      in the same queue; this run's progress file and the git log say what they built. Do not do
      later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
- [ ] M32. Dev settings and cheats by mode. Standalone keeps every dev tab and cheat as today.
      A client of a server can open the tabs but changes to gameplay tables (guns, monsters,
      player, world) are sent to the server and applied only when the server was started
      with a `-AllowDevTuning` switch; otherwise the rows are read-only and say why.
      Graphics and sound settings stay local in both modes. Done when: both cases are probed.
      Design goal: The tuning tools were built for a solo developer. Keep them for single player
      and stop them being a cheat menu on a shared server.
      Big picture: this is task M32 of 36 in the multiplayer project, phase 5 of 0-8 (wanderers
      and the world). The project turns this single-player survival game into one that also runs
      as a PvP game on a dedicated server (32-64 players, teams or solo, characters that persist),
      with single player still shipping from the same code. Phases 0-7 are built and proved on
      this Mac; hosting on GCP comes after and is not part of any task here. This phase is done
      when the monsters and the world behave sensibly with many players spread over the map. The
      strategy is `serversupportsysdesign.md`: section 1 the target, 4.1 authority, 4.2 where
      state lives, 4.8 the two modes, 7 the whole task list; read it before designing, and build
      for the later phases rather than for this task alone. The tasks before this one are done or
      in the same queue; this run's progress file and the git log say what they built. Do not do
      later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.

## Phase 6: teams

- [ ] M33. Teams. A team id on the PlayerState and a replicated roster on the GameState, with
      Server requests to create a team, invite a player, accept, leave and kick; a player on
      no team is solo. Friendly fire between teammates is off by default, set by a server
      setting. A team ends when its last member leaves (it does not survive a logout: the
      default until the design doc's open decision is settled). Done when: a 3-client probe
      forms a team of two, the pair cannot damage each other and both can damage the third.
      Design goal: Teams are a stated requirement of the target (teams or solo). Keep the model
      small: an id, a roster, and a few requests.
      Big picture: this is task M33 of 36 in the multiplayer project, phase 6 of 0-8 (teams). The
      project turns this single-player survival game into one that also runs as a PvP game on a
      dedicated server (32-64 players, teams or solo, characters that persist), with single player
      still shipping from the same code. Phases 0-7 are built and proved on this Mac; hosting on
      GCP comes after and is not part of any task here. This phase is done when players can form
      teams or run solo. The strategy is `serversupportsysdesign.md`: section 1 the target, 4.1
      authority, 4.2 where state lives, 4.8 the two modes, 7 the whole task list; read it before
      designing, and build for the later phases rather than for this task alone. The tasks before
      this one are done or in the same queue; this run's progress file and the git log say what
      they built. Do not do later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
      effort: high
- [ ] M34. Team UI. A team page in the M menu (create, invite from the player list, accept,
      leave), teammate name markers in the world and on-screen, and teammates' health in a
      small list on the HUD. Not shown in standalone. Done when: the menu verifiers pass and
      a `--net --windowed` capture shows the markers.
      Design goal: Make teams usable: players need to find, join and recognise teammates without
      leaving the game.
      Big picture: this is task M34 of 36 in the multiplayer project, phase 6 of 0-8 (teams). The
      project turns this single-player survival game into one that also runs as a PvP game on a
      dedicated server (32-64 players, teams or solo, characters that persist), with single player
      still shipping from the same code. Phases 0-7 are built and proved on this Mac; hosting on
      GCP comes after and is not part of any task here. This phase is done when players can form
      teams or run solo. The strategy is `serversupportsysdesign.md`: section 1 the target, 4.1
      authority, 4.2 where state lives, 4.8 the two modes, 7 the whole task list; read it before
      designing, and build for the later phases rather than for this task alone. The tasks before
      this one are done or in the same queue; this run's progress file and the git log say what
      they built. Do not do later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.

## Phase 7: the character persists

- [ ] M35. The character save by mode. Standalone keeps the local `OtherworldProfile` slot and
      "Save and Exit" exactly as today. On a server the client writes nothing: the server
      keeps one save per player id (for now the id the client connects with, behind one
      function so a verified account id can replace it later), holding what the profile
      holds plus worn garments and location. It saves on disconnect, every few minutes and
      on shutdown, and loads on join so the player returns where they logged out; a
      first-time player gets the starting inventory at a player start. Done when: a `--net`
      probe has a client pick up an item, disconnect and rejoin a restarted server at the
      same place with the item.
      Design goal: The character must outlive the session, and only the server can be trusted to
      keep it. The save is shaped so a verified account id can replace the placeholder id later.
      Big picture: this is task M35 of 36 in the multiplayer project, phase 7 of 0-8 (the
      character persists). The project turns this single-player survival game into one that also
      runs as a PvP game on a dedicated server (32-64 players, teams or solo, characters that
      persist), with single player still shipping from the same code. Phases 0-7 are built and
      proved on this Mac; hosting on GCP comes after and is not part of any task here. This phase
      is done when a player's character is kept by the server between sessions. The strategy is
      `serversupportsysdesign.md`: section 1 the target, 4.1 authority, 4.2 where state lives, 4.8
      the two modes, 7 the whole task list; read it before designing, and build for the later
      phases rather than for this task alone. The tasks before this one are done or in the same
      queue; this run's progress file and the git log say what they built. Do not do later tasks'
      work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
      effort: high

## Phase 8: close out

- [ ] M36. Both modes, end to end, as the shipped state. Write `probe_net_session.py`: two
      clients join through the "Multiplayer" page, loot, fight a wanderer, fight each other,
      one dies and respawns, one disconnects and rejoins. Write `probe_mode_switch.py`: one
      process plays single player, saves and exits to the title, joins a server, leaves it,
      and continues the single-player game with its profile intact and nothing carried
      between the two characters. Run the full verifier sweep and every `--game` probe for
      single player. Fix what fails. Go through the mode table in
      `serversupportsysdesign.md` 4.8 row by row and confirm each difference is implemented
      and probed in both modes, and that the builders hold no other mode branch (grep the
      IsStandalone / IsDedicatedServer uses and account for each in `Scripts/net/CLAUDE.md`).
      Then update `systemDesign.md` (architecture), the root `CLAUDE.md` "Current state" and
      hard rules (both modes are supported; a change is checked in both), and
      `serversupportsysdesign.md` (what is done, what was measured, what is left: the GCP
      phases) to match what was built.
      Design goal: Finish with evidence: both modes work, switching between them is safe, every
      mode difference is accounted for, and the documents describe the game as built.
      Big picture: this is task M36 of 36 in the multiplayer project, phase 8 of 0-8 (close out).
      The project turns this single-player survival game into one that also runs as a PvP game on
      a dedicated server (32-64 players, teams or solo, characters that persist), with single
      player still shipping from the same code. Phases 0-7 are built and proved on this Mac;
      hosting on GCP comes after and is not part of any task here. This phase is done when both
      modes are proven end to end and the documents match what was built. The strategy is
      `serversupportsysdesign.md`: section 1 the target, 4.1 authority, 4.2 where state lives, 4.8
      the two modes, 7 the whole task list; read it before designing, and build for the later
      phases rather than for this task alone. The tasks before this one are done or in the same
      queue; this run's progress file and the git log say what they built.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
      effort: high
