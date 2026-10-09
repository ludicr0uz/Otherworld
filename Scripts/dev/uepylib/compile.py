"""`uepy.py --compile`: the C++ cycle as one command (Source/CLAUDE.md, "Compile").

A build while an editor of this project is still exiting writes a numbered
dylib copy and leaves `UnrealEditor.modules` naming the old one, so the next
editor loads a module without the new classes. This closes the editors, waits
for them to be gone, builds, and makes the modules file name the newest dylib
of each module. The caller then proves the module loads.
"""

import glob
import json
import os
import re
import subprocess
import time

from uepylib import editors
from uepylib.paths import log, uproject

PROVE = ("import unreal\n"
         "assert hasattr(unreal, 'OtherworldMovementLibrary'), "
         "'OtherworldMovementLibrary missing: the editor loaded an old Otherworld module'\n"
         "print('[uepy] OtherworldMovementLibrary present')")
_ERROR = re.compile(r"error:|error C\d+|Error:|ERROR|Server targets are not")


def newest_dylib(bin_dir, module):
    """Newest dylib of a module: `libUnrealEditor-<module>[-NNNN].dylib`."""
    pat = re.compile(rf"libUnrealEditor-{re.escape(module)}(-\d+)?\.dylib$")
    hits = [p for p in glob.glob(os.path.join(bin_dir, f"libUnrealEditor-{module}*.dylib"))
            if pat.search(p)]
    return os.path.basename(max(hits, key=os.path.getmtime)) if hits else None


def fix_modules(bin_dir):
    """Rewrite UnrealEditor.modules where it names an older dylib than the newest.

    Returns the list of (module, was, now) it changed."""
    path = os.path.join(bin_dir, "UnrealEditor.modules")
    with open(path) as f:
        data = json.load(f)
    changed = []
    for module, name in data.get("Modules", {}).items():
        newest = newest_dylib(bin_dir, module)
        if newest and newest != name:
            changed.append((module, name, newest))
            data["Modules"][module] = newest
    if changed:
        with open(path, "w") as f:
            json.dump(data, f, indent="\t")
    return changed


def first_errors(output, limit=15):
    lines = [l for l in output.splitlines() if _ERROR.search(l)]
    return lines[:limit] or output.splitlines()[-limit:]


def build(engine, root):
    script = os.path.join(engine, "Build/BatchFiles/Mac/Build.sh")
    proc = subprocess.run([script, "OtherworldEditor", "Mac", "Development",
                           f"-project={uproject()}", "-waitmutex"],
                          capture_output=True, text=True, cwd=root)
    return proc.returncode, proc.stdout + proc.stderr


def run(engine, serve_dir=None, stop_warm=None, wait=60):
    """Close editors, build, fix the modules file. Returns 0 or 1."""
    root = os.path.dirname(uproject())
    if serve_dir and stop_warm:
        stop_warm(serve_dir)
    _closed, left = editors.close_editors()
    deadline = time.time() + wait
    while time.time() < deadline and editors.find_editors():
        time.sleep(1)
    if left or editors.find_editors():
        log("editors of this project are still running; not compiling")
        return 1
    log("compiling OtherworldEditor")
    code, out = build(engine, root)
    if code != 0:
        log(f"compile failed (exit {code}); first errors:")
        print("\n".join(first_errors(out)), flush=True)
        return 1
    for module, was, now in fix_modules(os.path.join(root, "Binaries/Mac")):
        log(f"UnrealEditor.modules named {was} for {module}; now {now}")
    log("compiled")
    return 0
