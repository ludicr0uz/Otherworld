"""The before-sweep's result kept on disk, so it survives across dev-team runs.

An entry is the sweep's rows, the tree snapshot it was swept on (devteam/scope:
every file and its hash), the probe set it ran (its ``probe:`` labels) and
when. ``load`` gives the rows back with the paths that changed since: none, and
the sweep is not run again; some, and the gate sweeps only the suites those
paths reach (scope.suites_for) and carries the other rows forward. The key
is the relevant files alone (scope.relevant), so a commit that touches only
docs, Scripts/dev, probes or a task file is the same tree to the gate.

A stale carry-forward cannot live longer than one night: an entry older than
MAX_AGE_S is a miss, and so is one swept under another probe set. One entry
only, the latest, because a tree that moved on does not come back.
"""
import hashlib
import json
import os
import time

from devteam import scope

PATH_PARTS = ("Saved", "DevTeam", "baseline_cache.json")
MAX_AGE_S = 24 * 3600


def path(root):
    return os.path.join(root, *PATH_PARTS)


def key(files, probes=()):
    """``files`` is a scope.snapshot; ``probes`` the labels of the probe set
    swept with it (none: verifiers only). Only the relevant files count."""
    digest = hashlib.sha1()
    for part in (*(f"{p}={h}" for p, h in sorted(scope.relevant(files).items())),
                 "probes:", *sorted(probes)):
        digest.update(part.encode("utf-8", "replace") + b"\0")
    return digest.hexdigest()


def load(root, files, probes=(), now=None, max_age_s=None):
    """(rows, changed paths) for this probe set, or None: no entry, a corrupt
    one, another probe set, or one older than ``max_age_s`` (MAX_AGE_S).
    ``changed`` is empty when the relevant files are as they were."""
    if max_age_s is None:
        max_age_s = MAX_AGE_S
    try:
        with open(path(root)) as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("probes") != sorted(probes):
        return None
    rows, kept = data.get("rows"), data.get("files")
    if not (isinstance(rows, dict) and rows and isinstance(kept, dict)):
        return None
    if (now or time.time()) - float(data.get("when") or 0) > max_age_s:
        return None
    if data.get("key") == key(files, probes):
        return rows, []
    return rows, [p for p in scope.changed(kept, files) if scope.suites_for([p]) != set()]


def exact(root, files, probes=(), now=None):
    """The rows when the relevant files are as they were, else None."""
    hit = load(root, files, probes, now)
    return hit[0] if hit and not hit[1] else None


def save(root, files, rows, probes=(), now=None):
    if not rows:
        return
    target = path(root)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    tmp = target + ".tmp"
    with open(tmp, "w") as fh:
        json.dump({"key": key(files, probes), "probes": sorted(probes), "rows": rows,
                   "files": files, "when": now or time.time()}, fh)
    os.replace(tmp, target)
