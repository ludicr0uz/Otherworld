"""The load test's arithmetic (probe_net_load.py), pure and unit-tested.

A run's samples are frame and world-tick times in milliseconds and each
connection's byte totals at the start and the end of the measuring window;
these turn them into the figures the table in Scripts/net/CLAUDE.md holds.
"""

import math


def mean(values):
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def percentile(values, fraction):
    """The value ``fraction`` (0..1) of the sorted samples lie at or below:
    the nearest-rank percentile, 0 with no samples."""
    ordered = sorted(values)
    if not ordered:
        return 0.0
    rank = min(max(1, int(math.ceil(fraction * len(ordered)))), len(ordered))
    return ordered[rank - 1]


def summarize(values):
    """{"n", "mean", "p99", "max"} of a list of milliseconds."""
    values = list(values)
    return {"n": len(values), "mean": round(mean(values), 2),
            "p99": round(percentile(values, 0.99), 2),
            "max": round(max(values), 2) if values else 0.0}


def rate(before, after, seconds):
    """Bytes (or packets) per second between two totals; 0 over no time."""
    return (after - before) / seconds if seconds > 0 else 0.0


def connection_rows(before, after, seconds):
    """One row per connection, matched by name across the two snapshots
    (a connection seen once is reported from the snapshot it is in, over
    its whole life): in and out bytes per second, packets per second, the
    actor channels and lag at the end."""
    rows = []
    first = {c["name"]: c for c in before}
    for c in after:
        b = first.get(c["name"], {"in_bytes": 0, "out_bytes": 0, "in_packets": 0,
                                   "out_packets": 0})
        rows.append({
            "name": c["name"],
            "player": c.get("player", ""),
            "in_bps": round(rate(b["in_bytes"], c["in_bytes"], seconds)),
            "out_bps": round(rate(b["out_bytes"], c["out_bytes"], seconds)),
            "in_pps": round(rate(b["in_packets"], c["in_packets"], seconds), 1),
            "out_pps": round(rate(b["out_packets"], c["out_packets"], seconds), 1),
            "actor_channels": c["actor_channels"],
            "lag_ms": round(c["lag_ms"], 1),
        })
    return rows


def kb(bytes_per_second):
    return f"{bytes_per_second / 1024.0:.1f} KB/s"
