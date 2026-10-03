"""node_catalog.py -- gather every FN_*/NODE_*/MACRO_* path into uebp/nodes/.

    python3 Scripts/dev/codemods/node_catalog.py            # dry run, on a copy
    python3 Scripts/dev/codemods/node_catalog.py --apply

Each such module-level constant, wherever it is defined, moves to the catalog
module of its engine library (HOMES). One path keeps one name: of several
names for a path the most used wins, and a name that meant two paths keeps
the more used one (the other takes a synonym, or its entry in RENAMED).
Every definition is deleted, every use renamed, every import re-pointed.
"""

import ast
import collections
import os
import re
import shutil
import sys
import tempfile
import textwrap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import source as S  # noqa: E402

CATALOG = re.compile(r"^(FN|NODE|MACRO)_[A-Z_0-9]+$")
EXTRA = ("INF",)
WIDTH = 100
# A name that held two paths: the less used path's new name.
RENAMED = {
    "/Script/UMG.Widget.SetVisibility": "FN_SET_WIDGET_VISIBILITY",
}
HOMES = (       # (catalog module, what it holds, path prefixes)
    ("math", "KismetMathLibrary: arithmetic, comparison, vectors, rotators, and INF",
     ("/Script/Engine.KismetMathLibrary",)),
    ("array", "KismetArrayLibrary", ("/Script/Engine.KismetArrayLibrary",)),
    ("system", "the other static libraries: system, string, text, input, material, "
               "GameplayStatics, user settings",
     ("/Script/Engine.Kismet", "/Script/Engine.GameplayStatics",
      "/Script/Engine.GameUserSettings", "/Script/PythonScriptPlugin")),
    ("ai", "AIModule and the navigation system", ("/Script/AIModule", "/Script/NavigationSystem")),
    ("gas", "GameplayAbilities", ("/Script/GameplayAbilities",)),
    ("umg", "UMG widgets and their libraries", ("/Script/UMG",)),
    ("actor", "member functions of engine classes: actors, components, controllers, "
              "the HUD, anim instances", ("/Script/",)),
    ("palette", "palette nodes (events, casts, break/make) and the standard macros", ("",)),
)
PRIORITY = ("combat.nodes", "npc.nodes", "combat.weapon_component.slot_nodes")


def is_catalog(name):
    return bool(CATALOG.match(name)) or name in EXTRA


def definitions(module):
    """{name: (value, Assign node)} for the catalog constants a module defines,
    evaluated over the module's own string constants (``f"{KML}.Add"``)."""
    env, out = {}, {}
    for node in module.tree.body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            continue
        if any(isinstance(n, (ast.Call, ast.Attribute, ast.Subscript))
               for n in ast.walk(node.value)):
            continue
        try:
            value = eval(compile(ast.Expression(node.value), module.rel, "eval"), {}, dict(env))
        except Exception:
            continue
        name = node.targets[0].id
        env[name] = value
        if is_catalog(name) and isinstance(value, (str, float)):
            out[name] = (value, node)
    return out


def bindings(project, defs):
    """{module name: {name: value}}: what each catalog name means in each
    module, through its own definitions and its imports."""
    def meaning(module_name, name, depth=0):
        if name in defs.get(module_name, {}):
            return defs[module_name][name][0]
        module = project.modules.get(module_name)
        if module and name in module.imports and depth < 6:
            source, original = module.imports[name]
            return meaning(source, original, depth + 1)
        return None

    out = {}
    for module in project.modules.values():
        names = set(defs.get(module.name, {})) | {n for n in module.imports if is_catalog(n)}
        found = {n: meaning(module.name, n) for n in names}
        out[module.name] = {n: v for n, v in found.items() if v is not None}
    return out


def choose_names(project, defs, bound):
    """{value: final name}, and the renames worth reporting."""
    uses = collections.defaultdict(collections.Counter)
    for module in project.modules.values():
        mine = bound[module.name]
        for name, (value, _node) in defs.get(module.name, {}).items():
            uses[value][name] += 0
        for node in ast.walk(module.tree):
            if isinstance(node, ast.Name) and node.id in mine and isinstance(node.ctx, ast.Load):
                uses[mine[node.id]][node.id] += 1
    in_priority = {n for m in PRIORITY for n in defs.get(m, {})}
    final, taken, report = {}, set(RENAMED.values()), []
    for value, name in RENAMED.items():
        final[value] = name
    order = sorted(uses, key=lambda v: (-sum(uses[v].values()), str(v)))
    for value in order:
        if value in final:
            continue
        ranked = sorted(uses[value], key=lambda n: (-uses[value][n], n not in in_priority,
                                                    len(n), n))
        free = [n for n in ranked if n not in taken]
        if not free:
            raise SystemExit(f"no free name for {value!r} (wanted {ranked}): add it to RENAMED")
        final[value] = free[0]
        taken.add(free[0])
    for value in order:
        others = sorted(n for n in uses[value] if n != final[value])
        if others:
            report.append(f"{final[value]} = {value!r}  (was also {', '.join(others)})")
    return final, report


def home(value):
    if not isinstance(value, str):
        return "math"                     # INF
    return next(module for module, _what, prefixes in HOMES
                if any(value.startswith(p) for p in prefixes))


def _comments(module, node):
    """(leading comment lines, trailing comment) attached to a definition."""
    lines = module.src.split("\n")
    lead, i = [], node.lineno - 2
    while i >= 0 and lines[i].lstrip().startswith("#"):
        lead.insert(0, lines[i].strip())
        i -= 1
    last = lines[node.end_lineno - 1]
    code_end = node.end_col_offset
    trail = last[code_end:].strip() if "#" in last[code_end:] else ""
    return [l for l in lead if "───" not in l and "---" not in l], trail, i + 2


def _owner(value):
    if not isinstance(value, str):
        return "~"
    return value.rsplit(".", 1)[0] if value.startswith("/") else value.split("|")[0]


def catalog_sources(project, defs, final):
    """{catalog module: file text}."""
    order = [m for m in PRIORITY if m in defs] + sorted(m for m in defs if m not in PRIORITY)
    chosen = {}
    for module_name in order:
        module = project.modules[module_name]
        for name, (value, node) in defs[module_name].items():
            lead, trail, _first = _comments(module, node)
            if value not in chosen or (not chosen[value][0] and not chosen[value][1]
                                       and (lead or trail)):
                chosen[value] = (lead, trail)
    out = {}
    for module_name, what, _prefixes in HOMES:
        values = [v for v in chosen if home(v) == module_name]
        groups = collections.OrderedDict()
        for value in sorted(values, key=lambda v: (_owner(v), final[v])):
            groups.setdefault(_owner(value), []).append(value)
        doc = textwrap.fill(f"uebp.nodes.{module_name} -- {what}.", 76)
        text = [f'"""{doc}"""' if "\n" not in doc else f'"""{doc}\n"""']
        for _owner_name, members in groups.items():
            text.append("")
            for value in members:
                lead, trail = chosen[value]
                text += lead
                line = f"{final[value]} = {value!r}".replace("'", '"')
                if len(line) + (len(trail) + 2 if trail else 0) > WIDTH and trail:
                    text.append(trail)
                    trail = ""
                if len(line) > WIDTH and isinstance(value, str):
                    cut = value.rfind(".", 0, WIDTH - len(final[value]) - 8)
                    pad = " " * (len(final[value]) + 4)
                    text.append(f'{final[value]} = ("{value[:cut]}"')
                    text.append(f'{pad}"{value[cut:]}")')
                else:
                    text.append(line + (f"  {trail}" if trail else ""))
        out[module_name] = "\n".join(text) + "\n"
    return out


def module_edits(project, module, defs, bound, final):
    """Edits for one module: its definitions deleted, its uses renamed, its
    imports re-pointed at the catalog."""
    mine = bound[module.name]
    if not mine:
        return []
    edits, needed = [], collections.defaultdict(set)
    for node in ast.walk(module.tree):
        if isinstance(node, ast.Name) and node.id in mine and isinstance(node.ctx, ast.Load):
            name = final[mine[node.id]]
            needed[home(mine[node.id])].add(name)
            if name != node.id:
                edits.append((*module.span(node), name))
    local = defs.get(module.name, {})
    helpers = set()                       # prefix constants only the definitions read
    for name, (_value, node) in local.items():
        _lead, _trail, first = _comments(module, node)
        edits.append((module.starts[first - 1], module.starts[node.end_lineno], ""))
        helpers |= {n.id for n in ast.walk(node.value) if isinstance(n, ast.Name)}
    gone = {id(n) for _v, node in local.values() for n in ast.walk(node)}
    for helper in helpers - set(local):
        reads = [n for n in ast.walk(module.tree) if isinstance(n, ast.Name)
                 and n.id == helper and isinstance(n.ctx, ast.Load) and id(n) not in gone]
        if not reads:
            for node in module.tree.body:
                if (isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                        and node.targets[0].id == helper):
                    edits.append((module.starts[node.lineno - 1],
                                  module.starts[node.end_lineno], ""))
    noqa, last_import, in_header = "", None, True
    for node in module.tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            in_header = False             # a late import is no place for these
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if in_header:
            last_import = node
        a, b = module.span(node)
        line_end = module.src.find("\n", b)
        comment = module.src[b:line_end] if "#" in module.src[b:line_end] else ""
        if "noqa" in comment:
            noqa = "# noqa: E402"
        if not isinstance(node, ast.ImportFrom) or not any(is_catalog(x.name)
                                                           for x in node.names):
            continue
        keep = [x.name + (f" as {x.asname}" if x.asname else "")
                for x in node.names if not is_catalog(x.name)]
        if keep:
            edits.append((a, b + len(comment),
                          S.import_text(node.module, keep, comment.rstrip())))
        else:
            edits.append((module.starts[node.lineno - 1], module.starts[node.end_lineno], ""))
    fresh = "".join(S.import_text(f"uebp.nodes.{m}", sorted(names), noqa) + "\n"
                    for m, names in sorted(needed.items()))
    if fresh:
        at = module.starts[last_import.end_lineno] if last_import else _after_docstring(module)
        edits.append((at, at, fresh))
    return edits


def _after_docstring(module):
    first = module.tree.body[0]
    is_doc = isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
    return module.starts[first.end_lineno] if is_doc else 0


def _tidy(path):
    """Squeeze the blank runs the deleted definitions leave to two lines."""
    with open(path) as fh:
        src = fh.read()
    new = re.sub(r"\n{4,}", "\n\n\n", src)
    if new != src:
        with open(path, "w") as fh:
            fh.write(new)


def run(root, verbose):
    project = S.Project(root)
    defs = {m.name: d for m in project.modules.values() if (d := definitions(m))}
    bound = bindings(project, defs)
    final, report = choose_names(project, defs, bound)
    sources = catalog_sources(project, defs, final)
    changed = 0
    for module in project.modules.values():
        if module.name.startswith("uebp.nodes"):
            continue
        edits = module_edits(project, module, defs, bound, final)
        if edits:
            done, skipped = S.apply(module, edits, True)
            if skipped:
                raise SystemExit(f"{module.rel}: {skipped} overlapping edits")
            _tidy(module.path)
            changed += 1
    package = os.path.join(root, "uebp", "nodes")
    old = os.path.join(root, "uebp", "nodes.py")
    if os.path.exists(old):
        os.remove(old)
    os.makedirs(package, exist_ok=True)
    listing = "\n".join(f"  {name + '.py':<11} {what}" for name, what, _p in HOMES)
    with open(os.path.join(package, "__init__.py"), "w") as fh:
        fh.write('"""uebp.nodes -- the one catalog of node paths every builder '
                 'authors with:\nfunction paths (FN_*), palette nodes (NODE_*) and '
                 'macros (MACRO_*), one\nmodule per engine library. Checked against '
                 'the editor by\nScripts/dev/check_node_catalog.py.\n\n'
                 f'{listing}\n"""\n')
    for name, text in sources.items():
        with open(os.path.join(package, name + ".py"), "w") as fh:
            fh.write(text)
    print(f"[node-catalog] {len(final)} paths in {len(sources)} modules, from "
          f"{sum(len(d) for d in defs.values())} definitions in {len(defs)} files; "
          f"{changed} modules rewritten")
    print(f"[node-catalog] one name per path ({len(report)} paths had several):")
    for line in report:
        print("    " + line)


def main(argv):
    root = S.SCRIPTS
    if "--apply" not in argv:
        root = os.path.join(tempfile.mkdtemp(prefix="node_catalog_"), "Scripts")
        shutil.copytree(S.SCRIPTS, root, ignore=shutil.ignore_patterns(
            "__pycache__", "generated_levels", "*.txt", "*.obj"))
        print(f"[node-catalog] dry run on a copy: diff -ru {S.SCRIPTS} {root}")
    run(root, "-v" in argv)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
