"""What the codemods share: the project's modules parsed, a call resolved to
the function it reaches, a call's or a def's argument list cut into exact
source spans, and edits applied to the text.

Plain Python, ``ast`` and ``tokenize`` only (no libcst on this machine).
"""

import ast
import bisect
import glob
import io
import os
import tokenize

SCRIPTS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKIP_DIRS = ("generated_levels", "__pycache__", os.path.join("dev", ""))


class Module:
    def __init__(self, path, root=SCRIPTS):
        self.path = path
        self.rel = os.path.relpath(path, root)
        rel = self.rel[:-3]
        self.name = rel.replace(os.sep, ".").removesuffix(".__init__")
        self.reload()

    def reload(self):
        with open(self.path) as fh:
            self.src = fh.read()
        self.tree = ast.parse(self.src)
        self.starts = [0]
        for line in self.src.split("\n"):
            self.starts.append(self.starts[-1] + len(line) + 1)
        self.parent = {}
        for node in ast.walk(self.tree):
            for child in ast.iter_child_nodes(node):
                self.parent[child] = node
        self.functions = {}        # qualname -> FunctionDef
        self._index(self.tree, "")
        self.imports, self.aliases = {}, {}
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for a in node.names:
                    self.imports[a.asname or a.name] = (node.module, a.name)
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if a.asname:
                        self.aliases[a.asname] = a.name
        self._tokens = None
        self._qualnames = {id(fn): name for name, fn in self.functions.items()}
        self._constructed = {}

    def _index(self, node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.functions[prefix + child.name] = child
                self._index(child, prefix + child.name + ".")
            elif isinstance(child, ast.ClassDef):
                self._index(child, prefix + child.name + ".")
            else:
                self._index(child, prefix)

    def offset(self, lineno, col):
        """A character offset from an ast position (whose columns are UTF-8 bytes)."""
        line = self.src[self.starts[lineno - 1]:self.starts[lineno] - 1]
        return self.starts[lineno - 1] + len(line.encode()[:col].decode())

    def span(self, node):
        return (self.offset(node.lineno, node.col_offset),
                self.offset(node.end_lineno, node.end_col_offset))

    def text(self, node):
        a, b = self.span(node)
        return self.src[a:b]

    def tokens(self):
        """The code tokens as (string, start, end) offsets, and their starts."""
        if self._tokens is None:
            skip = (tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT, tokenize.INDENT,
                    tokenize.DEDENT)
            toks = [(tok.string, self.starts[tok.start[0] - 1] + tok.start[1],
                     self.starts[tok.end[0] - 1] + tok.end[1])
                    for tok in tokenize.generate_tokens(io.StringIO(self.src).readline)
                    if tok.type not in skip]
            self._tokens = (toks, [t[1] for t in toks])
        return self._tokens

    def qualname(self, fn):
        return self._qualnames.get(id(fn))

    def constructed(self, scope):
        """{name: class name} for ``name = Cls(...)`` assignments in a scope."""
        if id(scope) not in self._constructed:
            found = {}
            for node in ast.walk(scope):
                if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
                        and isinstance(node.value.func, ast.Name)):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            found.setdefault(target.id, node.value.func.id)
            self._constructed[id(scope)] = found
        return self._constructed[id(scope)]

    def enclosing(self, node):
        """The function and class scopes around ``node``, innermost first."""
        out = []
        while node in self.parent:
            node = self.parent[node]
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                out.append(node)
        return out


class Project:
    def __init__(self, root=SCRIPTS):
        self.root, self.modules = root, {}
        for path in sorted(glob.glob(os.path.join(root, "**", "*.py"), recursive=True)):
            rel = os.path.relpath(path, root)
            if any(part in rel for part in SKIP_DIRS):
                continue
            module = Module(path, root)
            self.modules[module.name] = module

    def reload(self):
        for module in self.modules.values():
            module.reload()

    def lookup(self, module_name, name, depth=0):
        """(module, qualname) of the top-level function ``name`` in a module,
        following re-imports."""
        module = self.modules.get(module_name)
        if not module or depth > 6:
            return None
        if name in module.functions and "." not in name:
            return module, name
        if name in module.imports:
            source, original = module.imports[name]
            return self.lookup(source, original, depth + 1)
        return None

    def class_of(self, module, name, depth=0):
        """(module, class name) for a class visible in ``module`` as ``name``."""
        if any(q.startswith(name + ".") for q in module.functions) and not any(
                q == name for q in module.functions):
            return module, name
        if name in module.imports and depth < 6:
            source, original = module.imports[name]
            target = self.modules.get(source)
            if target:
                return self.class_of(target, original, depth + 1)
        return None

    def _receiver_class(self, module, call, receiver, conventions):
        scopes = module.enclosing(call)
        for scope in scopes:
            if isinstance(scope, ast.ClassDef):
                continue
            first = scope.args.args[0].arg if scope.args.args else None
            owner = module.parent.get(scope)
            if isinstance(owner, ast.ClassDef) and receiver == first:
                return module, owner.name
            made = module.constructed(scope).get(receiver)
            found = self.class_of(module, made) if made else None
            if found:
                return found
        return conventions(module, receiver) if conventions else None

    def resolve(self, module, call, conventions=None):
        """(module, qualname) of the project function a Call reaches, or None.
        ``conventions(module, receiver)`` names the class of a receiver that
        is a parameter (``g``), as (module, class name)."""
        func = call.func
        if isinstance(func, ast.Name):
            for scope in module.enclosing(call):
                if isinstance(scope, ast.ClassDef):
                    continue
                nested = module.qualname(scope) + "." + func.id
                if nested in module.functions:
                    return module, nested
            found = self.lookup(module.name, func.id)
            if found:
                return found
            owner = self._receiver_class(module, call, func.id, conventions)
            if owner and owner[1] + ".__call__" in owner[0].functions:
                return owner[0], owner[1] + ".__call__"
            return None
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            receiver = func.value.id
            if receiver in module.aliases:
                return self.lookup(module.aliases[receiver], func.attr)
            if receiver in module.imports:
                source, original = module.imports[receiver]
                as_module = self.modules.get(f"{source}.{original}")
                if as_module:
                    return self.lookup(as_module.name, func.attr)
            owner = self._receiver_class(module, call, receiver, conventions)
            if owner and f"{owner[1]}.{func.attr}" in owner[0].functions:
                return owner[0], f"{owner[1]}.{func.attr}"
        return None


# ─── Argument lists as source spans ──────────────────────────────────────────

def segments(module, after):
    """The comma-separated pieces of the parenthesised list that opens at or
    after offset ``after``: (open, close, [(start, end, comma_before)]).
    ``open``/``close`` are the offsets of the parentheses themselves."""
    toks, starts = module.tokens()
    i = bisect.bisect_left(starts, after)
    while toks[i][0] != "(":
        i += 1
    open_at, depth, out, first, last, comma = toks[i][1], 0, [], None, None, None
    for k in range(i, len(toks)):
        text, tok_start, tok_end = toks[k]
        if text in "([{" and text:
            depth += 1
            if depth == 1:
                continue
        elif text in ")]}" and text:
            depth -= 1
            if depth == 0:
                if first is not None:
                    out.append((first, last, comma))
                return open_at, tok_start, out
        if depth == 1 and text == ",":
            if first is not None:
                out.append((first, last, comma))
            first, last, comma = None, None, tok_start
            continue
        if first is None:
            first = tok_start
        last = tok_end
    raise ValueError("unbalanced parentheses")


def removal(segs, close, drop):
    """The spans to delete to remove the segments whose indices are in ``drop``."""
    out, i = [], 0
    while i < len(segs):
        if i not in drop:
            i += 1
            continue
        j = i
        while j + 1 in drop:
            j += 1
        if i > 0:
            out.append((segs[i][2], segs[j][1]))
        elif j + 1 < len(segs):
            out.append((segs[0][0], segs[j + 1][0]))
        else:
            out.append((segs[0][0], segs[j][1]))
        i = j + 1
    return out


def segment_of(module, segs, node):
    start = module.span(node)[0]
    for i, (a, b, _comma) in enumerate(segs):
        if a <= start < b:
            return i
    return None


def apply(module, edits, write):
    """Apply (start, end, replacement) edits that do not overlap; returns
    (applied, skipped). Lines an edit leaves blank are dropped."""
    done, skipped, src, floor = 0, 0, module.src, len(module.src) + 1
    for start, end, new in sorted(set(edits), reverse=True):
        if end > floor:
            skipped += 1
            continue
        whole_lines = src[start:end].endswith("\n")
        src, floor, done = src[:start] + new + src[end:], start, done + 1
        line_start = src.rfind("\n", 0, start) + 1
        line_end = src.find("\n", start)
        line_end = len(src) if line_end < 0 else line_end
        line = src[line_start:line_end]
        if line.strip() == "" and start != end and new == "" and not whole_lines:
            src = src[:line_start] + src[line_end + 1:]
        elif line != line.rstrip():
            src = src[:line_start] + line.rstrip() + src[line_end:]
    if done and write:
        with open(module.path, "w") as fh:
            fh.write(src)
    return done, skipped


# ─── Import statements ───────────────────────────────────────────────────────

IMPORT_WIDTH = 95


def import_text(module_name, names, comment=""):
    """``from m import a, b``, wrapped in parentheses past IMPORT_WIDTH."""
    one = f"from {module_name} import {', '.join(names)}"
    if comment:
        comment = "  " + comment.strip()
        if len(one) <= 64:
            return one.ljust(66) + comment.strip()
    if len(one) + len(comment) <= IMPORT_WIDTH:
        return one + comment
    lines, row = [], "   "
    for name in names:
        if len(row) + len(name) + 2 > IMPORT_WIDTH - 3:
            lines.append(row + ",")
            row = "   "
        row += (" " if row == "   " else ", ") + name
    lines.append(row + ")")
    return f"from {module_name} import ({comment}\n" + "\n".join(lines)


def import_edits(module, moves, renames=None):
    """Edits that re-home imported names. ``moves``: {(from module, name): to
    module}; a name moved to ``None`` is dropped. ``renames``: {(from module,
    name): new name}. Top-level ``from`` imports only; each target module ends
    with one statement, where its first source statement stood."""
    renames = renames or {}
    froms = [n for n in module.tree.body if isinstance(n, ast.ImportFrom) and n.module]
    wanted, touched = {}, []
    for node in froms:
        if not any((node.module, a.name) in moves for a in node.names):
            continue
        touched.append(node)
        for a in node.names:
            target = moves.get((node.module, a.name), node.module)
            name = renames.get((node.module, a.name), a.name)
            if target:
                wanted.setdefault(target, []).append(
                    name + (f" as {a.asname}" if a.asname else ""))
    if not touched:
        return []
    merged = [n for n in froms if n.module in wanted and n not in touched]
    for node in merged:
        wanted[node.module] += [a.name + (f" as {a.asname}" if a.asname else "")
                                for a in node.names]
    edits, first = [], min(touched + merged, key=lambda n: n.lineno)
    for node in touched + merged:
        a, b = module.span(node)
        line_end = module.src.find("\n", b)
        comment = module.src[b:line_end] if "#" in module.src[b:line_end] else ""
        text = ""
        if node is first:
            text = "\n".join(import_text(m, sorted(set(names)), comment.rstrip())
                             for m, names in sorted(wanted.items()))
        end = b + len(comment) if text or comment else b
        edits.append((a, end, text))
    return edits


# ─── Does every call still fit its function? ─────────────────────────────────

def arity_errors(project, conventions=None):
    """Calls whose arguments do not bind to the function they resolve to."""
    out = []
    for module in project.modules.values():
        for call in ast.walk(module.tree):
            if not isinstance(call, ast.Call):
                continue
            if any(isinstance(a, ast.Starred) for a in call.args) or any(
                    k.arg is None for k in call.keywords):
                continue
            target = project.resolve(module, call, conventions)
            if not target:
                continue
            fn = target[0].functions[target[1]]
            params = [a.arg for a in fn.args.posonlyargs + fn.args.args]
            is_method = isinstance(target[0].parent.get(fn), ast.ClassDef)
            if is_method:
                params = params[1:]
            required = len(params) - len(fn.args.defaults)
            if is_method and len(fn.args.defaults) > len(params):
                required = 0
            given = len(call.args)
            names = {k.arg for k in call.keywords}
            kwonly = {a.arg for a in fn.args.kwonlyargs}
            problem = None
            if given > len(params) and not fn.args.vararg:
                problem = f"{given} positional for {len(params)}"
            elif not fn.args.kwarg and names - set(params) - kwonly:
                problem = f"unknown keyword {sorted(names - set(params) - kwonly)}"
            elif names & set(params[:given]):
                problem = f"given twice: {sorted(names & set(params[:given]))}"
            else:
                missing = [p for p in params[given:required] if p not in names]
                if missing:
                    problem = f"missing {missing}"
            if problem:
                out.append(f"{module.rel}:{call.lineno}: "
                           f"{target[1]}(): {problem}")
    return sorted(out)
