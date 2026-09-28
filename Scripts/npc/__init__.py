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

THE CONTROLLER'S HEARTBEAT (one fragment per concern)
  sound        play one of several sounds (voice, melee impact)
  stats        this creature's health and flinch clips, once; voice on a timer
  melee        range + cooldown check, swing, damage, hit direction
  patrol       once-per-life setup (centre, run speed); stroll to a point
  senses       hurt, sight (cone + line of sight), touch, sound
  agro         the patrol/agro switch: setup -> [Aggro?] -> senses -> chase
  controller   BP_ForestWandererAI: the loop that calls all of the above

CHECKS
  verify       patrol and agro, per controller (Scripts/verify_npc_blueprints.py)

THE BODY
  character    BP_ForestWanderer and one child Blueprint per creature

Dependency direction: paths/nodes -> graph -> fragments -> controller ->
character -> entry point. No module imports the entry point. The only combat
imports are its data modules (game_state, paths, tuning).
"""
