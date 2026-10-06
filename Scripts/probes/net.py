"""Where a probe runs in a network run, and the board the processes share.

``uepy.py --net`` starts one dedicated server and N clients, and every one of
them runs the same probe files. A probe says where it runs with

    RUNS_ON = ("server", "client")      # every client
    RUNS_ON = ("server", "client 1")    # that client only

(absent: everywhere, and in a single-player --game run too; "standalone"
names that one), and reads where it is from ``p.where``, ``p.is_server``,
``p.client`` (1..N, 0 on the server) and ``p.clients``. A file may define
``probe_server(p)`` and ``probe_client(p)`` instead of one ``probe(p)``.

The processes share nothing but the level, so a step one side waits on is
posted to the board, a directory of small JSON files in the run's folder:

    p.post("shot")                              # on the server
    yield lambda: p.posted("server", "shot")    # on a client

The harness names the process in the environment (uepylib/net_plan.py):

    UEPY_NET_WHERE     "server", "client 1", ...
    UEPY_NET_CLIENTS   N
    UEPY_NET_DIR       the run's folder (the board is under it)
    UEPY_NET_ADDRESS   what a client opens, e.g. 127.0.0.1:17777

Pure Python (no unreal import), unit-tested in Scripts/dev/tests.
"""

import json
import os

SERVER, CLIENT, STANDALONE = "server", "client", "standalone"
# What boot.py posts once the server's level is up: the clients connect then.
LISTENING = "listening"
BOARD = "board"


def _slug(name):
    return name.replace(" ", "")


class Where(object):
    """One process of a run: its role, its number, and the run's board."""

    def __init__(self, role=STANDALONE, index=0, clients=0, directory=None, address=""):
        self.role, self.index, self.clients = role, index, clients
        self.directory, self.address = directory, address
        self._memory = {}

    @classmethod
    def from_env(cls, env):
        """This process's Where; a standalone one outside a network run."""
        name = (env.get("UEPY_NET_WHERE") or "").strip()
        if not name:
            return cls()
        role, _, number = name.partition(" ")
        if role not in (SERVER, CLIENT) or (role == CLIENT) != number.isdigit():
            raise ValueError(f"UEPY_NET_WHERE={name!r}: expected 'server' or 'client <n>'")
        return cls(role, int(number or 0), int(env.get("UEPY_NET_CLIENTS") or 0),
                   env.get("UEPY_NET_DIR") or None, env.get("UEPY_NET_ADDRESS") or "")

    @property
    def name(self):
        return f"{CLIENT} {self.index}" if self.role == CLIENT else self.role

    @property
    def networked(self):
        return self.role != STANDALONE

    def matches(self, runs_on):
        """Does a probe declaring ``RUNS_ON = runs_on`` run in this process?"""
        if runs_on is None:
            return True
        if isinstance(runs_on, str):
            runs_on = (runs_on,)
        return any(entry in (self.role, self.name) for entry in runs_on)

    # ─── the board ──────────────────────────────────────────────────────────

    def _path(self, where_name, key):
        return os.path.join(self.directory, BOARD, f"{_slug(where_name)}.{key}.json")

    def post(self, key, value=True):
        """Say ``key`` (with a JSON value) to every process of the run."""
        if not self.directory:
            self._memory[key] = value
            return
        path = self._path(self.name, key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(value, fh)
        os.replace(path + ".tmp", path)

    def posted(self, where_name, key):
        """What the process named ``where_name`` posted as ``key``, or None."""
        if not self.directory:
            return self._memory.get(key) if where_name == self.name else None
        try:
            with open(self._path(where_name, key), encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return None


def pick_probe(namespace, where):
    """The function of a probe file that runs here: ``probe_<role>``, else
    ``probe``. None when the file has neither."""
    fn = namespace.get(f"probe_{where.role}") or namespace.get("probe")
    return fn if callable(fn) else None
