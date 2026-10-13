"""The task completion log: one spreadsheet row per task dev-team finishes.

Saved/DevTeam/task_log.csv (beside the run directories; open it in Numbers or
Excel) gets a row when a task is written up, done or failed: when it ran, its
effort and model, its time in all and stage by stage (devteam/timing.py), its
tokens and cost by kind, and what the session said of it: what was
accomplished, what it decided, what got in the way.

Those three come from the session's final report, which the system prompt asks
to end with ``Summary:``, ``Decisions:`` and ``Challenges:`` sections
(``sections``). A report without them still fills the row: the summary is its
first paragraph and the challenges are the commits' "Issues encountered:".

The same record is what dev-team prints: under each task as it finishes
(``lines``) and beside each task in the list a run ends with (``printout``).

Cost by kind is the session's reported cost shared out over its four kinds of
token by price (``RATES``), model by model, so the parts always add up to the
cost the CLI reported; the rates only set the proportions.
"""

import csv
import datetime
import os
import re
import time

from devteam import timing
from devteam.accounting import describe_time, git, token_usage

NAME = "task_log.csv"
KINDS = ("input", "output", "cache_read", "cache_write")
SECTIONS = ("summary", "decisions", "challenges")

# $ per million tokens (input, output, cache read, cache write), fitted to the
# costs the CLI reported for 73 sessions of 10-13 Oct 2026 (to within 3 cents
# a session). Only their proportions are used. A model not listed is shared
# out like the first.
RATES = {
    "claude-opus-5-5": (4.0, 20.0, 0.2, 8.0),
    "claude-fable-5-1": (10.0, 50.0, 0.25, 20.0),
}
_USAGE_KEYS = ("inputTokens", "outputTokens", "cacheReadInputTokens",
               "cacheCreationInputTokens")

COLUMNS = (["date", "started", "finished", "run", "task #", "task", "status", "model",
            "effort", "commits", "turns", "total (min)"]
           + [f"{s} (min)" for s in timing.STAGES]
           + ["tokens", "input tokens", "output tokens", "cache read tokens",
              "cache write tokens", "cost ($)", "input ($)", "output ($)",
              "cache read ($)", "cache write ($)", "summary", "decisions", "challenges",
              "session", "task text"])

_HEAD = re.compile(r"^\s*(?:#{1,6}\s*)?\**(summary|decisions|challenges)"
                   r"(?:\**\s*:\**\s*(.*)|\**\s*)$", re.IGNORECASE)
_ISSUES = re.compile(r"^\s*Issues encountered:\s*(.*)$", re.IGNORECASE)
_TRAILER = re.compile(r"^(?:Co-Authored-By|Signed-off-by|Time|Tokens):", re.IGNORECASE)


def sections(reports):
    """{summary, decisions, challenges} out of the sessions' reports: the text
    under each heading, a follow-up session's (a gate fix) after the first's."""
    found = {name: [] for name in SECTIONS}
    for report in reports:
        current = None
        for line in (report or "").splitlines():
            head = _HEAD.match(line)
            if head:
                current = found[head.group(1).lower()]
                if current:
                    current.append("")
                line = head.group(2) or ""
                if not line:
                    continue
            if current is not None and (line.strip() or current):
                current.append(line.rstrip())
    return {name: "\n".join(text).strip() for name, text in found.items()}


def first_paragraph(report, limit=600):
    text = " ".join((report or "").strip().split("\n\n")[0].split())
    return text if len(text) <= limit else text[:limit - 3] + "..."


def issues(messages):
    """The "Issues encountered:" sections of commit messages, joined."""
    out, taking = [], False
    for line in (messages or "").splitlines():
        head = _ISSUES.match(line)
        if head:
            taking, line = True, head.group(1)
        elif taking and _TRAILER.match(line):
            taking = False
        if taking and (line.strip() or (out and out[-1])):
            out.append(line.rstrip())
    return "\n".join(out).strip()


def cost_split(result):
    """{kind: dollars}: the reported cost over the four kinds of token."""
    split = dict.fromkeys(KINDS, 0.0)
    models = result.get("modelUsage") or {}
    if not models:
        usage = token_usage(result)
        models = {"": dict(zip(_USAGE_KEYS, (usage[k] for k in KINDS)),
                           costUSD=result.get("total_cost_usd") or 0.0)}
    default = next(iter(RATES.values()))
    for name, used in models.items():
        rates = next((r for model, r in RATES.items() if name.startswith(model)), default)
        weights = [(used.get(key) or 0) * rate for key, rate in zip(_USAGE_KEYS, rates)]
        whole = sum(weights)
        for kind, weight in zip(KINDS, weights):
            split[kind] += (used.get("costUSD") or 0.0) * weight / whole if whole else 0.0
    return split


def build(task, n, status, effort, model, result, stages, reports, commits="",
          messages="", run="", started=None, finished=None):
    """One task's record: everything the log's row and the printout hold."""
    said = sections(reports)
    last = next((r for r in reversed(reports) if r), "")
    return dict(
        task=task.title, text=task.text, n=n, status=status, effort=effort,
        model=", ".join(result.get("modelUsage") or {}) or model or "",
        commits=commits, run=run, session=result.get("session_id") or "",
        turns=result.get("num_turns") or 0,
        started=started or time.time(), finished=finished or time.time(),
        stages=stages, seconds=timing.total(stages),
        tokens=token_usage(result), cost=result.get("total_cost_usd") or 0.0,
        cost_split=cost_split(result),
        summary=said["summary"] or first_paragraph(last),
        decisions=said["decisions"],
        challenges=said["challenges"] or issues(messages))


def commit_messages(root, before, after):
    if not (before and after and after != before):
        return ""
    return git(root, "log", "--format=%B", f"{before}..{after}").stdout


def record_task(task, n, status, effort, model, result, reports, run_dir, root,
                before, after):
    """Write a finished task up: close its clock (the stages run_one kept in
    the run directory), build its record, leave it on ``task.record`` and add
    its row to the log beside the run directories. Returns the record."""
    clock = timing.Stages(timing.path(run_dir, n))
    clock.finish()
    tools = timing.tool_time(os.path.join(run_dir, f"task-{n:02d}.jsonl"))
    record = build(
        task, n, status, effort, model, result,
        timing.breakdown(clock.spent, tools, result.get("duration_ms")), reports,
        commits=f"{before}..{after}" if before and after and after != before else "",
        messages=commit_messages(root, before, after),
        run=os.path.basename(run_dir), started=clock.started)
    task.record = record
    record["log"] = append(os.path.dirname(os.path.abspath(run_dir)), record)
    return record


def row(record):
    def clock(when):
        return datetime.datetime.fromtimestamp(when)

    def minutes(seconds):
        return f"{seconds / 60:.2f}" if seconds else ""

    tokens, split = record["tokens"], record["cost_split"]
    cells = {
        "date": clock(record["started"]).strftime("%Y-%m-%d"),
        "started": clock(record["started"]).strftime("%H:%M:%S"),
        "finished": clock(record["finished"]).strftime("%H:%M:%S"),
        "run": record["run"], "task #": record["n"], "task": record["task"],
        "status": record["status"], "model": record["model"], "effort": record["effort"],
        "commits": record["commits"], "turns": record["turns"],
        "total (min)": minutes(record["seconds"]),
        "tokens": tokens["total"], "cost ($)": f"{record['cost']:.2f}",
        "summary": record["summary"], "decisions": record["decisions"],
        "challenges": record["challenges"], "session": record["session"],
        "task text": record["text"],
    }
    for stage in timing.STAGES:
        cells[f"{stage} (min)"] = minutes(record["stages"].get(stage))
    for kind in KINDS:
        label = kind.replace("_", " ")
        cells[f"{label} tokens"] = tokens[kind]
        cells[f"{label} ($)"] = f"{split[kind]:.2f}"
    return [cells[c] for c in COLUMNS]


def append(log_root, record):
    """Add the record's row to the log. A log whose columns are another
    version's is set aside (task_log-<time>.csv) and a new one begun. Returns
    the log's path, or None when it could not be written."""
    path = os.path.join(log_root, NAME)
    try:
        if os.path.isfile(path):
            with open(path, newline="", encoding="utf-8-sig") as fh:
                header = next(csv.reader(fh), None)
            if header != COLUMNS:
                stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                os.rename(path, os.path.join(log_root, f"task_log-{stamp}.csv"))
        new = not os.path.isfile(path)
        # The BOM is what makes Excel read the file as UTF-8.
        with open(path, "a", newline="", encoding="utf-8-sig" if new else "utf-8") as fh:
            out = csv.writer(fh)
            if new:
                out.writerow(COLUMNS)
            out.writerow(row(record))
    except OSError as exc:
        print(f"    (could not write the task log {path}: {exc})")
        return None
    return path


def lines(record, indent="    "):
    """The record's breakdown, as printed under a task: where the time went,
    the tokens by kind and what each kind cost."""
    tokens, split = record["tokens"], record["cost_split"]
    kinds = [(kind.replace("_", " "), kind) for kind in KINDS]
    return [
        f"{indent}time    " + (timing.describe(record["stages"]) or "not clocked"),
        f"{indent}tokens  " + ", ".join(f"{label} {tokens[kind]:,}" for label, kind in kinds),
        f"{indent}cost    " + ", ".join(f"{label} ${split[kind]:.2f}" for label, kind in kinds),
    ]


def headline(record):
    return (f"{describe_time(record['seconds'] * 1000)}, ${record['cost']:.2f}, "
            f"{record['tokens']['total']:,} tokens")


def printout(outcomes, waiting):
    """What a run ends with: every task with its status and, when it was
    written up, its time, cost and tokens beside it and their breakdown
    under it; then the sum."""
    out, records = [], []
    for task, status in outcomes:
        record = getattr(task, "record", None)
        out.append(f"  {status:>11}  {task.title}" + (f"  -- {headline(record)}" if record else ""))
        if record:
            records.append(record)
            out += lines(record, indent=" " * 15)
    out += [f"  {'not run':>11}  {task.title}" for task in waiting]
    if len(records) > 1:
        stages = {}
        for record in records:
            for stage, seconds in record["stages"].items():
                stages[stage] = stages.get(stage, 0.0) + seconds
        out.append(f"  {'in all':>11}  {len(records)} tasks  -- "
                   f"{describe_time(timing.total(stages) * 1000)}, "
                   f"${sum(r['cost'] for r in records):.2f}, "
                   f"{sum(r['tokens']['total'] for r in records):,} tokens")
        out.append(" " * 15 + "time    " + timing.describe(stages))
    return out
