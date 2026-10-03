"""uebp -- authoring Blueprints from Python, shared by every builder package.

  graph.py   node/pin/connect/set, out/then, variable declaration and CDO
             defaults, component (subobject) helpers, events, the tick group
  g.py       _G: the node shapes a long fragment repeats (get, put, call,
             branch), each made and kept for the comment box
  layout.py  arrange(ed): lays a graph out before the compile, so no builder
             carries coordinates
  vars.py    Var (a member variable: its name, pin type and default), the
             type specs, declare(ed, TABLE) and defaults(TABLE)
  props.py   engine properties and components read through a variable node
  nodes/     the one catalog of node paths (FN_*, NODE_*, MACRO_*), a module
             per engine library; its own __init__ maps them
"""
