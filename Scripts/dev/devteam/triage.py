"""Effort triage: one cheap call sizes the queue before the run starts.

A small task ("hold the SMG like the pistol") ran at the same effort as a
multi-system feature, and thinking is over a third of a session's output
tokens. Before the first session, one Haiku call with no tools reads every
task that has no ``effort:`` hint and marks the small, obvious ones ``low``.
Everything else keeps the session default, so triage only ever lowers effort,
and when unsure it keeps the default: a wrong ``low`` costs a gate fix, a
wrong default costs a little money.

An ``effort:`` hint in the task file, or --effort, always wins; --no-triage
skips the call. A failed call changes nothing and says so.
"""

import json
import re
import subprocess

MODEL = "haiku"
TIMEOUT = 180

PROMPT = """\
You are sizing tasks for an automated dev team working on an Unreal Engine \
game driven by Unreal Python (CLAUDE.md describes the project). Each task \
below will run in its own session. Pick an effort level for each:

- "low": a contained change whose place in the code is obvious from the task \
text and that needs no new design: change a constant or tuning value, point \
one thing at an asset or animation the project already uses elsewhere, reuse \
an existing behaviour for one more item, or fix a bug whose cause the task \
states.
- "default": everything else. New features, new UI, anything that spans \
systems, needs engine investigation, animation, retargeting or visual \
judgement, imports new assets, or is ambiguous. When unsure, "default".

Tasks:

{tasks}

Answer with JSON only, no prose, one entry per task in order:
{{"tasks": [{{"n": 1, "effort": "low" or "default", "why": "<at most 12 words>"}}]}}"""


def build_prompt(tasks):
    body = "\n\n".join(f"{i}. {t.text}" for i, t in enumerate(tasks, 1))
    return PROMPT.format(tasks=body)


def build_cmd(prompt):
    # No tools, no MCP, nothing saved: the call only reads the prompt (and the
    # project's CLAUDE.md, which is what it needs to judge "obvious").
    return ["claude", "-p", prompt, "--model", MODEL, "--tools", "",
            "--strict-mcp-config", "--no-session-persistence",
            "--output-format", "json"]


def parse(text, count):
    """{task number: (level, why)} from the model's answer; levels other
    than low are dropped (the session default applies)."""
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not m:
        return {}
    try:
        entries = json.loads(m.group(0)).get("tasks") or []
    except (ValueError, AttributeError):
        return {}
    out = {}
    for e in entries:
        if not isinstance(e, dict):
            continue
        n, level = e.get("n"), str(e.get("effort", "")).lower()
        if isinstance(n, int) and 1 <= n <= count and level == "low":
            out[n] = ("low", " ".join(str(e.get("why", "")).split())[:120])
    return out


def triage(tasks, root, run=subprocess.run):
    """Set ``effort`` (and ``triage``, the reason) on the tasks triage marks
    low. Returns (cost in USD, error or None)."""
    if not tasks:
        return 0.0, None
    try:
        proc = run(build_cmd(build_prompt(tasks)), cwd=root, capture_output=True,
                   text=True, timeout=TIMEOUT, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 0.0, f"triage call failed: {exc}"
    try:
        result = json.loads(proc.stdout)
    except ValueError:
        return 0.0, f"triage call failed (exit {proc.returncode}): {proc.stdout[-200:]!r}"
    cost = result.get("total_cost_usd") or 0.0
    if result.get("is_error"):
        return cost, f"triage call failed: {str(result.get('result'))[:200]}"
    picks = parse(result.get("result"), len(tasks))
    for n, (level, why) in picks.items():
        tasks[n - 1].effort = level
        tasks[n - 1].triage = why
    return cost, None
