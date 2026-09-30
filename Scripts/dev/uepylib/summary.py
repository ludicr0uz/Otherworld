"""Read a script's output back into what matters: counts, failures, errors.

A verifier's full output is hundreds of PASS lines; a cold run's is thousands
of engine lines around them. A session that reads all of it pays for every
line on every later turn, so it greps -- and then usually needs a second turn
to tail the file for what the grep missed. ``summarize()`` does that reading
once, the same way every time:

- verifier totals, in every format the suites print:
    [VERIFY] 139/139 checks passed              graphics menu
    [VERIFY] 98 passed, 1 failed                combat, survival, NPC
    [VERIFY] ✅ ALL 257 CHECKS PASSED!           generated levels
    [VERIFY] ❌ 3/257 CHECKS FAILED!
- each failed check, with its detail when the suite prints one;
- the tail of every Python traceback;
- Python errors that are neither (a builder's log_error);
- for a builder, its last tagged line (``[GUN] done -- ...``).

It also decides failure: a verifier that reports failed checks fails its
target even though the script itself returned normally -- which it always
does, so before this a failing suite exited 0.
"""

import re

MAX_FAILURES = 12
MAX_ERRORS = 5
TRACEBACK_TAIL = 4

_STAMP = re.compile(r"^\[\d{4}\.\d\d\.\d\d-[\d.:]+\]\[\s*\d+\]")
_CATEGORY = re.compile(r"^Log\w+: (?:(Display|Warning|Error|Verbose): )?")
_LEVEL = re.compile(r"^(Display|Warning|Error|Info): ")

_TOTALS = (
    # (pattern, how to turn the groups into (passed, failed))
    (re.compile(r"\[VERIFY\] (\d+)/(\d+) checks passed"),
     lambda a, b: (int(a), int(b) - int(a))),
    (re.compile(r"\[VERIFY\] (\d+) passed, (\d+) failed"),
     lambda a, b: (int(a), int(b))),
    (re.compile(r"\[VERIFY\] ✅ ALL (\d+) CHECKS PASSED"),
     lambda a: (int(a), 0)),
    (re.compile(r"\[VERIFY\] ❌ (\d+)/(\d+) CHECKS FAILED"),
     lambda a, b: (int(b) - int(a), int(a))),
)
_FAIL_DETAILED = re.compile(r"\[VERIFY\] FAIL(?!ED)\s+(.+)")
_FAIL_NAMED = re.compile(r"\[VERIFY\]\s+(?:FAILED|failed): (.+)")
_FAIL_LEVEL = re.compile(r"❌\s*(.+)")
_PY_ERROR = re.compile(r"^(?:\[[^\]]*\]\[\s*\d+\])?(?:LogPython: )?Error: (.+)")
_TAGGED = re.compile(r"^\[(?!VERIFY\]|uepy|PROBE\])[A-Z][A-Za-z-]*\] .+")


def clean(line):
    """A log line without its timestamp, category and severity."""
    line = _STAMP.sub("", line.rstrip())
    line = _CATEGORY.sub("", line)
    return _LEVEL.sub("", line)


class Summary(object):

    def __init__(self):
        self.passed = None       # None: the output held no verifier totals
        self.failed = None
        self.failures = []       # one line per failed check
        self.tracebacks = []     # the last few lines of each
        self.errors = []         # other Python errors
        self.last_tag = None     # a builder's last "[TAG] ..." line

    @property
    def has_totals(self):
        return self.passed is not None

    @property
    def total(self):
        return (self.passed or 0) + (self.failed or 0)

    def as_dict(self):
        return {"passed": self.passed, "failed": self.failed,
                "failures": list(self.failures),
                "tracebacks": list(self.tracebacks), "errors": list(self.errors)}


def _add_unique(items, value, limit):
    if value not in items and len(items) < limit:
        items.append(value)


def _tracebacks(lines):
    """(tails, members): the last TRACEBACK_TAIL lines of every traceback in
    cleaned lines, and the indices of every line that belongs to one."""
    found, members, i = [], set(), 0
    while i < len(lines):
        if lines[i].startswith("Traceback (most recent call last)"):
            start = i
            i += 1
            while i < len(lines) and (lines[i].startswith((" ", "\t")) or not lines[i]):
                i += 1
            if i < len(lines):
                i += 1                       # the exception line itself
            block = [l for l in lines[start:i] if l.strip()]
            members.update(range(start, i))
            found.append("\n".join(block[-TRACEBACK_TAIL:]))
        else:
            i += 1
    return found, members


def summarize(text):
    s = Summary()
    raw = text.splitlines()
    lines = [clean(l) for l in raw]
    named, level_fails = [], []
    s.tracebacks, in_traceback = _tracebacks(lines)
    for index, (original, line) in enumerate(zip(raw, lines)):
        if index in in_traceback:
            continue
        for pattern, convert in _TOTALS:
            m = pattern.search(line)
            if m:
                passed, failed = convert(*m.groups())
                s.passed = (s.passed or 0) + passed
                s.failed = (s.failed or 0) + failed
                break
        else:
            m = _FAIL_DETAILED.search(line)
            if m:
                _add_unique(s.failures, m.group(1).strip(), MAX_FAILURES)
                continue
            m = _FAIL_NAMED.search(line)
            if m:
                named.append(m.group(1).strip())
                continue
            m = _FAIL_LEVEL.search(line)
            if m:
                level_fails.append(m.group(1).strip())
                continue
            m = _PY_ERROR.match(original.strip())
            if m and "[VERIFY]" not in m.group(1):
                _add_unique(s.errors, clean(m.group(1)).strip(), MAX_ERRORS)
            if _TAGGED.match(line):
                s.last_tag = line.strip()
    # A suite that prints "FAIL label -- detail" also prints "FAILED: label";
    # the detailed line says more, so the named list is only the fallback.
    if not s.failures:
        for name in named + level_fails:
            _add_unique(s.failures, name, MAX_FAILURES)
    return s


def verdict(result, summary):
    """A target passes when it ran cleanly *and* no verifier check failed."""
    return result.ok and not (summary.failed or 0)


def format_target(result, summary):
    """The summary lines for one target."""
    ok = verdict(result, summary)
    head = f"[uepy] {'ok  ' if ok else 'FAIL'}  {result.label}"
    if summary.has_totals:
        head += f"  {summary.passed}/{summary.total} checks passed"
    head += f"  ({result.seconds:.1f}s)"
    if not summary.has_totals and summary.last_tag and ok:
        head += f"  {summary.last_tag[:140]}"
    out = [head]
    for f in summary.failures:
        out.append(f"         FAIL {f[:300]}")
    extra = (summary.failed or 0) - len(summary.failures)
    if summary.failures and extra > 0:
        out.append(f"         (+{extra} more failed checks)")
    for tb in summary.tracebacks[-2:]:
        out.extend("         " + l[:300] for l in tb.splitlines())
    for e in summary.errors:
        out.append(f"         error: {e[:300]}")
    if not ok and not (summary.failures or summary.tracebacks or summary.errors):
        tail = [clean(l) for l in result.text.splitlines() if l.strip()][-6:]
        out.extend("         | " + l[:300] for l in tail)
    return out
