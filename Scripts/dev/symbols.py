"""Write Scripts/dev/symbols.txt: a symbol index of the tree, one line per symbol.

Under Scripts/: every `def`, `class` and `UPPER_CASE =` constant at any indent
for defs and classes, at column 0 for constants. Under Source/: every UCLASS
and UFUNCTION (the declaration that follows the macro). A line is
`path:line: text`, a `def` shows as its bare name, the path relative to Scripts/ (Source/ keeps its prefix).
Indented defs, tests/ and the like are left out to stay small. Files come from the git index, so the output is the same
for the commit as for the working tree. Grep it before reading code:

    grep -n 'ask_consts' Scripts/dev/symbols.txt

`python3 Scripts/dev/symbols.py` rewrites the file; the pre-commit hook does
that and stages it; `--check` exits 1 when it is stale (tests/test_symbols.py).
"""

import os
import re
import subprocess
import sys

DEV = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(DEV))
OUT = os.path.join(DEV, "symbols.txt")

PY = re.compile(r"^(?:async\s+)?(?:def|class)\s+\w+|^[A-Z][A-Z0-9_]*\s*=")
CPP_EXT = (".h", ".hpp", ".cpp")
COMMON = {"main", "probe", "probe_server", "probe_client",
          "WRITABLE", "LEVEL", "RUNS_ON", "SYSTEMS", "run"}  # one per file: noise
MACRO = re.compile(r"^\s*(UCLASS|UFUNCTION)\b")


def tracked():
    out = subprocess.run(["git", "ls-files", "-z", "--", "Scripts", "Source"],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return sorted(f for f in out.split("\0") if f)


def lines_of(path):
    try:
        with open(os.path.join(ROOT, path), encoding="utf-8", errors="replace") as fh:
            return fh.read().splitlines()
    except OSError:
        return []


def symbols():
    rows = []
    for path in tracked():
        if path.startswith("Scripts/") and path.endswith(".py") and not path.startswith("Scripts/dev/tests/"):
            for i, line in enumerate(lines_of(path), 1):
                if PY.match(line):
                    name = re.split(r"[(:=]", line.replace("async ", "").removeprefix("def "), 1)[0].strip()
                    if name in COMMON:
                        continue
                    rows.append(f"{path[len('Scripts/'):]}:{i}: {name}")
        elif path.startswith("Source/") and path.endswith(CPP_EXT):
            src = lines_of(path)
            for i, line in enumerate(src, 1):
                if MACRO.match(line):
                    nxt = next((s.strip() for s in src[i:i + 4]
                                if s.strip() and not s.strip().startswith(("UFUNCTION", "UCLASS", "meta", "//"))), "")
                    rows.append(f"{path}:{i}: {MACRO.match(line).group(1)} {nxt[:70]}")
    return "\n".join(rows) + "\n"


def main():
    text = symbols()
    if "--check" in sys.argv:
        cur = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        sys.exit(0 if cur == text else 1)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(text)


if __name__ == "__main__":
    main()
