"""The before-sweep's result kept on disk, so it survives across dev-team runs.

Keyed by the tree's state (HEAD plus the uncommitted changes, ``work.tree_state``)
and the probe set the sweep ran (its ``probe:`` labels), hashed to one string: an
unchanged tree's sweep is not run again, and a baseline swept under one probe set
is never the baseline of a run under another. One entry only, the latest, because
a tree that moved on does not come back.
"""
import hashlib
import json
import os

PATH_PARTS = ("Saved", "DevTeam", "baseline_cache.json")


def path(root):
    return os.path.join(root, *PATH_PARTS)


def key(state, probes=()):
    """``state`` is the tuple (HEAD, porcelain status) of work.tree_state;
    ``probes`` the labels of the probe set swept with it (none: verifiers only)."""
    digest = hashlib.sha1()
    for part in (*state, "probes:", *sorted(probes)):
        digest.update(part.encode("utf-8", "replace") + b"\0")
    return digest.hexdigest()


def load(root, state, probes=()):
    """The cached rows for this tree state and probe set, or None."""
    try:
        with open(path(root)) as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("key") != key(state, probes):
        return None
    rows = data.get("rows")
    return rows if isinstance(rows, dict) and rows else None


def save(root, state, rows, probes=()):
    if not rows:
        return
    target = path(root)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    tmp = target + ".tmp"
    with open(tmp, "w") as fh:
        json.dump({"key": key(state, probes), "rows": rows}, fh)
    os.replace(tmp, target)
