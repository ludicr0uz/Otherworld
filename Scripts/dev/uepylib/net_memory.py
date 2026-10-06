"""How much memory each process of a network run used.

net.py samples every process while the run waits and once more before the
kill; the report prints one line per process: its peak, and what it held at
the end. The figures in serversupportsysdesign.md section 5 are these.

Two measures, because on a machine that swaps they differ:

    footprint   what macOS charges the process (Activity Monitor's "Memory":
                resident + compressed + swapped). What it costs the machine.
    resident    ps's RSS: what is in RAM just now. Falls when the machine
                compresses or swaps, so it is the floor, not the cost.

``footprint`` is /usr/bin/footprint, absent off macOS: the line then gives
the resident figure alone.
"""

import re
import subprocess

FOOTPRINT = "/usr/bin/footprint"
# footprint's own line per process: "UnrealEditor [123]: 64-bit    Footprint: 3421 MB ..."
FOOTPRINT_LINE = re.compile(r"\[(\d+)\].*?Footprint:\s*([\d.]+)\s*([KMG])B")
KB = {"K": 1, "M": 1024, "G": 1024 * 1024}
# Seconds between two samples while the run waits.
EVERY = 2.0


def parse_ps(text):
    """{pid: resident KB} from ``ps -o pid=,rss=``."""
    found = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2 and all(p.isdigit() for p in parts):
            found[int(parts[0])] = int(parts[1])
    return found


def parse_footprint(text):
    """{pid: footprint KB} from ``footprint -p <pid> ...``."""
    return {int(pid): int(float(amount) * KB[unit])
            for pid, amount, unit in FOOTPRINT_LINE.findall(text)}


def _run(argv):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def sample(pids):
    """{pid: (resident KB, footprint KB or 0)} of the processes still alive."""
    pids = [str(p) for p in pids]
    if not pids:
        return {}
    resident = parse_ps(_run(["ps", "-o", "pid=,rss=", "-p", ",".join(pids)]))
    footprint = parse_footprint(_run(
        [FOOTPRINT, *(arg for pid in pids for arg in ("-p", pid))]))
    return {pid: (kb, footprint.get(pid, 0)) for pid, kb in resident.items()}


class Usage(object):
    """One process's samples: the peak of each measure, and the last."""

    def __init__(self):
        self.samples = 0
        self.peak_resident = self.peak_footprint = 0
        self.last_resident = self.last_footprint = 0

    def add(self, resident, footprint=0):
        self.samples += 1
        self.last_resident, self.last_footprint = resident, footprint
        self.peak_resident = max(self.peak_resident, resident)
        self.peak_footprint = max(self.peak_footprint, footprint)


class Meter(object):
    """Every process's Usage, by its name in the run."""

    def __init__(self):
        self.usage = {}

    def read(self, running):
        """Sample ``running``, the run's (process, Popen) pairs."""
        names = {proc.pid: process.name for process, proc in running
                 if proc.poll() is None}
        for pid, (resident, footprint) in sample(names).items():
            self.usage.setdefault(names[pid], Usage()).add(resident, footprint)


def gb(kb):
    return f"{kb / (1024.0 * 1024.0):.1f} GB"


def lines(usage, names):
    """The report's memory lines, a process each, then the total of the peaks."""
    out, total, measured = [], 0, "footprint"
    for name in names:
        u = usage.get(name)
        if u is None or not u.samples:
            continue
        if u.peak_footprint:
            out.append(f"  memory  {name:<10} peak {gb(u.peak_footprint)} footprint, "
                       f"{gb(u.peak_resident)} resident; at the end "
                       f"{gb(u.last_footprint)}, {gb(u.last_resident)}")
            total += u.peak_footprint
        else:
            measured = "resident"
            out.append(f"  memory  {name:<10} peak {gb(u.peak_resident)} resident; "
                       f"at the end {gb(u.last_resident)}")
            total += u.peak_resident
    if out:
        out.append(f"  memory  {'all':<10} {gb(total)} (the peaks' sum, {measured})")
    return out
