"""uebp -- authoring Blueprints from Python, shared by every builder package.

  graph.py   node/pin/connect/set, out/then, variable declaration and CDO
             defaults, component (subobject) helpers, events, the tick group
  g.py       _G: the node shapes a long fragment repeats (get, put, call,
             branch), each made and kept for the comment box
  layout.py  arrange(ed): lays a graph out before the compile, so no builder
             carries coordinates
  nodes.py   the engine paths graph.py itself needs
"""
