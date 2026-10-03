"""join_lines.py -- rejoin statements a codemod left wrapped for no reason.

    python3 Scripts/dev/codemods/join_lines.py [--apply] <files...>

Stripping arguments leaves ``f(a, b,\\n      c)`` where ``f(a, b, c)`` now
fits. A simple statement that spans lines, holds no comment and no
multi-line string, and fits in WIDTH columns once joined, is joined (a
``for`` header too, or re-hung under its bracket when it does not fit) -- but
only one the working tree changed since git HEAD: a statement HEAD already
wrapped that way was wrapped on purpose (a table, one entry per line). The
file's AST is compared before and after; a file whose AST would change is
left alone.
"""

import ast
import io
import os
import subprocess
import sys
import tokenize

WIDTH = 100
SIMPLE = (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Expr, ast.Return, ast.Raise)


def _kept_wraps(path):
    """The AST dumps of the statements HEAD holds wrapped over several lines."""
    shown = subprocess.run(["git", "show", f"HEAD:./{os.path.basename(path)}"],
                           cwd=os.path.dirname(os.path.abspath(path)),
                           capture_output=True, text=True)
    if shown.returncode:
        return set()
    tree = ast.parse(shown.stdout)
    return ({ast.dump(n) for n in ast.walk(tree)
             if isinstance(n, SIMPLE) and n.end_lineno > n.lineno}
            | {_header(n) for n in ast.walk(tree) if isinstance(n, ast.For)})


def _header(loop):
    return ast.dump(loop.target) + ast.dump(loop.iter)


def joined(src, keep=()):
    tree = ast.parse(src)
    lines = src.split("\n")
    busy = set()                      # lines holding a comment or part of a long string
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT:
            busy.add(tok.start[0])
        elif tok.type == tokenize.STRING and tok.start[0] != tok.end[0]:
            busy.update(range(tok.start[0], tok.end[0] + 1))
    spans = []
    for node in ast.walk(tree):
        if (isinstance(node, SIMPLE) and node.end_lineno > node.lineno
                and ast.dump(node) not in keep):
            span = range(node.lineno, node.end_lineno + 1)
            if busy.isdisjoint(span):
                spans.append((node.lineno, node.end_lineno))
    headers = [(n.lineno, n.iter.end_lineno) for n in ast.walk(tree)
               if isinstance(n, ast.For) and n.iter.end_lineno > n.lineno
               and _header(n) not in keep
               and busy.isdisjoint(range(n.lineno, n.iter.end_lineno + 1))]
    for first, last in sorted(spans + headers, reverse=True):
        parts = [lines[first - 1].rstrip()] + [l.strip() for l in lines[first:last]]
        one = parts[0]
        for part in parts[1:]:
            glue = "" if one.endswith(("(", "[", "{")) or part[:1] in ")]}" else " "
            one += glue + part
        if len(one) <= WIDTH:
            lines[first - 1:last] = [one]
        elif (first, last) in headers:
            # Too long to join: hang the rest under the first open bracket.
            head = lines[first - 1]
            col = head.index("(", head.index(" in ")) + 1
            lines[first:last] = [" " * col + l.strip() for l in lines[first:last]]
    out = "\n".join(lines)
    return out if ast.dump(ast.parse(out)) == ast.dump(tree) else src


def main(argv):
    write = "--apply" in argv
    saved = 0
    for path in (a for a in argv if not a.startswith("--")):
        with open(path) as fh:
            src = fh.read()
        new = joined(src, _kept_wraps(path))
        saved += src.count("\n") - new.count("\n")
        if write and new != src:
            with open(path, "w") as fh:
                fh.write(new)
    print(f"[join-lines] {saved} lines {'joined' if write else 'would be joined'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
