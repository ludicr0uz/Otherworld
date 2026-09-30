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
second one waits for the heartbeat instead of starting a rival editor.
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


def _wait_for_beat(directory, alive, timeout):
    """Wait for a heartbeat while ``alive()`` holds."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if inbox.heartbeat(directory):
            return True
        if not alive():
            return False
        time.sleep(0.25)
    return False


def ensure(engine, directory, boot_timeout=300):
    """A listening server on ``directory``, booting one if needed. True if
    one is listening when this returns."""
    os.makedirs(directory, exist_ok=True)
    if inbox.heartbeat(directory):
        return True
    if not _claim_boot(directory):
        log("warm editor: another call is booting it; waiting")
        booter = os.path.join(directory, BOOTING)
        return _wait_for_beat(
            directory, lambda: inbox.pid_alive(_read_pid(booter)) or inbox.heartbeat(directory),
            boot_timeout)
    try:
        for leftover in (STOP, "heartbeat"):
            try:
                os.remove(os.path.join(directory, leftover))
            except OSError:
                pass
        driver = os.path.join(directory, "serve_driver.py")
        with open(driver, "w", encoding="utf-8") as fh:
            fh.write(DRIVER)
        env = dict(os.environ, UEPY_INBOX_DIR=directory)
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
