"""The one report of a network run: every process's log and probe results.

Pure: net.py hands it what each process left behind (its log, its probes'
JSON, whether it died), and it returns the lines to print and the verdict.

A run is clean when every client joined and stayed, no process logged a
Blueprint runtime error, an "Accessed None" or a network failure, and every
probe passed in every process it ran in -- and ran in at least one.
"""

import os
import re

from uepylib.game import MAX_NOTABLE, probe_report
from uepylib.net_plan import SERVER

# What a join looks like from each side.
JOIN = {True: r"LogNet: Join succeeded", False: r"LogNet: Welcomed by server"}
NET_PATTERNS = (
    ("bp errors", r"Blueprint Runtime Error"),
    ("accessed None", r"Accessed None"),
    ("net failures", r"Network Failure|Travel Failure|LogNet: Error"),
)
NOTABLE = re.compile("|".join(p for _l, p in NET_PATTERNS))
MAX_LINE = 200


class ProcessReport(object):
    """What one process left: its log's text, its probes' payload (None when
    it never wrote one) and its exit code (None while it lived to be killed)."""

    def __init__(self, name, text, payload=None, exit_code=None, log=""):
        self.name, self.text, self.payload = name, text, payload
        self.exit_code, self.log = exit_code, log

    @property
    def is_server(self):
        return self.name == SERVER

    @property
    def joins(self):
        return len(re.findall(JOIN[self.is_server], self.text))

    def expected_joins(self, clients):
        return clients if self.is_server else 1

    def counts(self):
        return [(label, len(re.findall(pattern, self.text)))
                for label, pattern in NET_PATTERNS]

    def notable(self):
        hits = [l.strip() for l in self.text.splitlines() if NOTABLE.search(l)]
        shown = [h[:MAX_LINE] for h in hits[:MAX_NOTABLE]]
        if len(hits) > MAX_NOTABLE:
            shown.append(f"(+{len(hits) - MAX_NOTABLE} more)")
        return shown


def summary(reports, clients):
    """(lines, ok): one row a process -- joins, error counts, how it ended."""
    labels = [label for label, _p in NET_PATTERNS]
    lines = ["  " + "".join(f"{h:<15}" for h in ["process", "joins"] + labels).rstrip()]
    ok = True
    for r in reports:
        want = r.expected_joins(clients)
        counts = r.counts()
        died = "" if r.exit_code is None else f"died (exit {r.exit_code})"
        cells = [r.name, f"{r.joins}/{want}"] + [str(n) for _l, n in counts] + [died]
        lines.append("  " + "".join(f"{c:<15}" for c in cells).rstrip())
        if r.joins != want or died or any(n for _l, n in counts) or not r.text:
            ok = False
    for r in reports:
        if not r.text:
            lines.append(f"  | {r.name}: no log")
        lines.extend(f"  | {r.name}: {line}" for line in r.notable())
    return lines, ok


def probes(reports, probe_names):
    """(lines, ok): each probe's checks, process by process."""
    lines, ok = [], True
    ran = set()
    for r in reports:
        if r.payload is None:
            lines.append(f"[probe] FAIL  {r.name}: no results -- it never finished "
                         f"(see {os.path.basename(r.log) or 'its log'})")
            ok = False
            continue
        ran.update(p.get("name") for p in r.payload.get("probes") or [])
        named = dict(r.payload, probes=[
            dict(p, name=f"{p.get('name')} @ {r.name}") for p in r.payload.get("probes") or []],
            setup_errors=[f"{r.name}: {e}" for e in r.payload.get("setup_errors") or []])
        part, good = probe_report(named)
        lines.extend(part)
        ok = ok and good
    for name in probe_names:
        if name not in ran and all(r.payload is not None for r in reports):
            lines.append(f"[probe] FAIL  {name} ran in no process (its RUNS_ON names "
                         f"none of: {', '.join(r.name for r in reports)})")
            ok = False
    return lines, ok


def report(reports, clients, probe_names=(), memory=()):
    """(lines, ok) for the whole run. ``memory`` is net_memory's lines: what
    each process used, which fails nothing."""
    lines, ok = summary(reports, clients)
    lines.extend(memory)
    if probe_names:
        part, good = probes(reports, probe_names)
        lines.extend(part)
        ok = ok and good
    return lines, ok
