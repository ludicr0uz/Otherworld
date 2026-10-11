"""Keep the Mac awake for the length of a run.

An unattended run is only as fast as the machine stays awake. The run of
2026-10-11 lost the night to idle sleep: the Mac dozed off ten seconds after
the third task's first turns, woke for a minute every 15 minutes to do its
own maintenance, and the session got one model turn per wake. So dev-team
holds an idle-sleep assertion on itself for as long as it runs: ``caffeinate
-i -w <pid>`` (prevent idle system sleep, exit when that pid does). The
display may still sleep, and a closed lid still sleeps the machine unless it
is on power with an external display; neither is this module's business.

``hold()`` is a context manager. Without caffeinate (not macOS), or if it
fails to start, it does nothing and says so once.
"""
import contextlib
import os
import shutil
import subprocess

TOOL = "caffeinate"


def start(pid=None, tool=None):
    """The caffeinate process holding the assertion for ``pid`` (this process),
    or None when there is no caffeinate to run."""
    path = shutil.which(tool or TOOL)
    if not path:
        return None
    try:
        return subprocess.Popen([path, "-i", "-w", str(pid or os.getpid())],
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
    except OSError:
        return None


@contextlib.contextmanager
def hold(say=print, tool=None):
    """Hold the Mac awake for the block. ``say`` gets the one line about it."""
    proc = start(tool=tool)
    if proc is None:
        say("dev-team: no caffeinate here -- the machine may sleep during the run")
    else:
        say(f"dev-team: holding the Mac awake for the run ({TOOL} pid {proc.pid})")
    try:
        yield proc
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
