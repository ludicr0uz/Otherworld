"""The latest result of every probe that has run, kept across dev-team runs.

Saved/DevTeam/probe_status.json holds one entry per probe: when it last ran,
the commit the tree was on (and whether it had uncommitted changes), and how
it did. It is written after every probe launch dev-team makes, in a task's
gate or in the final sweep, and after a session's ``uepy.py --probes-for``
(ok/FAIL only, no counts), and read as the final sweep's "before" when the
run has no baseline sweep of its own (dev-team without --check-baseline), so
a run need not sweep the probes twice to know what newly fails.
``dev-team probes`` prints it.
"""

import datetime
import json
import os

from devteam.probe_gate import PREFIX

PATH_PARTS = ("Saved", "DevTeam", "probe_status.json")


def path(root):
    return os.path.join(root, *PATH_PARTS)


def load(root):
    """{probe name: entry}, or {} when there is no record yet."""
    try:
        with open(path(root)) as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def update(root, rows, head, dirty=False, when=None):
    """Record the probe rows of a sweep (verifier rows are passed over).
    Returns the record as it is now."""
    record = load(root)
    stamp = (when or datetime.datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    for label, row in (rows or {}).items():
        if not label.startswith(PREFIX) or not isinstance(row, dict):
            continue
        record[label[len(PREFIX):]] = {
            "when": stamp, "head": head or "?", "dirty": bool(dirty),
            "ok": bool(row.get("ok")), "passed": row.get("passed"),
            "failed": row.get("failed"),
            "failures": list(row.get("failures") or [])[:5],
        }
    target = path(root)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target + ".tmp", "w") as fh:
        json.dump(record, fh, indent=1, sort_keys=True)
    os.replace(target + ".tmp", target)
    return record


def as_rows(record, labels):
    """The record as sweep rows, for the labels it holds."""
    rows = {}
    for label in labels:
        entry = record.get(label[len(PREFIX):]) if label.startswith(PREFIX) else None
        if entry:
            rows[label] = {"ok": entry.get("ok", False), "passed": entry.get("passed") or 0,
                           "failed": entry.get("failed") or 0,
                           "failures": list(entry.get("failures") or [])}
    return rows


def describe(record, labels):
    """A noun phrase: what the record holds of ``labels``, and from when."""
    held = [record[l[len(PREFIX):]] for l in labels if l[len(PREFIX):] in record]
    if not held:
        return f"probe record, which holds no result for any of the {len(labels)} probe(s)"
    whens = sorted(e.get("when", "") for e in held)
    heads = sorted({e.get("head", "?") for e in held})
    span = whens[0] if whens[0] == whens[-1] else f"{whens[0]} to {whens[-1]}"
    return (f"recorded results of {len(held)} of {len(labels)} probe(s), from {span} "
            f"at commit{'s' if len(heads) > 1 else ''} {', '.join(heads)}")


def listing(record, pattern=None):
    """One line per probe, newest last; ``pattern`` keeps the names holding it."""
    names = sorted(record, key=lambda n: (record[n].get("when", ""), n))
    lines = []
    for name in names:
        if pattern and pattern.lower() not in name.lower():
            continue
        e = record[name]
        status = "ok  " if e.get("ok") else "FAIL"
        counts = ""
        if e.get("passed") is not None:     # a session's --probes-for records no counts
            counts = f"  {e['passed']}/{e['passed'] + (e.get('failed') or 0)}"
        lines.append(f"  {e.get('when', '?'):19}  {e.get('head', '?'):>9}"
                     f"{'+' if e.get('dirty') else ' '} {status} {name}{counts}"
                     + (f"  -- {e['failures'][0][:80]}" if e.get("failures") else ""))
    return lines
