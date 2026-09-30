"""The probe driver: advances probe generators one game tick at a time.

Pure Python with no ``unreal`` import, so the whole waiting and recording
logic is unit-tested off-engine (Scripts/dev/tests/test_probe_runner.py). The
in-game side (boot.py) only supplies the two clocks and calls ``advance()``
from the Slate tick.

Why generators: a probe runs on the game thread inside a tick callback, so it
can never block to wait for the game -- a ``time.sleep`` there freezes the very
world it is waiting on. Yielding hands the tick back, and the driver resumes
the probe when its wait is over:

    yield 0.3                  0.3 s of *game* time (the world clock; in a
                               -nullrhi run it lags the wall clock badly)
    yield lambda: hc_dead()    until the callable returns something truthy

Every wait is bounded by the probe's wall-clock ``timeout``, so a condition
that never comes true fails the probe instead of hanging the run.
"""

import traceback

DEFAULT_TIMEOUT = 60.0      # wall seconds for one probe, waits included
DETAIL_LIMIT = 300          # characters of detail kept per check


def _short(value):
    text = str(value)
    return text if len(text) <= DETAIL_LIMIT else text[:DETAIL_LIMIT - 3] + "..."


class Ledger(object):
    """What one probe found: its checks, its notes, and a fatal error if any."""

    def __init__(self, name):
        self.name = name
        self.checks = []
        self.notes = []
        self.error = None

    def check(self, label, ok, detail=""):
        """Record one result. Returns ``ok`` so a probe can branch on it."""
        ok = bool(ok)
        self.checks.append({"ok": ok, "label": label, "detail": _short(detail)})
        return ok

    def note(self, text):
        self.notes.append(_short(text))

    @property
    def passed(self):
        return self.error is None and all(c["ok"] for c in self.checks)

    def as_dict(self):
        return {"name": self.name, "checks": list(self.checks),
                "notes": list(self.notes), "error": self.error}


class ProbeRun(object):
    """One probe: a generator factory plus the state of its current wait."""

    def __init__(self, ledger, factory, game_time, wall_time,
                 timeout=DEFAULT_TIMEOUT):
        self.ledger = ledger
        self._factory = factory
        self._game_time = game_time
        self._wall_time = wall_time
        self._timeout = timeout
        self._gen = None
        self._wait = None           # (kind, value, description)
        self._started = None
        self.done = False

    def _fail(self, message):
        self.ledger.error = message
        self.done = True
        # Close the generator, so a probe's `finally` (putting a file back,
        # say) runs on a timeout or an error too, not only on a clean finish.
        if self._gen is not None:
            try:
                self._gen.close()
            except Exception:
                pass

    def _set_wait(self, value):
        if callable(value):
            self._wait = ("until", value, getattr(value, "__name__", "condition"))
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            self._wait = ("time", self._game_time() + float(value), f"{value} s")
        elif value is None:
            self._wait = ("time", self._game_time(), "one tick")
        else:
            raise TypeError(f"a probe may yield seconds or a callable, not {value!r}")

    def _waiting(self):
        """True while the current wait is still in force."""
        if self._wait is None:
            return False
        kind, value, _desc = self._wait
        if kind == "time":
            return self._game_time() < value
        return not value()

    def advance(self):
        """Do at most one step. Returns True once the probe has finished."""
        if self.done:
            return True
        try:
            if self._gen is None:
                self._started = self._wall_time()
                result = self._factory()
                if not hasattr(result, "send"):      # a plain function: ran already
                    self.done = True
                    return True
                self._gen = result
                self._set_wait(self._gen.send(None))
                return False
            if self._wall_time() - self._started > self._timeout:
                desc = self._wait[2] if self._wait else "?"
                self._fail(f"timed out after {self._timeout:.0f} s "
                           f"(waiting for {desc})")
                return True
            if self._waiting():
                return False
            self._set_wait(self._gen.send(None))
            return False
        except StopIteration:
            self.done = True
            return True
        except Exception:
            self._fail(traceback.format_exc(limit=6).strip())
            return True


class Queue(object):
    """Runs probes one after another. ``advance()`` is called once per tick."""

    def __init__(self, runs):
        self.runs = list(runs)
        self._index = 0

    @property
    def done(self):
        return self._index >= len(self.runs)

    def advance(self):
        while not self.done:
            if not self.runs[self._index].advance():
                return False
            self._index += 1
        return True

    def results(self):
        return [r.ledger.as_dict() for r in self.runs]
