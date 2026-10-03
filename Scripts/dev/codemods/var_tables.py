"""var_tables.py -- each Blueprint's variables named once, in a table.

    python3 Scripts/dev/codemods/var_tables.py [--apply] [--fingerprint <dir>]

Every bare-string variable name (``add_get_member_variable_node("Health")``,
a wrapper around one, the pin on that node, a default's key, a probe's
WRITABLE entry) becomes a row of the owning Blueprint's table (TABLES) or, for
an engine class's property, a constant of uebp/props.py. The owner is the
class path given at the site; with none, the one Blueprint that declares the
name (from a graph_fingerprint.py directory), by module where several do.
Types come from the fingerprint. A row is typed, and the builder's own
``_declare`` removed, only where this tool found that ``_declare``; a static
default moves with it. What it cannot place it leaves and reports.
"""

import ast
import collections
import glob
import json
import os
import re
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import source as S          # noqa: E402
import strip_coords as SC   # noqa: E402

NODE_CALLS = ("add_get_member_variable_node", "add_set_member_variable_node")
PIN_CALLS = ("_pin", "_set", "out", "_loose_pin")
# alias: (table module, Blueprint package, modules that author its graph)
TABLES = {
    "WV": ("combat.weapon_component.vars", "/Game/Weapons/BP_WeaponComponent",
           ("combat.weapon_component",)),
    "HV": ("combat.health_vars", "/Game/Weapons/BP_HealthComponent",
           ("combat.health_component", "combat.death", "combat.respawn", "combat.replacement",
            "combat.gun_drop", "combat.debuff_drain", "combat.hit_reaction", "loot.")),
    "IV": ("combat.item_vars", "/Game/Weapons/BP_WeaponItem", ("combat.weapon_items",)),
    "SV": ("combat.settings_vars", "/Game/Weapons/BP_Settings", ("combat.settings_savegame",)),
    "BV": ("combat.burst_vars", "/Game/Weapons/BP_BloodSplash", ("combat.burst",)),
    "AV": ("combat.ammo_vars", "/Game/Weapons/BP_AmmoPickup", ("combat.ammo_pickup",)),
    "FV": ("combat.footstep_vars", "/Game/Weapons/BP_FootstepComponent", ("combat.footsteps",)),
    "MV": ("graphics_menu.hud_vars", "/Game/UI/BP_GraphicsMenuHUD",
           ("graphics_menu", "build_graphics_menu")),
    "NV": ("npc.controller_vars", "/Game/Forest/NPC/BP_ForestWandererAI", ("npc",)),
    "UV": ("survival.component_vars", "/Game/Survival/BP_SurvivalComponent",
           ("survival.survival_component", "survival.debuffs")),
    "DV": ("world.day_night_vars", "/Game/World/BP_DayNightCycle", ("world",)),
}
PROPS = ("EP", "uebp.props")
# A wrapper's class expression that is not a constant: what it comes to.
FIXED = {"class_path or self.item_class": "ITEM_CLASS_PATH"}
# Constants that hold a variable's name without being called *_VAR.
NAME_CONSTANTS = {("survival.paths", "ASC_COMPONENT")}
# Class constants this tool cannot evaluate, and properties of the engine
# class a graph's own Blueprint derives from (no class at the site).
CLASS_TABLE = {"SETTINGS_CLASS_PATH": "SV"}
INHERITED = {"BrainComponent"}
BASIC = {"real": "FLOAT", "bool": "BOOL", "int": "INT", "name": "NAME", "string": "STRING"}
WRAP = {"struct": "struct", "object": "obj", "class": "cls"}
SHORT = {'struct("/Script/CoreUObject.Vector")': "VECTOR"}


def constants(project):
    """({module: {constant: value}} for the module-level string constants,
    {class path: (paths module, constant)}, {variable name: (module,
    constant)} for the names some module already holds as a constant)."""
    local, by_value, named = {}, {}, {}
    for module in sorted(project.modules.values(), key=lambda m: (len(m.name), m.name)):
        env = local.setdefault(module.name, {})
        for node in module.tree.body:
            if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)):
                continue
            try:
                value = eval(compile(ast.Expression(node.value), "x", "eval"), {}, dict(env))
            except Exception:
                continue
            name = node.targets[0].id
            if not isinstance(value, str):
                continue
            env[name] = value
            pure = "import unreal" not in module.src
            if (name.endswith("_CLASS_PATH") and value.startswith("/Game/")
                    and module.name.endswith(".paths")):
                by_value.setdefault(value, (module.name, name))
            data = re.search(r"(tuning|consts|paths|game_state)$", module.name)
            if pure and ((name.endswith("_VAR") and data)
                         or (module.name, name) in NAME_CONSTANTS):
                named.setdefault(value, (module.name, name))
    return local, by_value, named


def wrappers(project):
    """{(module, qualname): (name parameter index, class parameter index or
    None, the class expression when it is fixed)}: the functions that hand a
    parameter to a variable node, directly or through one another."""
    found, grew = {}, True
    while grew:
        grew = False
        for module in project.modules.values():
            for qualname, fn in module.functions.items():
                if (module.name, qualname) in found:
                    continue
                is_method = isinstance(module.parent.get(fn), ast.ClassDef)
                every = [a.arg for a in fn.args.posonlyargs + fn.args.args]
                params = every[1:] if is_method else every
                for call in ast.walk(fn):
                    name_arg, class_arg = _var_args(project, module, call, found)
                    if not (isinstance(name_arg, ast.Name) and name_arg.id in params):
                        continue
                    index, fixed = None, None
                    if isinstance(class_arg, ast.Name) and class_arg.id in params:
                        index = params.index(class_arg.id)
                        at = every.index(class_arg.id) - (len(every) - len(fn.args.defaults))
                        fixed = ast.unparse(fn.args.defaults[at]) if at >= 0 else None
                    elif class_arg is not None:
                        fixed = ast.unparse(class_arg)
                    found[(module.name, qualname)] = (params.index(name_arg.id), index, fixed)
                    grew = True
                    break
    return found


def _var_args(project, module, call, found):
    """(name argument, class argument) if ``call`` makes a variable node."""
    if not isinstance(call, ast.Call):
        return None, None
    if isinstance(call.func, ast.Attribute) and call.func.attr in NODE_CALLS and call.args:
        return call.args[0], call.args[1] if len(call.args) > 1 else None
    target = project.resolve(module, call, SC.conventions)
    if target and (target[0].name, target[1]) in found:
        at, class_at, fixed = found[(target[0].name, target[1])]
        if at < len(call.args):
            given = call.args[class_at] if class_at is not None and class_at < len(
                call.args) else next((k.value for k in call.keywords
                                      if k.arg == "class_path"), None)
            if given is None and fixed and fixed != "None":
                given = ast.parse(fixed, mode="eval").body
            return call.args[at], given
    return None, None


class Plan:
    def __init__(self, project, fingerprint):
        self.project = project
        self.local, self.by_value, self.named = constants(project)
        self.order = 0
        self.blueprints = {}
        for path in glob.glob(os.path.join(fingerprint, "*.json")):
            with open(path) as fh:
                data = json.load(fh)
            self.blueprints[data["path"]] = data
        self.alias_of = {bp: alias for alias, (_m, bp, _p) in TABLES.items()}
        self.rows = collections.defaultdict(dict)     # alias -> {name: [type, default]}
        self.props, self.unplaced = set(), []

    def owns(self, alias, name):
        data = self.blueprints.get(TABLES[alias][1], {})
        return name in data.get("variables", {}) or any(
            c.split(" | ")[0] == name for c in data.get("components", []))

    def value_of(self, module, name, depth=0):
        """A constant's value as ``module`` sees it: its own, or an imported one."""
        if name in self.local.get(module.name, {}):
            return self.local[module.name][name]
        if name in module.imports and depth < 6:
            source, original = module.imports[name]
            target = self.project.modules.get(source)
            return self.value_of(target, original, depth + 1) if target else None
        everywhere = {env[name] for env in self.local.values() if name in env}
        return everywhere.pop() if len(everywhere) == 1 else None    # a wrapper's default

    def owner(self, module, name, class_arg):
        """The reference to write for a bare variable name: ``WV.Held``,
        ``EP.MAX_WALK_SPEED``, or None when it cannot be placed."""
        if class_arg is not None and ast.unparse(class_arg) != "None":
            text = FIXED.get(ast.unparse(class_arg), ast.unparse(class_arg))
            if text in CLASS_TABLE:
                return self.place(CLASS_TABLE[text], name)
            value = self.value_of(module, text) or (class_arg.value if isinstance(
                class_arg, ast.Constant) else None)
            if not value:
                return None
            if value.startswith("/Script/"):
                self.props.add(name)
                return f"{PROPS[0]}.{_upper(name)}"
            alias = self.alias_of.get(value.split(".")[0])
            if alias:
                return self.place(alias, name)
            return None
        holders = [a for a in TABLES if self.owns(a, name)]
        if len(holders) > 1:
            holders = [a for a in holders
                       if any(module.name.startswith(p) for p in TABLES[a][2])]
        if not holders and name in INHERITED:
            self.props.add(name)
            return f"{PROPS[0]}.{_upper(name)}"
        return self.place(holders[0], name) if len(holders) == 1 else None

    def place(self, alias, name):
        """The reference for a variable of a table's Blueprint: the constant
        some module already holds its name in, or else a row of the table."""
        if name in self.named:
            return "=".join(self.named[name])            # "module=CONSTANT"
        self.rows[alias].setdefault(name, [None, None, [], 0])
        return f"{alias}.{name}"

    def type_text(self, alias, name, imports):
        """The row's pin type as source, from the fingerprint."""
        entry = self.blueprints[TABLES[alias][1]]["variables"].get(name)
        if not entry:
            return None
        category, _sub, target, container = (entry["type"].split("|") + [""] * 4)[:4]
        if category in BASIC:
            text = BASIC[category]
        elif category in WRAP:
            path = re.search(r"'([^']+)'", target)
            if not path:
                return None
            known = self.by_value.get(path.group(1))
            if known and known[0] != TABLES[alias][0]:
                imports[known[0]].add(known[1])
            text = f'{WRAP[category]}({known[1] if known else chr(34) + path.group(1) + chr(34)})'
            text = SHORT.get(text, text)
        else:
            return None
        return f"array({text})" if container == "Array" else text if container in (
            "None", "") else None


def _upper(name):
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name).upper()


def _static(module, fn, expr):
    """Is a default expression plain data to a table module: names that are
    imports from modules free of ``unreal``, no calls but conversions?"""
    for node in ast.walk(expr):
        if isinstance(node, ast.Call) and not (isinstance(node.func, ast.Name)
                                               and node.func.id in ("float", "int", "str")):
            return False
        if isinstance(node, ast.Name) and node.id not in ("True", "False", "None", "float",
                                                          "int", "str"):
            source = module.imports.get(node.id)
            target = module.project.modules.get(source[0]) if source else None
            if not target or "import unreal" in target.src:
                return False
    return True


def site_edits(plan, module, wraps):
    """(edits, aliases used) for the bare names in one module's graph code
    and WRITABLE lists."""
    edits, used = [], set()

    def swap(node, ref):
        if ref:
            edits.append((*module.span(node), ref.split("=")[-1]))
            used.add(ref if "=" in ref else ref.split(".")[0])

    bound = {}                                   # (function, local) -> (name, ref)
    for call in ast.walk(module.tree):
        name_arg, class_arg = _var_args(plan.project, module, call, wraps)
        if isinstance(name_arg, ast.Constant) and isinstance(name_arg.value, str):
            ref = plan.owner(module, name_arg.value, class_arg)
            if not ref:
                plan.unplaced.append(f"{module.rel}:{call.lineno}: {name_arg.value!r}")
                continue
            swap(name_arg, ref)
            holder = module.parent.get(call)
            scope = next((s for s in module.enclosing(call)
                          if isinstance(s, ast.FunctionDef)), module.tree)
            if isinstance(holder, ast.Assign) and isinstance(holder.targets[0], ast.Name):
                bound[(scope, holder.targets[0].id)] = (name_arg.value, ref)
            if (isinstance(holder, ast.Call) and isinstance(holder.func, ast.Name)
                    and holder.func.id in PIN_CALLS and len(holder.args) > 1
                    and holder.args[0] is call and isinstance(holder.args[1], ast.Constant)
                    and holder.args[1].value == name_arg.value):
                swap(holder.args[1], ref)
    for call in ast.walk(module.tree):
        if (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                and call.func.id in PIN_CALLS and len(call.args) > 1
                and isinstance(call.args[0], ast.Name)
                and isinstance(call.args[1], ast.Constant)):
            scope = next((s for s in module.enclosing(call)
                          if isinstance(s, ast.FunctionDef)), module.tree)
            name, ref = bound.get((scope, call.args[0].id), (None, None))
            if name == call.args[1].value:
                swap(call.args[1], ref)
    for node in ast.walk(module.tree):           # a probe's (BP_PATH, "Name") pairs
        if not (isinstance(node, ast.Tuple) and len(node.elts) == 2
                and isinstance(node.elts[0], ast.Name)
                and node.elts[0].id.endswith("_BP_PATH")):
            continue
        alias = plan.alias_of.get(plan.value_of(module, node.elts[0].id) or "")
        names = [node.elts[1]]
        holder = module.parent.get(node)
        if isinstance(holder, ast.ListComp) and isinstance(node.elts[1], ast.Name):
            names = [e for g in holder.generators if isinstance(g.iter, (ast.Tuple, ast.List))
                     for e in g.iter.elts]
        for item in names:
            if (alias and isinstance(item, ast.Constant) and isinstance(item.value, str)
                    and plan.owns(alias, item.value)):
                swap(item, plan.place(alias, item.value))
    return edits, used


def builder_edits(plan, module, imports):
    """In a builder: the ``_declare`` of each tabled name removed (its row
    becomes typed), its static default moved, the table declared instead."""
    edits, used = [], set()
    for fn in [f for f in module.functions.values() if isinstance(f, ast.FunctionDef)]:
        declared, first, editor = collections.defaultdict(list), {}, {}
        for node in ast.walk(fn):
            calls, loop = [], None
            if isinstance(node, ast.Expr) and _is_declare(node.value):
                calls = [(node, node.value.args[1])]
            elif (isinstance(node, ast.For) and len(node.body) == 1
                  and isinstance(node.body[0], ast.Expr) and _is_declare(node.body[0].value)
                  and isinstance(node.iter, ast.Tuple)
                  and isinstance(node.target, ast.Name)
                  and isinstance(node.body[0].value.args[1], ast.Name)
                  and node.body[0].value.args[1].id == node.target.id):
                loop, calls = node, [(node, e) for e in node.iter.elts]
            hit = []
            for statement, name in calls:
                if not (isinstance(name, ast.Constant) and isinstance(name.value, str)):
                    continue
                ref = plan.owner(module, name.value, None)
                alias = ref.split(".")[0] if ref else None
                if not alias or alias == PROPS[0] or "=" in ref:
                    continue
                type_text = plan.type_text(alias, name.value, imports[alias])
                if not type_text:
                    continue
                plan.order += 1
                plan.rows[alias][name.value][0] = type_text
                plan.rows[alias][name.value][3] = plan.order
                declared[alias].append(name.value)
                first.setdefault(alias, statement)
                editor[alias] = module.text((loop.body[0] if loop else statement).value.args[0])
                hit.append(name)
            if not hit:
                continue
            top, notes = _lead(module, node.lineno)
            a, b = module.starts[top - 1], module.starts[node.end_lineno]
            if loop and len(hit) < len(loop.iter.elts):
                keep = [module.text(e) for e in loop.iter.elts if e not in hit]
                if len(keep) == 1 and keep[0].startswith("*"):
                    edits.append((*module.span(loop.iter), keep[0][1:]))
                elif len(keep) == 1:
                    call = loop.body[0].value
                    one = (f"_declare({module.text(call.args[0])}, {keep[0]}, "
                           f"{module.text(call.args[2])})")
                    edits.append((module.span(loop)[0], module.span(loop)[1], one))
                else:
                    edits.append((*module.span(loop.iter), f"({', '.join(keep)})"))
            else:
                edits.append((a, b, ""))
                ref = plan.owner(module, hit[0].value, None)
                plan.rows[ref.split(".")[0]][hit[0].value][2] += notes
        for alias, statement in first.items():
            at = module.starts[_lead(module, statement.lineno)[0] - 1]
            pad = " " * statement.col_offset
            edits.append((at, at, f"{pad}declare({editor[alias]}, {alias}.TABLE)\n"))
            used |= {alias, "declare"}
        for call in ast.walk(fn):                 # the defaults written beside them
            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                    and call.func.id == "_apply_defaults" and len(call.args) == 2
                    and isinstance(call.args[1], ast.Dict)):
                continue
            table, moved = call.args[1], set()
            for key, value in zip(table.keys, table.values):
                if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                    continue
                ref = plan.owner(module, key.value, None)
                alias = ref.split(".")[0] if ref else None
                if not alias or alias == PROPS[0]:
                    continue
                if "=" in ref:
                    edits.append((*module.span(key), ref.split("=")[1]))
                    used.add(ref)
                    continue
                line = module.src[module.starts[key.lineno - 1]:module.span(key)[0]]
                rest = module.src[module.span(value)[1]:module.starts[value.end_lineno] - 1]
                alone = not line.strip() and re.fullmatch(r",\s*(#.*)?", rest)
                if key.value in declared[alias] and alone and _static(module, fn, value):
                    top, notes = _lead(module, key.lineno)
                    row = plan.rows[alias][key.value]
                    row[1] = module.text(value)
                    row[2] += notes + ([rest.lstrip(", ")] if "#" in rest else [])
                    for name in {n.id for n in ast.walk(value) if isinstance(n, ast.Name)}:
                        if name in module.imports:
                            imports[alias][module.imports[name][0]].add(name)
                    edits.append((module.starts[top - 1], module.starts[value.end_lineno], ""))
                    moved.add(alias)
                else:
                    edits.append((*module.span(key), ref))
                    used.add(alias)
            for alias in moved:
                at = module.span(table)[0] + 1
                edits.append((at, at, f"**defaults({alias}.TABLE), "))
                used |= {alias, "defaults"}
    return edits, used


def _lead(module, lineno):
    """(first line, comment lines) of the comment block directly above a line."""
    lines, first, out = module.src.split("\n"), lineno, []
    while first > 1 and lines[first - 2].lstrip().startswith("#"):
        first -= 1
        out.insert(0, lines[first - 1].strip())
    return first, out


def _is_declare(call):
    return (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
            and call.func.id == "_declare" and len(call.args) == 3)


def import_lines(module, used, noqa):
    lines = []
    helpers = sorted(u for u in used if u in ("declare", "defaults"))
    if helpers:
        lines.append(S.import_text("uebp.vars", helpers, noqa))
    borrowed = collections.defaultdict(set)
    for ref in (u for u in used if "=" in u):
        source, name = ref.split("=")
        if source != module.name and name not in module.imports:
            borrowed[source].add(name)
    lines += [S.import_text(source, sorted(names), noqa)
              for source, names in sorted(borrowed.items())]
    for alias in sorted(u for u in used if u not in ("declare", "defaults") and "=" not in u):
        target = PROPS[1] if alias == PROPS[0] else TABLES[alias][0]
        package, _, name = target.rpartition(".")
        lines.append(f"from {package} import {name} as {alias}"
                     + (f"  {noqa}" if noqa else ""))
    return "".join(line + "\n" for line in lines)


def table_source(plan, alias, imports):
    module, blueprint, _prefixes = TABLES[alias]
    rows = plan.rows[alias]
    needs = sorted({w for t, *_rest in rows.values() if t for w in re.findall(
        r"\b(FLOAT|BOOL|INT|NAME|STRING|VECTOR|struct|obj|cls|array)\b", t)} | {"Var"})
    ordered = sorted(rows, key=lambda n: (rows[n][3] == 0, rows[n][3], n))
    text = [f'"""{blueprint.rsplit("/", 1)[1]}\'s member variables, named once: each row is',
            "the name, the pin type and the default (uebp/vars.py). The builder declares",
            "TABLE; a row with no type is a component, or a variable declared elsewhere.",
            '"""', "", S.import_text("uebp.vars", needs)]
    text += [S.import_text(m, sorted(names)) for m, names in sorted(imports.items())]
    text.append("")
    for name in ordered:
        kind, default, notes, _order = rows[name]
        text += notes
        args = [repr(name).replace("'", '"')] + ([kind] if kind else []) + (
            [default] if default else [])
        text.append(f"{name} = Var({', '.join(args)})")
    typed = [n for n in ordered if rows[n][0]]
    text += ["", "TABLE = (" + ", ".join(typed) + ("," if len(typed) == 1 else "") + ")"]
    body = "\n".join(text) + "\n"
    return re.sub(r"^(TABLE = \()(.{90,})$", lambda m: _wrap_table(typed), body, flags=re.M)


def _wrap_table(names):
    lines, row = ["TABLE = ("], "   "
    for name in names:
        if len(row) + len(name) + 2 > 92:
            lines.append(row.rstrip())
            row = "   "
        row += f" {name},"
    return "\n".join(lines + [row.rstrip(), ")"])


def run(root, fingerprint):
    project = S.Project(root)
    SC.PROJECT = project
    for module in project.modules.values():
        module.project = project
    plan = Plan(project, fingerprint)
    wraps = wrappers(project)
    imports = collections.defaultdict(lambda: collections.defaultdict(set))
    pending = {}
    for module in project.modules.values():
        if module.name.startswith(("uebp.", "forest_", "asset_pipeline")):
            continue
        a, used_a = site_edits(plan, module, wraps)
        b, used_b = builder_edits(plan, module, imports)
        if a or b:
            pending[module.name] = (a + b, used_a | used_b)
    for name, (edits, used) in pending.items():
        module = project.modules[name]
        clash = [u for u in used if "=" not in u
                 and (u in module.imports or u in module.aliases)]
        if clash:
            raise SystemExit(f"{module.rel} already binds {clash}")
        header = [n for n in module.tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        firstdef = next((n.lineno for n in module.tree.body
                         if isinstance(n, (ast.FunctionDef, ast.ClassDef))), 10 ** 9)
        header = [n for n in header if n.lineno < firstdef]
        noqa = "# noqa: E402" if "noqa: E402" in module.src else ""
        first = module.tree.body[0]
        doc = isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
        at = (module.starts[header[-1].end_lineno] if header
              else module.starts[first.end_lineno] if doc else 0)
        edits.append((at, at, import_lines(module, used, noqa)))
        done, skipped = S.apply(module, edits, True)
        if skipped:
            raise SystemExit(f"{module.rel}: {skipped} overlapping edits")
    for alias in sorted(plan.rows):
        path = os.path.join(root, *TABLES[alias][0].split(".")) + ".py"
        with open(path, "w") as fh:
            fh.write(table_source(plan, alias, imports[alias]))
    with open(os.path.join(root, "uebp", "props.py"), "w") as fh:
        fh.write('"""Engine properties and components the graphs read through a variable '
                 'node:\nthe name each is known by on its engine class."""\n\n'
                 + "".join(f'{_upper(n)} = "{n}"\n' for n in sorted(plan.props)))
    print(f"[var-tables] {sum(len(r) for r in plan.rows.values())} rows in "
          f"{len(plan.rows)} tables, {len(plan.props)} engine properties, "
          f"{len(pending)} modules rewritten")
    for alias in sorted(plan.rows):
        typed = sum(1 for t, *_rest in plan.rows[alias].values() if t)
        print(f"    {alias} {TABLES[alias][0]}: {len(plan.rows[alias])} rows, {typed} typed")
    print("[var-tables] names that already had a constant, now used everywhere:")
    for name, (source, const) in sorted(plan.named.items()):
        if any(f"{source}={const}" in used for _e, used in pending.values()):
            print(f"    {name!r}: {source}.{const}")
    for line in sorted(set(plan.unplaced)):
        print(f"[var-tables] LEFT: {line}")


def main(argv):
    root = S.SCRIPTS
    fingerprint = os.path.join(os.path.dirname(S.SCRIPTS), "Saved", "uepy", "fingerprint",
                               "baseline_a")
    if "--fingerprint" in argv:
        fingerprint = argv[argv.index("--fingerprint") + 1]
    if "--apply" not in argv:
        root = os.path.join(tempfile.mkdtemp(prefix="var_tables_"), "Scripts")
        shutil.copytree(S.SCRIPTS, root, ignore=shutil.ignore_patterns(
            "__pycache__", "generated_levels", "*.txt", "*.obj"))
        print(f"[var-tables] dry run on a copy: diff -ru {S.SCRIPTS} {root}")
    run(root, fingerprint)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
