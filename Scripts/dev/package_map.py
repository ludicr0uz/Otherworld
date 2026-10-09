#!/usr/bin/env python3
"""The package maps, checked: each package's ``__init__`` docstring against its modules.

A package under Scripts/ lists its modules in its ``__init__.py`` docstring, by
hand, and an agent finds a module's owner there before it opens anything. This
says where a map and its directory disagree, both ways:

  missing   a ``.py`` of the package the docstring never names. A name counts
            wherever it stands as a whole word, and a glob the map writes
            (``probe_*``, ``fetch_*.py``) names every module it matches.
  ghost     a name the docstring lists that is not there: a token ending
            ``.py`` anywhere in it, or a module name at the head of a map line
            (``name  what it owns``, ``a, b, c``, ``a  b  c``). A glob without
            ``.py`` is not judged: most of them name constants (``FN_*``).

    python3 Scripts/dev/package_map.py                  # every package; exit 1 on a finding
    python3 Scripts/dev/package_map.py --fix <package>  # append what is missing

``--fix`` appends one line per missing module, its name and the first sentence
of its own docstring, at the end of the map: move it to its section by hand. It
never removes a ghost; that line is somebody's to rewrite.
Scripts/dev/tests/test_package_maps.py runs the check on every package.
"""

import argparse
import ast
import fnmatch
import os
import re
import sys

DEV = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(DEV)
ROOT = os.path.dirname(SCRIPTS)

MAX_LINE = 110     # of an appended description

_NAME = r"[A-Za-z_][A-Za-z0-9_]*"
_GLOB = r"[A-Za-z_][A-Za-z0-9_]*\*[A-Za-z0-9_*]*"
# A path or a bare file name ending .py; <Level>-style placeholders never match.
_PY_TOKEN = re.compile(r"(?<![\w<>./*-])((?:[\w.*-]+/)*[\w*]+\.py)(?![\w<>])")
_GLOB_TOKEN = re.compile(r"(?<![\w/.<>])(%s)(?:\.py)?(?![\w/<>])" % _GLOB)
# "  name  what it owns" and "  a, b, c  what they own": names, then two spaces or the end.
_ENTRY = re.compile(r"^ {1,6}((?:%s)(?:, *(?:%s))*),?(?: {2,}\S.*)?$" % (_NAME, _NAME))
# "  a  b  c": nothing but names, two spaces apart, and three at least (two are
# a name and a one-word description).
_ROW = re.compile(r"^ {1,6}(%s(?: {2,}%s){2,})$" % (_NAME, _NAME))


def packages(top=SCRIPTS):
    """Every directory under ``top`` that has an ``__init__.py``, sorted."""
    found = []
    for folder, dirs, files in os.walk(top):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        if "__init__.py" in files:
            found.append(folder)
    return found


def modules(package):
    return sorted(f[:-3] for f in os.listdir(package)
                  if f.endswith(".py") and f != "__init__.py")


def subpackages(package):
    return sorted(d for d in os.listdir(package)
                  if os.path.isfile(os.path.join(package, d, "__init__.py")))


def docstring(path):
    with open(path, encoding="utf-8") as fh:
        return ast.get_docstring(ast.parse(fh.read()), clean=False) or ""


def first_line(path):
    """What a module's docstring opens with: its first sentence, without the
    ``name.py -- `` some begin with; '' when it has none."""
    doc = docstring(path).strip()
    if not doc:
        return ""
    text = " ".join(doc.split("\n\n")[0].split())
    stem = re.escape(os.path.basename(path)[:-3])
    text = re.sub(r"^%s(\.py)? (--|\u2014|-) " % stem, "", text)
    text = re.split(r"(?<=[^.]\.) ", text)[0].rstrip(".")
    return text if len(text) <= MAX_LINE else text[:MAX_LINE].rsplit(" ", 1)[0] + " ..."


def _globs(doc):
    return sorted(set(_GLOB_TOKEN.findall(doc)))


def missing(package):
    """The package's modules its map never names."""
    doc = docstring(os.path.join(package, "__init__.py"))
    globs = _globs(doc)
    return [m for m in modules(package)
            if not re.search(r"(?<![\w/])%s(?!\w)" % re.escape(m), doc)
            and not any(fnmatch.fnmatchcase(m, g) for g in globs)]


def _listed(doc):
    """The names a map lists at the head of its lines."""
    names = []
    for line in doc.splitlines():
        hit = _ROW.match(line)
        if hit:
            names += hit.group(1).split()
            continue
        hit = _ENTRY.match(line)
        if hit:
            names += [n.strip() for n in hit.group(1).split(",")]
    return names


def _py_exists(package, token):
    if "*" in token:
        folder, pattern = os.path.split(token)
        return any(fnmatch.filter(os.listdir(base), pattern)
                   for base in (os.path.join(package, folder), os.path.join(SCRIPTS, folder),
                                os.path.join(ROOT, folder)) if os.path.isdir(base))
    if "/" in token:
        return any(os.path.isfile(os.path.join(base, token)) for base in (package, SCRIPTS, ROOT))
    return token in _all_py()


_ALL_PY = None


def _all_py():
    """Every .py file name in the project's own trees: a bare name may be any of them."""
    global _ALL_PY
    if _ALL_PY is None:
        _ALL_PY = set()
        for top in (SCRIPTS, os.path.join(ROOT, "Content", "Python")):
            for _folder, _dirs, files in os.walk(top):
                _ALL_PY.update(f for f in files if f.endswith(".py"))
    return _ALL_PY


def ghosts(package):
    """The names the map lists that do not exist."""
    doc = docstring(os.path.join(package, "__init__.py"))
    here = set(modules(package)) | set(subpackages(package))
    found = [n for n in _listed(doc) if n not in here]
    found += [t for t in _PY_TOKEN.findall(doc) if not _py_exists(package, t)]
    return sorted(set(found))


def fix(package):
    """Append a line per missing module to the map; returns the names added."""
    names = missing(package)
    if not names:
        return []
    init = os.path.join(package, "__init__.py")
    with open(init, encoding="utf-8") as fh:
        source = fh.read()
    tree = ast.parse(source)
    node = tree.body[0].value if tree.body and isinstance(tree.body[0], ast.Expr) else None
    if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
        raise SystemExit(f"{init}: no docstring to append to; write its first line")
    lines = source.splitlines(keepends=True)
    last = lines[node.end_lineno - 1]
    quote = last[node.end_col_offset - 3:node.end_col_offset]
    if quote not in ('"""', "'''"):
        raise SystemExit(f"{init}: the docstring is not triple-quoted")
    width = max(len(n) for n in names) + 2
    added = "".join(f"  {n.ljust(width)}{first_line(os.path.join(package, n + '.py'))}".rstrip()
                    + "\n" for n in names)
    head = last[:node.end_col_offset - 3]
    if head.strip():        # text on the closing line: end it, and leave a blank line
        head = head.rstrip() + "\n\n"
    elif node.end_lineno > 1 and lines[node.end_lineno - 2].strip():
        head = "\n" + head
    lines[node.end_lineno - 1] = head + added + last[node.end_col_offset - 3:]
    with open(init, "w", encoding="utf-8") as fh:
        fh.write("".join(lines))
    return names


def _resolve(arg):
    for path in (arg, os.path.join(SCRIPTS, arg), os.path.join(ROOT, arg)):
        if os.path.isfile(os.path.join(path, "__init__.py")):
            return os.path.abspath(path)
    raise SystemExit(f"{arg}: not a package (no __init__.py)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("packages", nargs="*", help="package directories (default: all under Scripts/)")
    ap.add_argument("--fix", action="store_true", help="append each missing module's first docstring line")
    args = ap.parse_args(argv)
    if args.fix and not args.packages:
        ap.error("--fix takes the package to fix")
    bad = 0
    for package in [_resolve(p) for p in args.packages] or packages():
        rel = os.path.relpath(package, ROOT)
        if args.fix:
            for name in fix(package):
                print(f"{rel}: added {name}")
        for kind, names in (("missing", missing(package)), ("ghost", ghosts(package))):
            if names:
                bad += 1
                print(f"{rel}: {kind}: {', '.join(names)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
