"""The before-sweep's result kept on disk, so it survives across dev-team runs.

Keyed by the tree's state (HEAD plus the uncommitted changes, ``work.tree_state``)
hashed to one string: an unchanged tree's sweep is not run again. One entry only,
the latest, because a tree that moved on does not come back.
"""
import hashlib
import json
import os

PATH_PARTS = ("Saved", "DevTeam", "baseline_cache.json")


def path(root):
    return os.path.join(root, *PATH_PARTS)


def key(state):
    """``state`` is the tuple (HEAD, porcelain status) of work.tree_state."""
    digest = hashlib.sha1()
    for part in state:
        digest.update(part.encode("utf-8", "replace") + b"\0")
    return digest.hexdigest()


def load(root, state):
    """The cached rows for this tree state, or None."""
    try:
        with open(path(root)) as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("key") != key(state):
        return None
    rows = data.get("rows")
    return rows if isinstance(rows, dict) and rows else None


def save(root, state, rows):
    if not rows:
        return
    target = path(root)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    tmp = target + ".tmp"
    with open(tmp, "w") as fh:
        json.dump({"key": key(state), "rows": rows}, fh)
    os.replace(tmp, target)
