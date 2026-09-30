"""npc -- the forest wanderers' Blueprints, as Unreal Python.

Entry point: Scripts/build_npc_blueprints.py (ensure_npc_variants() builds the
parent pair, then one child Blueprint and one AI controller per creature).
Every number these graphs bake in lives in forest_generator/npc_placement.py
(chase, melee) and forest_generator/npc_agro.py (senses, patrol), neither of
which imports `unreal`, so the offline generator reads the same values. The
noise record the senses listen to, and the per-gun ShotVolume, are combat's
(combat/noise.py, combat/tuning.py); this package reads their names.

DATA (constants -- no Blueprint authoring)
  paths        /Game paths, the controller's variable names, mesh offsets
  nodes        FN_* function paths, NODE_* palette names

SHARED AUTHORING HELPERS
  graph        create/load a Blueprint, pins, connect, _set, _resolve

THE CONTROLLER'S STEPS (one fragment per concern)
  sound        play one of several sounds (voice, melee impact)
  corpse       the corpse state: a Dead pawn stops the behaviour tree for good
  stats        this creature's health and flinch clips, once; voice on a timer
  melee        range + cooldown check, swing, damage, hit direction
  block        the player's guard: blocked damage and its stamina cost
  combat_trace the [COMBAT-TRACE] line a landed swing logs, when enabled
  patrol       once-per-life setup (centre, run speed); stroll to a point
  senses       hurt, sight (cone + line of sight), touch, sound
  chase        the move order at the player (pathfinding or straight line)
  agro         the notice and patrol steps: player present, one per sense, stroll
  steps        every BT_<Step> custom event, built from the fragments above
  controller   BP_ForestWandererAI: on possession, run its Behavior Tree

THE BEHAVIOUR TREE
  step_task    BTT_<controller>_Step: calls the step event its node names
  tree         BB_ForestWanderer and BT_<controller>, as the runtime tree

CHECKS (Scripts/verify_npc_blueprints.py)
  verify       patrol, agro, corpse and guard, per controller
  verify_tree  the Blackboard, each tree's priorities, the step events

THE BODY
  character    BP_ForestWanderer and one child Blueprint per creature

Dependency direction: paths/nodes -> graph -> fragments -> steps ->
step_task/tree -> controller -> character -> entry point. No module imports
the entry point. The only combat imports are its data modules (game_state,
paths, tuning).
"""
