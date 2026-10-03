"""Find and close the project's running editors.

An unattended session must not share the project with an open editor: builds
pushed into it can time out mid-save or crash it (a dev-team run segfaulted
the user's editor that way), and a cold build next to it writes packages the
editor then overwrites with its stale copies. dev-team therefore closes every
editor of this project before it starts work.

Closing is graceful first: an editor listening on the inbox is asked to save
its dirty packages and quit, so nothing the user had open is lost. Only an
editor that does not answer -- or has no inbox -- gets SIGTERM, then SIGKILL.
Leftover UnrealEditor-Cmd processes (cold runs, -game runs) go straight to
SIGTERM. UnrealEditorServices is a shared helper, never a match.
"""

import os
import re
import signal
import subprocess
import time

from uepylib import inbox
from uepylib.paths import editor_inbox, log, uproject

# The binary's basename must end right there: UnrealEditorServices is not one.
_BINARY = re.compile(r"/(UnrealEditor(?:-Cmd)?)(?=\s|$)")

# A dirty level is saved without its RecastNavMesh: the editor re-creates one
# on open, and a game that loads a saved one never builds a tile
# (Scripts/world/level_save.py).
QUIT_JOB = """
import unreal
_world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
if _world and _world.get_outermost().is_dirty():
    _sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for _a in [a for a in _sub.get_all_level_actors() if isinstance(a, unreal.RecastNavMesh)]:
        _sub.destroy_actor(_a)
saved = unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
unreal.log_warning(f"[uepy] saved dirty packages: {saved}; quitting")
unreal.SystemLibrary.quit_editor()
"""

GRACEFUL_SECONDS = 90.0     # a save of a big level can take a while
TERM_SECONDS = 20.0


class EditorProcess(object):

    def __init__(self, pid, binary, command):
        self.pid, self.binary, self.command = pid, binary, command

    @property
    def is_ui(self):
        return self.binary == "UnrealEditor"

    def __repr__(self):
        return f"EditorProcess({self.pid}, {self.binary})"


def parse_ps(text, project_path, extra_pids=()):
    """Editor processes in ``ps -axo pid=,command=`` output that belong to the
    project: its .uproject is on the command line, or the pid is one the
    inbox heartbeat named (an editor opened from the launcher may carry no
    project argument)."""
    found = []
    for line in text.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2 or not parts[0].isdigit():
            continue
        pid, command = int(parts[0]), parts[1]
        m = _BINARY.search(command)
        if not m:
            continue
        if project_path in command or pid in extra_pids:
            found.append(EditorProcess(pid, m.group(1), command))
    return found


def _wait_gone(pid, seconds):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if not inbox.pid_alive(pid):
            return True
        time.sleep(0.5)
    return not inbox.pid_alive(pid)


def find_editors():
    beat = inbox.heartbeat(editor_inbox())
    extra = {int(beat["pid"])} if beat and str(beat.get("pid", "")).isdigit() else set()
    ps = subprocess.run(["ps", "-axo", "pid=,command="], capture_output=True, text=True)
    return [p for p in parse_ps(ps.stdout, uproject(), extra) if p.pid != os.getpid()]


def _ask_to_quit(proc):
    """Save-and-quit through the inbox. True if the editor then exited."""
    beat = inbox.heartbeat(editor_inbox())
    if not beat or beat.get("pid") != proc.pid:
        return False
    if beat.get("pie"):
        log(f"editor {proc.pid} is in PIE; asking it to quit anyway")
    inbox.send(editor_inbox(), "code", QUIT_JOB, allow_pie=True)
    log(f"asked editor {proc.pid} to save its dirty packages and quit")
    return _wait_gone(proc.pid, GRACEFUL_SECONDS)


def _signal(proc):
    for sig, wait in ((signal.SIGTERM, TERM_SECONDS), (signal.SIGKILL, 5.0)):
        try:
            os.kill(proc.pid, sig)
        except ProcessLookupError:
            return True
        if _wait_gone(proc.pid, wait):
            return True
    return False


def close_editors():
    """Close every editor of this project. Returns (closed, still_running)."""
    closed, left = [], []
    for proc in find_editors():
        how = "quit"
        if not (proc.is_ui and _ask_to_quit(proc)):
            how = "signalled"
            if proc.is_ui:
                log(f"editor {proc.pid} did not quit on request -- terminating "
                    "it (unsaved changes may be lost)")
            if not _signal(proc):
                left.append(proc)
                continue
        log(f"closed {proc.binary} {proc.pid} ({how})")
        closed.append(proc)
    return closed, left
