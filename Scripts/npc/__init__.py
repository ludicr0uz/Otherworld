"""npc -- the forest wanderers' Blueprints, as Unreal Python.

Entry point: Scripts/build_npc_blueprints.py (ensure_npc_variants() builds the
parent pair, then one child Blueprint and one AI controller per creature).
Every number these graphs bake in lives in forest_generator/npc_placement.py
(chase, melee), forest_generator/npc_agro.py (senses, patrol) and
forest_generator/npc_strafe.py (the step between swings) and
forest_generator/npc_stalk.py (the wendigo's hunt) and
forest_generator/npc_ward.py (fire holding it off), none of
which imports `unreal`, so the offline generator reads the same values.
The senses, patrol, speed, melee and health numbers, and those of the hunt
and the fire that a developer tunes, are then overlaid by
npc/monster_tuning.csv (monster_tuning.py) and baked as the controller's
Tune* variable defaults (tuned.py), not as pin literals. The
noise record the senses listen to, and the per-gun ShotVolume, are combat's
(combat/noise.py, combat/tuning.py); this package reads their names.

DATA (constants -- no Blueprint authoring)
  paths        /Game paths, the controller's variable names, mesh offsets
  nodes        FN_* function paths, NODE_* palette names
  monster_tuning  the tunable stats (MONSTER_STATS), monster_tuning.csv and
               monster_specs(): the CSV over npc_agro/npc_placement/
               npc_stalk/npc_ward's literals, per creature. Pure Python (the game's save uses it)

SHARED AUTHORING HELPERS
  graph        create/load a Blueprint, pins, connect, _set, _resolve
  tuned        the controller's Tune* variables: declare, read, CDO defaults.
               Every fragment below reads its numbers off them, which is
               what lets the M panel's MONSTER TUNING tab change a live one

THE CONTROLLER'S STEPS (one fragment per concern)
  sound        play one of several sounds (voice, melee impact)
  corpse       the corpse state: a Dead pawn stops the behaviour tree for good
               (Pulse), and the alive gate every other step starts at
  stats        this creature's health and flinch clips, once; voice on a timer
  melee        range + cooldown check, swing, damage, hit direction; then
               the creature's on-hit effects, rolled onto the player by
               survival/on_hit_graph.py (a wendigo's blow: bleeding, 33%)
  block        the player's guard: blocked damage and its stamina cost
  combat_trace the [COMBAT-TRACE] line a landed swing logs, when enabled
  patrol       once-per-life setup (centre, run speed); stroll to a point
  senses       hurt, sight (cone + line of sight), touch, sound
  chase        the move order at the player (pathfinding or straight line)
  strafe       between two swings: the head of the Chase step that sends it
               off and round the player instead, facing them
  stalk        a stalker's Stalk step (the wendigo): roar, then a leg at a
               time to the next tree (faster than its run, the way round
               turned about every few seconds) and a wait behind it (none
               in the open: it runs on; past 150 m straight at them), then
               fail for good, which is the charge (Chase takes over). Hurt
               by the player it is Enraged: the step fails from the start
  stalk_cover  ...the next tree: the sweeps for one, the spot behind its
               trunk, and what makes a spot cover (a trunk wide enough)
  ward         a fire-fearing creature's Ward step (the wendigo): while the
               player holds fire out at it, it circles instead of attacking,
               turning about every couple of seconds;
               past the fire the step fails; held off long enough, it runs
  ward_roar    ...its two roars at the fire: one part way through the hold,
               one at its end before it runs; a blow that lands on the
               player (melee's ``clears``) starts the hold over
  roar         the bellow itself: stop, face the player, the roar clip and a
               voice. The hunt's first pass and the fire's two both play it
  agro         the notice and patrol steps: player present, one per sense, stroll
  sight_cone   debug mode: the Tick that draws the sight (aggro) cone, as
               senses.py tests it, yellow on patrol and red on the hunt
  steps        every BT_<Step> custom event, built from the fragments above
  controller   BP_ForestWandererAI: on possession, run its Behavior Tree

THE BEHAVIOUR TREE
  step_task    BTT_<controller>_Step: calls the step event its node names
  tree         BB_ForestWanderer and BT_<controller>, as the runtime tree

CHECKS (Scripts/verify_npc_blueprints.py)
  verify       patrol, agro, corpse and guard, per controller
  verify_tree  the Blackboard, each tree's priorities, the step events
  verify_sight_cone  debug mode's cone: its gates and what it is drawn from
  verify_strafe  the step between two swings: when, where to, facing, speed
  verify_stalk   the wendigo's hunt: roar, turns, rage, catch-up, legs,
                 charge
  verify_stalk_cover  ...its next tree: sweeps, the trunk's width, the same
                 tree between the spot and the player, the open
  verify_ward    fire holding it off: the gate, the hold, the ring, the flight
  verify_ward_roar  ...its roars at the fire: the throw, the two roars, the
                 stand, and the blow that starts the hold over
  verify_on_hit  what a landed swing leaves on the player: the roll, the apply

THE BODY
  character    BP_ForestWanderer and one child Blueprint per creature (each
               afraid of fire tagged FearsFire, which a hot blade's blow reads)

Dependency direction: paths/nodes -> graph -> fragments -> steps ->
step_task/tree -> controller -> character -> entry point. No module imports
the entry point. The only combat imports are its data modules (game_state,
paths, tuning): the player's Blocking and FireWard are read by name.
"""
