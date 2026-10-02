"""A warm headless editor of one's own, serving an inbox until told to stop.

A cold run pays a 20-40 s boot per call, whatever the script does; dev-team
sessions made ~15 such calls a task, so booting was over a quarter of their
wall time. Under $UEPY_SERVE=<dir> the first uepy call boots one
``UnrealEditor-Cmd`` that runs ``uepy_inbox.serve()`` on <dir> and outlives
the call (its own process group); every later call is an inbox job, in about
the time the script itself takes.

It is private to its caller: it polls <dir>, never Saved/uepy, so nothing the
user's editor is sent reaches it and nothing it is sent reaches the user's.
``stop()`` asks it to exit (a ``stop`` file) and kills it only if it does not.

Only one boots at a time: the first caller holds ``booting`` (its pid) and a
second one waits for the heartbeat instead of starting a rival editor. And
only one runs at a time: an editor that is still there but no longer answers
(crashed into its handler, or hung) is killed before another is booted, so two
never serve one inbox.

"Up" means ``serve()``'s own heartbeat (``"serving": true``). The editor is
started with $UEPY_SERVING, which keeps uepy_inbox's Slate-tick listener out
of it: that listener used to beat and take the first job during start-up.
"""

import os
import signal
import subprocess
import time

from uepylib import inbox
from uepylib.paths import editor_cmd, log, uproject

DRIVER = '''
import os, sys
import unreal
sys.path.insert(0, os.path.join(unreal.Paths.convert_relative_path_to_full(
    unreal.Paths.project_dir()), "Content", "Python"))
import uepy_inbox
uepy_inbox.serve()
'''

BOOTING = "booting"
STOP = "stop"
PID = "server.pid"
STOP_SECONDS = 60.0


def _read_pid(path):
    try:
        with open(path) as fh:
            return int(fh.read().strip())
    except (OSError, ValueError):
        return None


def _claim_boot(directory):
    """True if this caller may boot; False if another live caller is booting."""
    lock = os.path.join(directory, BOOTING)
    for _ in range(2):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            owner = _read_pid(lock)
            if owner is not None and inbox.pid_alive(owner):
                return False
            os.remove(lock)          # left by a caller that died mid-boot
            continue
        with os.fdopen(fd, "w") as fh:
            fh.write(str(os.getpid()))
        return True
    return False


def _serving(directory):
    """The heartbeat of a serve() loop on ``directory``, or None."""
    beat = inbox.heartbeat(directory)
    return beat if beat and beat.get("serving") else None


def _wait_for_beat(directory, alive, timeout):
    """Wait for serve()'s heartbeat while ``alive()`` holds."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _serving(directory):
            return True
        if not alive():
            return False
        time.sleep(0.25)
    return False


def ensure(engine, directory, boot_timeout=300):
    """A listening server on ``directory``, booting one if needed. True if
    one is listening when this returns."""
    os.makedirs(directory, exist_ok=True)
    if _serving(directory):
        return True
    if not _claim_boot(directory):
        log("warm editor: another call is booting it; waiting")
        booter = os.path.join(directory, BOOTING)
        return _wait_for_beat(
            directory, lambda: inbox.pid_alive(_read_pid(booter)) or _serving(directory),
            boot_timeout)
    try:
        gone = discard(directory)
        if gone:
            log(f"warm editor: pid {gone} was still there but not answering; killed it")
        for leftover in (STOP, "heartbeat"):
            try:
                os.remove(os.path.join(directory, leftover))
            except OSError:
                pass
        driver = os.path.join(directory, "serve_driver.py")
        with open(driver, "w", encoding="utf-8") as fh:
            fh.write(DRIVER)
        env = dict(os.environ, UEPY_INBOX_DIR=directory, UEPY_SERVING="1")
        env.pop("UEPY_SERVE", None)
        started = time.time()
        log(f"warm editor: booting one for this session ({directory})")
        # A file, never a pipe, for the same reason as cold.py; and its own
        # session, so it outlives this call and a Ctrl-C of the caller.
        with open(os.path.join(directory, "server.log"), "w") as sink:
            proc = subprocess.Popen(
                [editor_cmd(engine), uproject(), f"-ExecutePythonScript={driver}",
                 "-NoUI", "-stdout"],
                stdout=sink, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                env=env, start_new_session=True)
        with open(os.path.join(directory, PID), "w") as fh:
            fh.write(str(proc.pid))
        # poll(), not the pid: a child that died is a zombie, and a zombie's pid
        # still answers kill(0).
        up = _wait_for_beat(directory, lambda: proc.poll() is None, boot_timeout)
        if up:
            log(f"warm editor: pid {proc.pid} up in {time.time() - started:.0f}s; "
                "later calls reuse it")
        else:
            log(f"warm editor: did not come up (see {directory}/server.log)")
            if proc.poll() is None:
                _kill(proc.pid)
                proc.wait()
        return up
    finally:
        try:
            os.remove(os.path.join(directory, BOOTING))
        except OSError:
            pass


def _kill(pid):
    for sig, wait in ((signal.SIGTERM, 20.0), (signal.SIGKILL, 5.0)):
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            return
        deadline = time.time() + wait
        while time.time() < deadline and inbox.pid_alive(pid):
            time.sleep(0.25)
        if not inbox.pid_alive(pid):
            return


def _is_server(pid, directory):
    """True if ``pid`` is an editor serving ``directory``: its command line
    names the driver in it. A pid file outlives its process, and the number
    may by now belong to something else."""
    ps = subprocess.run(["ps", "-o", "command=", "-p", str(pid)],
                        capture_output=True, text=True)
    return "UnrealEditor" in ps.stdout and directory in ps.stdout


def discard(directory, is_server=_is_server):
    """Kill the editor recorded for ``directory`` if its process is still
    there, without asking: for one that crashed or hung, where there is nothing
    left to save and SIGTERM is not answered. Returns its pid, or None if
    there was nothing to kill."""
    pid = _read_pid(os.path.join(directory, PID))
    if pid is None or not inbox.pid_alive(pid) or not is_server(pid, directory):
        return None
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return None
    deadline = time.time() + 10.0
    while time.time() < deadline and inbox.pid_alive(pid):
        try:
            os.waitpid(pid, os.WNOHANG)      # reap it if it is this caller's child
        except OSError:
            pass
        time.sleep(0.1)
    for leftover in ("heartbeat", PID):
        try:
            os.remove(os.path.join(directory, leftover))
        except OSError:
            pass
    return pid


def stop(directory, seconds=STOP_SECONDS):
    """Ask the server on ``directory`` to exit; kill it if it will not.
    True if one was running."""
    pid = _read_pid(os.path.join(directory, PID))
    if pid is None or not inbox.pid_alive(pid):
        return False
    with open(os.path.join(directory, STOP), "w"):
        pass
    deadline = time.time() + seconds
    while time.time() < deadline and inbox.pid_alive(pid):
        time.sleep(0.25)
    if inbox.pid_alive(pid):
        log(f"warm editor: pid {pid} did not stop on request; terminating it")
        _kill(pid)
    return True
