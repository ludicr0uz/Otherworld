"""What dev-team itself is doing, said at the terminal with the time, and kept.

``step`` prints one line stamped with the clock time, for the slow steps that
would otherwise leave the terminal quiet: a sweep starting, a probe launch,
a session beginning. ``Tee`` mirrors everything printed from then on (the
steps, the session narration, the write-ups) into the run's ``run.log``, so a
run can be read back after the terminal has scrolled away.
"""

import datetime
import os
import sys


def clock(when=None):
    return (when or datetime.datetime.now()).strftime("%H:%M:%S")


def step(text, indent="    "):
    """One timestamped progress line."""
    print(f"{indent}{clock()}  {text}", flush=True)


def shown(path, root):
    """A path as a step line shows it: relative to the project when it is
    inside it, as given otherwise."""
    rel = os.path.relpath(path, root)
    return path if rel.startswith("..") else rel


class Tee(object):
    """A stdout that also appends to a file; ``with Tee(path):`` installs it."""

    def __init__(self, path):
        self.path, self.inner, self.fh = path, None, None

    def write(self, text):
        self.inner.write(text)
        try:
            self.fh.write(text)
        except (OSError, ValueError):
            pass
        return len(text)

    def flush(self):
        self.inner.flush()
        try:
            self.fh.flush()
        except (OSError, ValueError):
            pass

    def isatty(self):
        return self.inner.isatty()

    def fileno(self):
        return self.inner.fileno()

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def __enter__(self):
        self.inner, self.fh = sys.stdout, open(self.path, "a")
        sys.stdout = self
        return self

    def __exit__(self, *exc):
        sys.stdout = self.inner
        self.fh.close()
        return False
