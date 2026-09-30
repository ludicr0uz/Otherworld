"""One headless ``claude -p`` session: its prompt, command line, environment,
and the live one-line-per-step view of what it is doing."""

import json
import os
import re
import signal
import subprocess

FAIL_MARK = "FAILED:"

PROMPT = """\
You are one member of an automated dev team working through a queue of tasks, \
one fresh session per task. No human is watching this session: do not ask \
questions or wait for answers. Where a choice is the user's, make the sensible \
call and say what you chose in your final report.

Your task ({n} of {total}):

{task}

Work the way CLAUDE.md says: follow its conventions and verify your change the \
way the project verifies things before you finish.{commit}
{progress}
Every earlier turn is re-read on each new one, so keep what you pull in lean: \
grep -n and sed -n ranges for a file of more than a few hundred lines, and \
whole files only when you need all of them.

In this session uepy.py always boots a fresh editor (UEPY_COLD=1; no editor is \
open) and prints a summary per script (UEPY_OUTPUT=summary: verifier counts, \
failed checks, traceback tails, plus the path of the full log); pass --full \
to see everything. To check behaviour in the running game, write a probe and \
run it with `uepy.py --game --probe FILE` (Scripts/probes/__init__.py).

{gate}

End with a short report: what changed, how you verified it, and anything left \
undone. If you could not complete the task, make the first line of the report \
"{fail} <reason>"."""

PROGRESS = """
Earlier tasks in this run and their reports are in {path} -- read it if your \
task may depend on them.
"""

GATE = """\
Before this session started, dev-team ran the verifier suite:

{table}

When you finish, dev-team runs the same suite again. A verifier that newly \
fails, or fails more checks than above, fails this task, so run the suites \
you touched before you commit."""

GATE_BROKEN = """\
dev-team could not get a baseline from the verifier suite before this session \
(the sweep itself failed). Run the full sweep yourself before you commit."""

COMMIT = """ When the task is done and verified, commit your changes \
(never --no-verify). Besides saying what changed, the commit message body must \
have a section headed "Issues encountered:" listing each problem you hit while \
working (failed checks, wrong assumptions, engine or tooling surprises, dead \
ends) and, for each, the steps you took to resolve it -- or \
"Issues encountered: none", above any co-author line. dev-team appends the \
time and token trailers after you commit, so do not write those yourself."""

FIX = """\
dev-team re-ran the verifier suite after your session, and it regressed:

{problems}

{table}

Find and fix the cause. Change a check only if the check itself is wrong, and \
say so in the report. Re-run the affected suites, then commit the fix{commit}. \
End with the same kind of report; if you cannot fix it, make its first line \
"{fail} <reason>"."""


def build_prompt(task, n, total, progress_path, baseline_table, commit):
    progress = PROGRESS.format(path=progress_path) if n > 1 else ""
    if baseline_table is None:
        gate = GATE_BROKEN
    else:
        gate = GATE.format(table=baseline_table)
    return PROMPT.format(n=n, total=total, task=task.text, progress=progress,
                         commit=COMMIT if commit else "", gate=gate, fail=FAIL_MARK)


def build_fix_prompt(problems, table, commit):
    return FIX.format(problems="\n".join(f"- {p}" for p in problems), table=table,
                      commit=" (a new commit; do not amend)" if commit else "",
                      fail=FAIL_MARK)


def build_cmd(prompt, permission_mode, name=None, model=None, effort=None,
              budget=None, resume=None):
    # --strict-mcp-config with no --mcp-config: no MCP servers at all. The
    # claude.ai connectors (Docs, Drive) add tools to every turn and no task
    # here uses them; ENABLE_CLAUDEAI_MCP_SERVERS=false in session_env() too.
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose",
           "--permission-mode", permission_mode, "--strict-mcp-config"]
    if resume:
        cmd += ["--resume", resume]
    elif name:
        cmd += ["--name", name]
    if model:
        cmd += ["--model", model]
    if effort:
        cmd += ["--effort", effort]
    if budget:
        cmd += ["--max-budget-usd", str(budget)]
    return cmd


def session_env(base):
    env = dict(base)
    env["UEPY_COLD"] = "1"               # never an editor the user may reopen
    env["UEPY_OUTPUT"] = "summary"       # counts and failures, not 2,000 lines
    env["ENABLE_CLAUDEAI_MCP_SERVERS"] = "false"
    return env


class Narrator(object):
    """Turns stream-json events into the live progress lines."""

    def __init__(self, root):
        self.root = root
        roots = "|".join(re.escape(r) for r in (root, root.replace(" ", "\\ ")))
        # A leading `cd <root>[/sub];` or `cd <root>[/sub] &&`, quoted or with
        # escaped spaces -- sessions prefix nearly every command with one.
        self.cd_root = re.compile(
            rf"""^cd\s+(["']?)(?:{roots})(/[^"';&]*)?\1\s*(?:;|&&)\s*""")

    def describe(self, tool):
        """One line for a tool call."""
        name, inp = tool.get("name", "?"), tool.get("input") or {}
        detail = (inp.get("description") or inp.get("file_path") or inp.get("pattern")
                  or inp.get("command") or inp.get("prompt") or "")
        detail = " ".join(str(detail).split())
        m = self.cd_root.match(detail)
        if m:
            sub = (m.group(2) or "").strip("/")
            detail = (f"[{sub}] " if sub else "") + detail[m.end():]
        detail = detail.replace(self.root + "/", "").replace(self.root, ".")
        return f"{name}: {detail[:90]}" if detail else name


def note(text):
    """The model's own words between tool calls, as one line."""
    text = " ".join(text.split())
    return text if len(text) <= 200 else text[:197] + "..."


def run_session(cmd, root, log_path, env):
    """Run one session, narrating it. Returns (ok, report, result event)."""
    narrator = Narrator(root)
    result = {}
    # A text block is printed only once a tool call follows it: the last one
    # is the final report, which is printed in full after the session.
    pending = []
    with open(log_path, "a") as log:
        proc = subprocess.Popen(cmd, cwd=root, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, env=env,
                                stdin=subprocess.DEVNULL, start_new_session=True)
        try:
            for line in proc.stdout:
                log.write(line)
                log.flush()
                try:
                    event = json.loads(line)
                except ValueError:
                    print(f"    {line.rstrip()}")
                    continue
                if event.get("type") == "system" and event.get("subtype") == "init":
                    print(f"    session {event.get('session_id')}")
                elif event.get("type") == "assistant" and not event.get("parent_tool_use_id"):
                    for block in event.get("message", {}).get("content", []):
                        if block.get("type") == "text" and block.get("text", "").strip():
                            pending.append(block["text"])
                        elif block.get("type") == "tool_use":
                            for text in pending:
                                print(f"    » {note(text)}")
                            pending.clear()
                            print(f"    · {narrator.describe(block)}")
                elif event.get("type") == "result":
                    result = event
            proc.wait()
        except KeyboardInterrupt:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait()
            raise
    report = (result.get("result") or "").strip()
    ok = (proc.returncode == 0 and result and not result.get("is_error")
          and not report.startswith(FAIL_MARK))
    return bool(ok), report, result
