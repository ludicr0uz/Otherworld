"""plumbing_pins.py -- the plumbing pins become helpers, and every module
imports its authoring helpers from uebp directly.

    python3 Scripts/dev/codemods/plumbing_pins.py            # dry run
    python3 Scripts/dev/codemods/plumbing_pins.py -v         # ...and every rewrite
    python3 Scripts/dev/codemods/plumbing_pins.py --apply

  _pin(N, "ReturnValue", is_input=False) -> out(N)
  _pin(N, <name>, is_input=False)        -> out(N, <name>)
  BEL.find_then_pin(N)                   -> then(N)
  BEL.find_else_pin(N)                   -> else_(N)
  from combat.graph / npc.graph import X -> from uebp.graph import X

``_connect(E, _pin(N, "execute"))`` is left as it is: the helper the plan
names for it, ``exec_in``, is what a hundred fragments call their own exec
parameter. A rewrite is skipped, and counted, inside a scope that binds
``out``, ``then`` or ``else_`` to something of its own.
"""

import ast
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import source as S  # noqa: E402

SHIMS = ("combat.graph", "npc.graph")
STAY = {"npc.graph": ("_Graph", "_mesh_object", "_log")}       # the NPC package's own
MOVED = {("combat.graph", "_log"): "combat.log"}
RENAMED = {("npc.graph", "_asset_sub"): "_assets"}
FINDERS = {"find_then_pin": "then", "find_else_pin": "else_"}


def _uebp_names(project):
    module = project.modules["uebp.graph"]
    names = {q for q in module.functions if "." not in q}
    for node in module.tree.body:
        if isinstance(node, ast.Assign):
            names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
    return names


def _binds(scope, name, top_level):
    """Does this scope bind ``name``: as a parameter, a store, or a def? For
    the module, only at its top level."""
    stack = list(ast.iter_child_nodes(scope))
    while stack:
        inner = stack.pop()
        if isinstance(inner, (ast.FunctionDef, ast.ClassDef, ast.Lambda)):
            if getattr(inner, "name", None) == name:
                return True
            if top_level:
                continue
        if isinstance(inner, ast.arg) and inner.arg == name:
            return True
        if (isinstance(inner, ast.Name) and inner.id == name
                and isinstance(inner.ctx, ast.Store)):
            return True
        stack.extend(ast.iter_child_nodes(inner))
    return False


def _bound(module, node, name):
    """Does a scope around ``node`` (or the module) bind ``name`` itself?"""
    scopes = [s for s in module.enclosing(node) if not isinstance(s, ast.ClassDef)]
    return (any(_binds(s, name, False) for s in scopes)
            or any(a.arg == name for s in scopes for a in s.args.args + s.args.kwonlyargs)
            or _binds(module.tree, name, True))


def shim_moves(project, module, uebp):
    """(moves, renames) that take this module's imports off the shims."""
    moves, renames = {}, {}
    for node in module.tree.body:
        if not isinstance(node, ast.ImportFrom) or node.module not in SHIMS:
            continue
        for a in node.names:
            key = (node.module, a.name)
            if key in MOVED:
                moves[key] = MOVED[key]
            elif key in RENAMED:
                moves[key], renames[key] = "uebp.graph", RENAMED[key]
            elif a.name in uebp and a.name not in STAY.get(node.module, ()):
                moves[key] = "uebp.graph"
    return moves, renames


def pin_edits(project, module, skipped):
    """(edits, helper names used) for the pin rewrites in one module."""
    edits, used = [], set()
    for call in ast.walk(module.tree):
        if not isinstance(call, ast.Call):
            continue
        func, helper, args = call.func, None, None
        if (isinstance(func, ast.Attribute) and func.attr in FINDERS
                and isinstance(func.value, ast.Name) and func.value.id == "BEL"
                and len(call.args) == 1 and not call.keywords):
            helper, args = FINDERS[func.attr], module.text(call.args[0])
        elif (isinstance(func, ast.Name) and func.id == "_pin" and len(call.args) == 2
              and len(call.keywords) == 1 and call.keywords[0].arg == "is_input"
              and isinstance(call.keywords[0].value, ast.Constant)
              and call.keywords[0].value.value is False):
            target = project.resolve(module, call)
            if not target or (target[0].name, target[1]) != ("uebp.graph", "_pin"):
                continue
            helper, name = "out", call.args[1]
            args = module.text(call.args[0])
            if not (isinstance(name, ast.Constant) and name.value == "ReturnValue"):
                args += ", " + module.text(name)
        if not helper:
            continue
        if _bound(module, call, helper):
            skipped[helper] = skipped.get(helper, 0) + 1
            continue
        a, b = module.span(call)
        edits.append((a, b, f"{helper}({args})"))
        used.add(helper)
    return edits, used


def _fix_imports(module, used, verbose):
    """After the rewrites: import the helpers used, drop what nothing uses."""
    src = module.src
    tree = ast.parse(src)
    loaded = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "uebp.graph":
            have = [a.name for a in node.names]
            keep = sorted({n for n in have if n in loaded or n not in ("_pin", "BEL")} | used)
            a, b = module.span(node)
            line_end = src.find("\n", b)
            comment = src[b:line_end] if "#" in src[b:line_end] else ""
            return [(a, b + len(comment), S.import_text("uebp.graph", keep, comment.rstrip()))]
    return []


def run(project, write, verbose):
    uebp = _uebp_names(project)
    skipped, count = {}, {"imports": 0, "pins": 0}
    for module in project.modules.values():
        if module.name in SHIMS or module.name.startswith("uebp."):
            continue
        moves, renames = shim_moves(project, module, uebp)
        edits = S.import_edits(module, moves, renames)
        for (_source, old), new in renames.items():
            edits += [(*module.span(n), new) for n in ast.walk(module.tree)
                      if isinstance(n, ast.Name) and n.id == old]
        if edits:
            count["imports"] += 1
            S.apply(module, edits, True)
            module.reload()
        if "uebp.graph" not in {v[0] for v in module.imports.values()}:
            continue                       # not an authoring module
        edits, used = pin_edits(project, module, skipped)
        if verbose:
            for a, b, new in sorted(edits):
                print(f"    {module.rel}:{module.src.count(chr(10), 0, a) + 1}: "
                      f"{module.src[a:b]} -> {new}")
        if edits:
            count["pins"] += S.apply(module, edits, True)[0]
            module.reload()
            S.apply(module, _fix_imports(module, used, verbose), True)
            module.reload()
    print(f"[plumbing-pins] imports re-homed in {count['imports']} modules; "
          f"{count['pins']} pin rewrites; skipped (name bound locally): {skipped}")


def main(argv):
    write, verbose = "--apply" in argv, "-v" in argv
    root = S.SCRIPTS
    if not write:
        root = os.path.join(tempfile.mkdtemp(prefix="plumbing_pins_"), "Scripts")
        shutil.copytree(S.SCRIPTS, root, ignore=shutil.ignore_patterns(
            "__pycache__", "generated_levels", "*.txt", "*.obj"))
        print(f"[plumbing-pins] dry run on a copy: diff -ru {S.SCRIPTS} {root}")
    run(S.Project(root), write, verbose)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
