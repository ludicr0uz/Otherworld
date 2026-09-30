"""Cold runs: one UnrealEditor-Cmd boot for N scripts.

A boot costs 35-45 s regardless of the script, so every target of one call
shares a single boot. The driver brackets each target with marker lines, which
``split_targets()`` uses to hand each one its own slice of the log -- so a cold
run reports per target exactly like the inbox does.
"""

import os
import re
import subprocess
import tempfile
import time

from uepylib.paths import editor_cmd, log, uproject
from uepylib.summary import clean
from uepylib.targets import TargetResult, label_for

START = "[uepy] === "
END = "[uepy] --- "

# runpy with run_name="__main__" so a script whose work sits behind
# `if __name__ == "__main__":` still does it -- which most builders here do.
# The markers go through unreal.log_warning: in a cold run print() never
# reaches the log, so a printed marker is simply not there to split on.
DRIVER = '''
import runpy, time, traceback
import unreal
TARGETS = {targets!r}
for kind, value, label in TARGETS:
    unreal.log_warning({start!r} + label)
    started, ok = time.time(), True
    try:
        if kind == "file":
            runpy.run_path(value, run_name="__main__")
        else:
            exec(compile(value, "<uepy>", "exec"), {{"__name__": "__main__"}})
    except SystemExit as exc:
        ok = not exc.code
    except Exception:
        unreal.log_error(traceback.format_exc())
        ok = False
    unreal.log_warning({end!r} + label + (" ok " if ok else " FAILED ")
                       + "%.1f" % (time.time() - started))
'''

_END_LINE = re.compile(re.escape(END) + r"(.*) (ok|FAILED) ([\d.]+)\s*$")


def split_targets(text, labels):
    """Per-target TargetResults from a cold log, in ``labels`` order.

    A target whose end marker never printed (the editor died under it) failed
    and gets everything logged after its start; a target that never started
    failed with the tail of the boot log, which is where the reason will be.
    """
    lines = text.splitlines()
    found = []
    current, chunk = None, []
    for line in lines:
        stripped = clean(line).strip()
        if stripped.startswith(START) and current is None:
            current, chunk = stripped[len(START):], []
            continue
        m = _END_LINE.search(stripped) if current is not None else None
        if m and m.group(1) == current:
            ok = m.group(2) == "ok" and "Traceback (most recent call last)" not in "\n".join(chunk)
            found.append(TargetResult(current, ok, float(m.group(3)), "\n".join(chunk)))
            current = None
            continue
        if current is not None:
            chunk.append(line)
    if current is not None:
        found.append(TargetResult(current, False, 0.0,
                                  "\n".join(chunk + ["(the run ended mid-script)"])))
    tail = "\n".join(lines[-40:])
    out = []
    for label in labels:
        match = next((r for r in found if r.label == label), None)
        if match is not None:
            found.remove(match)
        out.append(match or TargetResult(
            label, False, 0.0, "(never started -- end of the boot log:)\n" + tail))
    return out


def run_cold(engine, targets, report, boot_timeout=900):
    """Boot once, run every target, report each. Returns the full log text."""
    binary = editor_cmd(engine)
    tmp = tempfile.mkdtemp(prefix="uepy-")
    labelled = [(kind, value, label_for(kind, value)) for kind, value in targets]
    driver = os.path.join(tmp, "uepy_driver.py")
    with open(driver, "w", encoding="utf-8") as fh:
        fh.write(DRIVER.format(targets=labelled, start=START, end=END))
    log(f"cold boot ({len(targets)} script(s), one launch)")
    started = time.time()
    # Log to a FILE, never to a pipe. subprocess pipes deadlock here: the editor
    # hands its inherited stdout to long-lived helpers (UnrealEditorServices and
    # friends) that outlive the run, so capture_output=True waits for an EOF
    # that never comes. A file has no such failure mode.
    outfile = os.path.join(tmp, "cold.log")
    with open(outfile, "w") as sink:
        proc = subprocess.Popen(
            [binary, uproject(), f"-ExecutePythonScript={driver}", "-NoUI", "-stdout"],
            stdout=sink, stderr=subprocess.STDOUT)
        try:
            proc.wait(timeout=boot_timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            log(f"cold run exceeded {boot_timeout}s and was killed")
    with open(outfile, errors="replace") as fh:
        text = fh.read()
    for result in split_targets(text, [label for _k, _v, label in labelled]):
        report(result)
    log(f"cold run finished in {time.time() - started:.0f}s")
    return text
