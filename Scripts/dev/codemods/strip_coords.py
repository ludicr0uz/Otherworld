"""strip_coords.py -- delete every node coordinate from the authoring code.

    python3 Scripts/dev/codemods/strip_coords.py            # dry run: the plan
    python3 Scripts/dev/codemods/strip_coords.py -v         # ...and every rewrite
    python3 Scripts/dev/codemods/strip_coords.py --apply [--base <git rev>]

A dry run rewrites a scratch copy of Scripts/ and leaves it behind to diff.

uebp.layout.arrange places the nodes, so a coordinate carries nothing. This
rewrites, to a fixpoint:

  _at(EXPR, X, Y)          -> EXPR
  _palette(ed, NAME, X, Y) -> _palette(ed, NAME)
  a parameter that was only ever used to compute coordinates: dropped from
      the signature and from every call site, resolved by name (through
      imports, nested defs and the helper classes' methods), never by position
  a local that was only ever a coordinate (``y = y0 + 300``): its assignment
  a loop variable that was only ever one (an ``enumerate`` index, a column of
      a literal table): the index, or the column from every row

A parameter or local is "only a coordinate" when it was read before the
rewrite and nothing reads it after: its every use sat inside a stripped
argument. What the tool cannot resolve it leaves and reports.
"""

import ast
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import source as S  # noqa: E402

SINKS = {("uebp.graph", "_at"): "unwrap", ("uebp.graph", "_palette"): (2, 3)}
PURE_CALLS = {"int", "float", "len", "min", "max", "abs", "round", "range"}


def conventions(module, receiver):
    """The class of a receiver that arrives as a parameter."""
    package = module.name.split(".")[0]
    if receiver == "g":
        if package == "npc":
            return _class(module, "npc.graph", "_Graph")
        return _class(module, "combat.weapon_component.common", "_G")
    if receiver == "k" and package == "npc":
        return _class(module, "npc.senses", "_Maker")
    if receiver == "steps" and package == "npc":
        return _class(module, "npc.steps", "_Steps")
    return None


def _class(module, name, cls):
    target = PROJECT.modules.get(name)
    return (target, cls) if target else None


def loads(fn):
    """Names read anywhere in a function, nested functions included. A name
    read only to compute its own next value (``x = x + 800``) is not read."""
    own = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            pairs = [(node.target, node.value)]
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
            if (isinstance(target, ast.Tuple) and isinstance(value, ast.Tuple)
                    and len(target.elts) == len(value.elts)):
                pairs = list(zip(target.elts, value.elts))
            else:
                pairs = [(target, value)]
        else:
            continue
        for target, value in pairs:
            if isinstance(target, ast.Name):
                own |= {id(n) for n in ast.walk(value)
                        if isinstance(n, ast.Name) and n.id == target.id}
    return {n.id for n in ast.walk(fn)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and id(n) not in own}


def params(fn):
    return [a.arg for a in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs]


def snapshot(project, base):
    """What each function read at git revision ``base``, before any rewrite:
    {(module, qualname): names}. From git, so a second run (after the leftovers
    are fixed by hand) still knows what was a coordinate."""
    out = {}
    repo = os.path.dirname(S.SCRIPTS)
    for module in project.modules.values():
        shown = subprocess.run(["git", "show", f"{base}:Scripts/{module.rel}"], cwd=repo,
                               capture_output=True, text=True)
        if shown.returncode:
            continue                                  # new since base
        old = S.Module.__new__(S.Module)
        old.functions = {}
        old._index(ast.parse(shown.stdout), "")
        for qualname, fn in old.functions.items():
            out[(module.name, qualname)] = loads(fn)
    return out


def droppable(project, before):
    """{(module name, qualname): [param names]} read before, unread now."""
    out = {}
    for module in project.modules.values():
        for qualname, fn in module.functions.items():
            was = before.get((module.name, qualname), set())
            now = loads(fn)
            is_method = isinstance(module.parent.get(fn), ast.ClassDef)
            gone = [p for p in params(fn)[1 if is_method else 0:]
                    if p in was and p not in now]
            if gone:
                out[(module.name, qualname)] = gone
    return out


def _def_edits(module, fn, names):
    after = module.offset(fn.lineno, fn.col_offset) + len("def ")
    _open, close, segs = S.segments(module, after)
    drop = set()
    for arg in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs:
        if arg.arg in names:
            drop.add(S.segment_of(module, segs, arg))
    return [(a, b, "") for a, b in S.removal(segs, close, drop)]


def _call_edits(module, call, fn, names, is_method, problems):
    """Drop the arguments that bind to ``names`` of ``fn``."""
    positional = [a.arg for a in fn.args.posonlyargs + fn.args.args][1 if is_method else 0:]
    _open, close, segs = S.segments(module, module.span(call.func)[1])
    drop = set()
    for i, arg in enumerate(call.args):
        if isinstance(arg, ast.Starred):
            if any(p in names for p in positional[i:]):
                problems.append(f"{module.rel}:{call.lineno}: starred call, "
                                f"cannot drop {names}")
            break
        if i < len(positional) and positional[i] in names:
            drop.add(S.segment_of(module, segs, arg))
    for keyword in call.keywords:
        if keyword.arg in names:
            drop.add(S.segment_of(module, segs, keyword.value))
    return [(a, b, "") for a, b in S.removal(segs, close, drop)]


def _sink_edits(module, call, kind, problems):
    _open, close, segs = S.segments(module, module.span(call.func)[1])
    start, end = module.span(call)
    if call.keywords or any(isinstance(a, ast.Starred) for a in call.args):
        problems.append(f"{module.rel}:{call.lineno}: unusual sink call")
        return []
    if kind == "unwrap":
        if len(segs) != 3:
            problems.append(f"{module.rel}:{call.lineno}: _at with {len(segs)} arguments")
            return []
        # Anything but a call or a name keeps the parentheses it leaned on.
        atom = isinstance(call.args[0], (ast.Call, ast.Name, ast.Attribute, ast.Subscript))
        return [(start, segs[0][0], "" if atom else "("),
                (segs[0][1], end, "" if atom else ")")]
    drop = {i for i in kind if i < len(segs)}
    return [(a, b, "") for a, b in S.removal(segs, close, drop)]


def _pure(expr):
    return not any(isinstance(c, ast.Call) and not (isinstance(c.func, ast.Name)
                                                    and c.func.id in PURE_CALLS)
                   for c in ast.walk(expr))


def _dead_pairs(module, node, was, now):
    """``a, x = f(), x0 + 900`` with x dead -> ``a = f()``: the dead targets and
    their values, cut out of both tuples."""
    targets, values = node.targets[0].elts, node.value.elts
    dead = [i for i, t in enumerate(targets)
            if isinstance(t, ast.Name) and t.id in was and t.id not in now
            and _pure(values[i])]
    if not dead:
        return []
    if len(dead) == len(targets):
        a, b = module.starts[node.lineno - 1], module.starts[node.end_lineno]
        owner = module.parent[node]
        alone = any(len(getattr(owner, f, [])) < 2 and node in getattr(owner, f, [])
                    for f in ("body", "orelse", "finalbody"))
        return [] if alone or module.src[a:module.span(node)[0]].strip() else [(a, b, "")]
    edits = []
    for elts in (targets, values):
        spans = [module.span(e) for e in elts]
        for i in dead:
            if i > 0:
                edits.append((spans[i - 1][1], spans[i][1], ""))
            else:
                edits.append((spans[0][0], spans[1][0], ""))
    return edits


def _dead_stores(module, fn, was):
    """Whole-line deletions of ``name = <pure>`` where the name was read before
    and is read by nothing now."""
    now, out = loads(fn), []
    for node in ast.walk(fn):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Tuple)
                and isinstance(node.value, ast.Tuple)
                and len(node.targets[0].elts) == len(node.value.elts)):
            out += _dead_pairs(module, node, was, now)
            continue
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
        elif isinstance(node, ast.AugAssign):
            target = node.target
        else:
            continue
        if not isinstance(target, ast.Name) or target.id not in was or target.id in now:
            continue
        if not _pure(node.value):
            continue
        owner = module.parent[node]
        siblings = [s for field in ("body", "orelse", "finalbody")
                    for s in getattr(owner, field, []) if node in getattr(owner, field, [])]
        if len(siblings) < 2:
            continue                    # would leave an empty block
        a = module.starts[node.lineno - 1]
        b = module.starts[node.end_lineno]
        if module.src[a:module.span(node)[0]].strip():
            continue                    # shares its line with something else
        out.append((a, b, ""))
    return out


def _dead_loop_vars(module, fn, was):
    """A loop variable that only ever placed nodes: ``for i, x in enumerate(e)``
    with ``i`` unread becomes ``for x in e``, and a dead column of a literal
    table (``for v, dy in ((A, 0), (B, 120))``) is cut from every row."""
    now, out = loads(fn), []

    def dead(node):
        return isinstance(node, ast.Name) and node.id in was and node.id not in now

    for loop in ast.walk(fn):
        if not isinstance(loop, ast.For) or not isinstance(loop.target, ast.Tuple):
            continue
        elts, source = loop.target.elts, loop.iter
        if (len(elts) == 2 and dead(elts[0]) and isinstance(source, ast.Call)
                and isinstance(source.func, ast.Name) and source.func.id == "enumerate"
                and len(source.args) == 1 and not source.keywords):
            kept = elts[1]
            inner = kept.elts if isinstance(kept, ast.Tuple) else [kept]
            a, b = module.span(inner[0])[0], module.span(inner[-1])[1]
            out.append((module.span(loop.target)[0], module.span(kept)[1] if not isinstance(
                kept, ast.Tuple) else _closing(module, b), module.src[a:b]))
            out.append((*module.span(source), module.text(source.args[0])))
            continue
        drop = [i for i, e in enumerate(elts) if dead(e)]
        rows = source.elts if isinstance(source, (ast.Tuple, ast.List)) else []
        if (not drop or len(drop) == len(elts) or not rows
                or not all(isinstance(r, ast.Tuple) and len(r.elts) == len(elts)
                           for r in rows)):
            continue
        spans = [module.span(e) for e in elts]
        for i in drop:
            out.append((spans[i - 1][1], spans[i][1], "") if i else
                       (spans[0][0], spans[1][0], ""))
        for row in rows:
            start = module.span(row)[0]
            open_at, close, segs = S.segments(module, start)
            if open_at != start:
                return []                   # a row written without parentheses
            keep = [seg for i, seg in enumerate(segs) if i not in drop]
            if len(keep) == 1:
                out.append((open_at, close + 1, module.src[keep[0][0]:keep[0][1]]))
            else:
                out += [(a, b, "") for a, b in S.removal(segs, close, set(drop))]
    return out


def _closing(module, after):
    """The offset just past the ``)`` that closes a parenthesised target."""
    rest = module.src[after:]
    return after + len(rest) - len(rest.lstrip()) + 1 if rest.lstrip().startswith(")") else after


def one_pass(project, before, write, verbose, problems):
    """Collect and apply one round of rewrites. Returns (edits, dropped)."""
    dropping = droppable(project, before)
    total = 0
    for module in project.modules.values():
        edits = []
        for (name, qualname), names in dropping.items():
            if name == module.name:
                edits += _def_edits(module, module.functions[qualname], names)
        for qualname, fn in module.functions.items():
            was = before.get((module.name, qualname), set())
            edits += _dead_stores(module, fn, was)
            edits += _dead_loop_vars(module, fn, was)
        for call in ast.walk(module.tree):
            if not isinstance(call, ast.Call):
                continue
            target = project.resolve(module, call, conventions)
            if not target:
                continue
            key = (target[0].name, target[1])
            if key in SINKS:
                edits += _sink_edits(module, call, SINKS[key], problems)
            if key in dropping:
                fn = target[0].functions[target[1]]
                is_method = isinstance(target[0].parent.get(fn), ast.ClassDef)
                edits += _call_edits(module, call, fn, dropping[key], is_method, problems)
        if verbose:
            for a, b, _new in sorted(set(edits)):
                line = module.src.count("\n", 0, a) + 1
                print(f"    {module.rel}:{line}: "
                      f"- {module.src[a:b]!r}")
        done, _skipped = S.apply(module, edits, write)
        total += done
    return total, dropping


def main(argv):
    global PROJECT
    write, verbose = "--apply" in argv, "-v" in argv
    root = S.SCRIPTS
    if not write:
        root = os.path.join(tempfile.mkdtemp(prefix="strip_coords_"), "Scripts")
        shutil.copytree(S.SCRIPTS, root, ignore=shutil.ignore_patterns(
            "__pycache__", "generated_levels", "*.txt", "*.obj"))
        print(f"[strip-coords] dry run on a copy: diff -ru {S.SCRIPTS} {root}")
    PROJECT = S.Project(root)
    base = argv[argv.index("--base") + 1] if "--base" in argv else "HEAD"
    before = snapshot(PROJECT, base)
    arity_before = set(S.arity_errors(PROJECT, conventions))
    problems, plan = [], {}
    for round_no in range(1, 40):
        total, dropping = one_pass(PROJECT, before, True, verbose, problems)
        for key, names in dropping.items():
            plan.setdefault(key, []).extend(names)
        print(f"[strip-coords] round {round_no}: {total} rewrites, "
              f"{sum(len(v) for v in dropping.values())} parameters dropped")
        if not total:
            break
        PROJECT.reload()
    print("[strip-coords] parameters dropped, by function:")
    for (module, qualname), names in sorted(plan.items()):
        print(f"    {module}.{qualname}: {', '.join(names)}")
    for line in sorted(set(problems)):
        print(f"[strip-coords] LEFT: {line}")
    fresh = sorted(set(S.arity_errors(PROJECT, conventions)) - arity_before)
    for line in fresh:
        print(f"[strip-coords] ARITY: {line}")
    return 1 if fresh else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
