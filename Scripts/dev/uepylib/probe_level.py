"""Which level a probe runs on.

A probe run boots ``PROBE_MAP`` (the small ``Lvl_Probe_50m``) unless the probe
declares ``LEVEL = "/Game/Maps/..."`` at module level, or ``--map`` is given
(which wins for every probe). Probes that share a level share one launch; the
declaration is read from the source, so nothing is imported.
"""

import ast

from uepylib import game

PROBE_MAP = "/Game/Maps/Lvl_Probe_50m"


def declared(path):
    """The probe file's ``LEVEL``, or None."""
    try:
        with open(path, encoding="utf-8") as fh:
            body = ast.parse(fh.read()).body
    except (OSError, SyntaxError):
        return None
    for node in body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "LEVEL" for t in node.targets):
            try:
                return ast.literal_eval(node.value)
            except ValueError:
                return None
    return None


def by_level(probes, explicit=None):
    """[(level, [probe paths])] in first-seen order. No probes: the plain
    smoke run's level (``explicit`` or the old default)."""
    if not probes:
        return [(explicit or game.DEFAULT_MAP, [])]
    groups = {}
    for p in probes:
        groups.setdefault(explicit or declared(p) or PROBE_MAP, []).append(p)
    return list(groups.items())
