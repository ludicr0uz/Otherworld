"""typed_set.py -- ``_set(n, pin, "true")`` becomes ``_set(n, pin, True)``.

    python3 Scripts/dev/codemods/typed_set.py [--apply]

uebp.graph._set formats a Python bool as the pin literal, so the two bool
strings need not be spelled. Only direct calls of uebp.graph._set are
rewritten: a wrapper that tells a literal from a pin by ``isinstance(value,
str)`` still needs the string.
"""

import ast
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import source as S  # noqa: E402

BOOLS = {"true": "True", "false": "False"}


def main(argv):
    write = "--apply" in argv
    project = S.Project()
    total = 0
    for module in project.modules.values():
        edits = []
        for call in ast.walk(module.tree):
            if not (isinstance(call, ast.Call) and len(call.args) == 3 and not call.keywords
                    and isinstance(call.args[2], ast.Constant)
                    and call.args[2].value in BOOLS):
                continue
            target = project.resolve(module, call)
            if target and (target[0].name, target[1]) == ("uebp.graph", "_set"):
                edits.append((*module.span(call.args[2]), BOOLS[call.args[2].value]))
        total += len(edits)
        if write and edits:
            S.apply(module, edits, True)
    print(f"[typed-set] {total} bool literals {'typed' if write else 'would be typed'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
