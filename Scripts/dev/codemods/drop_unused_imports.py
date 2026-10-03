"""drop_unused_imports.py -- remove the imports a codemod left unused.

    python3 Scripts/dev/codemods/drop_unused_imports.py [--apply]

Only what pyflakes reports unused now and did not at git HEAD: an import that
was already unused is somebody's choice (a re-export, a side effect).
"""

import collections
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import source as S  # noqa: E402

UNUSED = re.compile(r"^(.*?):\d+:\d+:? '([\w.]+)' imported but unused")


def unused(root):
    """{relative path: {(module, name)}} from pyflakes."""
    out = collections.defaultdict(set)
    report = subprocess.run([sys.executable, "-m", "pyflakes", "."], cwd=root,
                            capture_output=True, text=True).stdout
    for line in report.splitlines():
        m = UNUSED.match(line)
        if m and "generated_levels" not in m.group(1):
            module, _, name = m.group(2).rpartition(".")
            out[os.path.normpath(m.group(1))].add((module, name.split(" as ")[0]))
    return out


def at_head(repo):
    """The same report for git HEAD, from a scratch checkout of Scripts/."""
    scratch = subprocess.run(["mktemp", "-d"], capture_output=True, text=True).stdout.strip()
    subprocess.run(f"git archive HEAD Scripts | tar -x -C '{scratch}'", shell=True, cwd=repo,
                   check=True)
    return unused(os.path.join(scratch, "Scripts"))


def main(argv):
    write = "--apply" in argv
    before = at_head(os.path.dirname(S.SCRIPTS))
    project = S.Project()
    dropped = 0
    for rel, names in sorted(unused(S.SCRIPTS).items()):
        fresh = names - before.get(rel, set())
        module = next((m for m in project.modules.values() if m.rel == rel), None)
        if not fresh or not module:
            continue
        edits = S.import_edits(module, {key: None for key in fresh})
        for module_name, name in sorted(fresh):
            print(f"    {rel}: {module_name}.{name}")
        dropped += len(fresh)
        if write:
            S.apply(module, edits, True)
    print(f"[drop-unused-imports] {dropped} imports {'dropped' if write else 'would go'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
