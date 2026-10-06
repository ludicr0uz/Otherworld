"""What a network run starts: one dedicated server and N clients.

Pure: the processes' names, command lines and environments, and the checks on
``--net``'s arguments. net.py starts what this describes; Scripts/probes/net.py
reads the environment back inside each process.

Every process is the editor binary, booted into the empty Entry map, where
Scripts/probes/boot.py takes over: the server opens the level and a client,
once the server listens, opens its address (game.py says why Entry first).
"""

import os

from uepylib.game import ENTRY_URL, render_args

HOST = "127.0.0.1"
# Not the engine's 7777: a run never meets a server someone left up.
DEFAULT_PORT = 17777
# Each client is a whole editor binary, 3-5 GB of it (serversupportsysdesign.md 5).
MAX_CLIENTS = 8
SERVER, CLIENT = "server", "client"
# Windowed clients step down the screen, so each one's title bar shows.
WINDOW_STEP = 60


class Process(object):
    """One process of the run: who it is, and where its files go."""

    def __init__(self, role, index, run_dir):
        self.role, self.index = role, index
        self.name = f"{CLIENT} {index}" if role == CLIENT else SERVER
        slug = self.name.replace(" ", "")
        self.log = os.path.join(run_dir, f"{slug}.log")
        self.results = os.path.join(run_dir, f"{slug}.json")
        self.inbox = os.path.join(run_dir, f"inbox-{slug}")


def check_args(clients, port, seconds=None):
    """The reason ``--net``'s arguments cannot run, or None."""
    if clients < 1:
        return "--net needs at least one client (--clients N)"
    if clients > MAX_CLIENTS:
        return (f"--clients {clients}: at most {MAX_CLIENTS}, each one is an editor "
                f"binary's worth of memory")
    if not 1024 <= port <= 65535:
        return f"--port {port}: expected 1024-65535"
    if seconds is not None and seconds < 1:
        return f"--seconds {seconds}: expected a positive number"
    return None


def processes(run_dir, clients):
    """The server, then client 1..N."""
    return [Process(SERVER, 0, run_dir)] + [
        Process(CLIENT, i, run_dir) for i in range(1, clients + 1)]


def command(editor, project, process, port, windowed=False):
    """The process's command line."""
    if process.role == SERVER:
        how = ["-server", f"-port={port}"]
    else:
        how = ["-game", *render_args(windowed)]
        if windowed:
            offset = WINDOW_STEP * (process.index - 1)
            how += [f"-WinX={offset}", f"-WinY={offset}"]
    # -nomenu: nobody is there to press Enter on the title menu (game.py).
    return [editor, project, ENTRY_URL, *how, "-unattended", "-nomenu",
            "-forcelogflush", f"-abslog={process.log}"]


def environment(base, process, run_dir, clients, port, level, probes, probe_timeout=None):
    """The process's environment: who it is, and the probes it is to run."""
    env = dict(base)
    # A process started from inside a serving editor's shell is not that editor.
    for inherited in ("UEPY_SERVE", "UEPY_SERVING"):
        env.pop(inherited, None)
    env["UEPY_INBOX_DIR"] = process.inbox
    env["UEPY_NET_WHERE"] = process.name
    env["UEPY_NET_CLIENTS"] = str(clients)
    env["UEPY_NET_DIR"] = run_dir
    env["UEPY_NET_ADDRESS"] = f"{HOST}:{port}"
    env["UEPY_PROBES"] = os.pathsep.join(probes)
    env["UEPY_PROBE_MAP"] = level
    env["UEPY_PROBE_RESULTS"] = process.results
    if probe_timeout:
        env["UEPY_PROBE_TIMEOUT"] = str(probe_timeout)
    return env
