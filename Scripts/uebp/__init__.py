"""uebp -- authoring Blueprints from Python, shared by every builder package.

  graph.py   node/pin/connect/set, out/then, variable declaration and CDO
             defaults, component (subobject) helpers, events, the tick group
  g.py       _G: the node shapes a long fragment repeats (get, put, call,
             branch), each made and kept for the comment box
  layout.py  arrange(ed): lays a graph out before the compile, so no builder
             carries coordinates
  vars.py    Var (a member variable: its name, pin type and default), the
             type specs, declare(ed, TABLE) and defaults(TABLE)
  net.py     networked Blueprints: Server / Client / Multicast custom events,
             Replicated and RepNotify variables, actors and components that
             replicate (through Source/OtherworldEditor; CLAUDE.md is the guide)
  props.py   engine properties and components read through a variable node
  pose_share.py  an anim graph's pose that feeds two inputs: share(ed) puts a
             cached pose there (a pose linked twice is updated twice a frame
             and plays everything under it at double speed), unshare(ed)
             takes it back out for the builders, fed(pin) reads through it
  nodes/     the one catalog of node paths (FN_*, NODE_*, MACRO_*), a module
             per engine library; its own __init__ maps them
"""
