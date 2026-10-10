"""One headless ``claude -p`` session: its prompt, command line, environment,
and the live one-line-per-step view of what it is doing."""

import contextlib
import json
import os
import re
import signal
import subprocess

from devteam.pause import interrupt

FAIL_MARK = "FAILED:"
FAB_MARK = "FAB-REQUIRED:"

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
whole files only when you need all of them. Grep Scripts/dev/symbols.txt \
first to find where a symbol lives, and batch independent reads into one \
command rather than one per turn.

In this session uepy.py runs scripts in a headless editor of this session's \
own (UEPY_SERVE): the first call boots it (20-40 s), later calls reuse it, so \
a run costs about what the script itself takes. It is warm: modules under \
Scripts/ are re-imported for every call, but assets earlier calls loaded stay \
loaded, as in any open editor. Do not pass --cold (it stops the warm editor \
first, then pays a full boot). If a script crashes or hangs the warm editor, \
uepy.py kills it, boots a fresh one and runs that script again by itself, \
saying so in one line: do not kill or restart the editor yourself. A script \
reported as failed that way took down two editors in a row. uepy.py \
prints a summary per script (UEPY_OUTPUT=summary: verifier counts, failed \
checks, traceback tails, plus the path of the full log); pass --full to see \
everything. To check behaviour in the running game, write a probe and \
run it with `uepy.py --game --probe FILE` (Scripts/probes/__init__.py).

Run every command in the foreground: never run_in_background, and do not \
start a run to poll for later. This headless session is never told when a \
background command finishes, so a session that waits for one ends with its \
work unverified and uncommitted. Give a long run a timeout instead (up to \
600000 ms), and put several probes in one launch (`--probe A --probe B`) \
rather than one launch each. A long --game or --net run can instead be \
detached: `uepy.py --net --clients 2 --detach --probe P` prints a run \
directory and returns at once, so read or edit meanwhile, then `uepy.py \
--wait <run dir> --timeout 500` prints the usual report (and fails on \
timeout); `--status` lists runs. One detached run at a time. While you work, run `uepy.py --probes-for` \
(no paths: the probes your `git diff` can affect, one --game and one --net \
launch; `--dry-run` lists them) instead of choosing probes by hand or \
repeating one. Do not run the regression yourself: dev-team's gate runs the \
verifiers before and after you, and a smoke set of probes once the run's last \
task is done (after each task too, when the run asks for it); a probe that \
newly fails counts against the run, or the task. End when your change is \
proven by its own probe.

{gate}

{fab}

End with a short report: what changed, how you verified it, and anything left \
undone. If you could not complete the task, make the first line of the report \
"{fail} <reason>"."""

# The contract devteam/fab.py parses. Kept beside the prompt it is part of.
FAB = """\
Fab assets (models, animations, Megascans) can only be acquired by the user: \
never try to sign in, drive the Fab plugin, or download from fab.com, and do \
not substitute a stand-in for an asset the task needs. First check what the \
project already has: assets/cache/fab/index.md and index.json (rebuild with \
`uepy.py Scripts/asset_pipeline/fab_index.py`). You may search fab.com to \
pick a listing. If the task needs one that is not there, finish whatever does \
not depend on it, commit that, and end your report with the request instead: \
first line "{mark} <summary>", then one line per asset:
- <listing name> | url: <fab.com listing url> | at: /Game/<folder it should import to> | why: <what it is for>
dev-team asks the user for them and resumes this session once they are in."""

PROGRESS = """
Earlier tasks in this run and their reports are in {path} -- read it if your \
task may depend on them.
"""

GATE = """\
Before this session started, dev-team ran the verifier suite (a `probe:` row is a probe of the gate's set, when it has one):

{table}

When you finish, dev-team runs the same suite again. A verifier or probe that newly \
fails, or fails more checks than above, fails this task, so run the suites \
you touched before you commit.

{known}"""

KNOWN_RULE = """\
Standing failures are listed in Scripts/dev/known_failures.md (one line each: \
verifier or probe | check label | since | why). A listed check that fails is not \
yours and never counts as a regression. Never rebuild, stash or check out HEAD to \
prove a baseline: report against the recorded one."""

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


# Commands every session runs dozens of times, allowed outright. In auto mode
# anything not allowed goes to the classifier first, which measured 0.6-2.2 s
# a call (about 1.3 s median over ~1,400 calls a day); allowed, 0.03 s, the
# same as bypassPermissions. Everything else still goes through the mode.
# A compound command is allowed when each part is, so the sessions' habitual
# `cd "<root>"; sed -n ...; grep ...` needs `cd` here too.
ALLOW = [
    "Bash(cd *)", "Bash(ls *)", "Bash(cat *)", "Bash(head *)", "Bash(tail *)",
    "Bash(sed -n *)", "Bash(grep *)", "Bash(rg *)", "Bash(wc *)", "Bash(sort *)",
    "Bash(uniq *)", "Bash(cut *)", "Bash(diff *)",
    "Bash(git status *)", "Bash(git log *)", "Bash(git show *)", "Bash(git diff *)",
    "Bash(git grep *)", "Bash(git blame *)", "Bash(git rev-parse *)",
    "Bash(python3 Scripts/dev/uepy.py *)",
    "Bash(python3 -m unittest discover -s Scripts/dev/tests*)",
]
# No session touches the cloud: the GCP build VM (Scripts/server/gcp) bills by the hour and
# is the owner's to start. Denied here, and session_env() takes gcloud's credentials away.
DENY = ["Bash(gcloud:*)", "Bash(gsutil:*)", "Bash(bq:*)"]
SETTINGS = {"permissions": {"allow": ALLOW, "deny": DENY}}


def build_prompt(task, n, total, progress_path, baseline_table, commit):
    progress = PROGRESS.format(path=progress_path) if n > 1 else ""
    if baseline_table is None:
        gate = GATE_BROKEN + "\n\n" + KNOWN_RULE
    else:
        gate = GATE.format(table=baseline_table, known=KNOWN_RULE)
    return PROMPT.format(n=n, total=total, task=task.text, progress=progress,
                         commit=COMMIT if commit else "", gate=gate, fail=FAIL_MARK,
                         fab=FAB.format(mark=FAB_MARK))


def build_fix_prompt(problems, table, commit):
    return FIX.format(problems="\n".join(f"- {p}" for p in problems), table=table,
                      commit=" (a new commit; do not amend)" if commit else "",
                      fail=FAIL_MARK)


RESUMED = """\
dev-team paused this session at the user's request and has now resumed it. \
While it was paused: the command that was running, if any, was killed part \
way; the warm editor was stopped; and your uncommitted work was parked in a \
commit and has been put back as it was, uncommitted{where}. The project may \
have been built from other code meanwhile, so assets under Content/ are not \
to be trusted: re-run the builders for what you changed before you believe a \
verifier or a probe. Then carry on with the task from where you stopped{commit}, \
and end with the same kind of report; if you cannot complete it, make its \
first line "{fail} <reason>"."""


def build_resumed_prompt(branch, commit):
    return RESUMED.format(
        where=f", on the branch {branch}" if branch else "",
        commit=" and commit on this branch as you would have" if commit else "",
        fail=FAIL_MARK)


LIMIT_RESUMED = """\
The Claude session limit stopped this session part way, and it has now reset: \
dev-team waited it out and is resuming you. The command that was running, if \
any, was ended with your turn and may need running again; the warm editor \
boots again by itself on the next uepy.py call. Carry on with the task from \
where you stopped{commit}, and end with the same kind of report; if you cannot \
complete it, make its first line "{fail} <reason>"."""

UNCOMMITTED = """\
Your last turn ended without a commit, and the working tree has changes that \
were not there when your session began. If you were waiting for a background \
command: this headless session is never told when one finishes, and whatever \
was running was ended with your turn. Run it again in the foreground (a \
timeout of up to 600000 ms; several probes go in one launch with repeated \
--probe) and read its output. Then finish the task: verify, commit as asked, \
and end with the same kind of report. If the changes are not yours or the task \
cannot be completed, make the report's first line "{fail} <reason>"."""


def build_limit_resumed_prompt(commit):
    return LIMIT_RESUMED.format(commit=" and commit as asked" if commit else "",
                                fail=FAIL_MARK)


def build_uncommitted_prompt():
    return UNCOMMITTED.format(fail=FAIL_MARK)


def build_cmd(prompt, permission_mode, name=None, model=None, effort=None,
              budget=None, resume=None, fast=False):
    # --strict-mcp-config with no --mcp-config: no MCP servers at all. The
    # claude.ai connectors (Docs, Drive) add tools to every turn and no task
    # here uses them; ENABLE_CLAUDEAI_MCP_SERVERS=false in session_env() too.
    # A headless session runs in fast mode only when its --settings say so
    # (devteam/fast.py decides).
    settings = dict(SETTINGS, fastMode=True) if fast else SETTINGS
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose",
           "--permission-mode", permission_mode, "--strict-mcp-config",
           "--settings", json.dumps(settings)]
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


def session_env(base, serve_dir):
    env = dict(base)
    env.pop("UEPY_COLD", None)
    env["UEPY_SERVE"] = serve_dir        # its own warm editor, never the user's
    env["UEPY_OUTPUT"] = "summary"       # counts and failures, not 2,000 lines
    env["ENABLE_CLAUDEAI_MCP_SERVERS"] = "false"
    # An empty config directory: gcloud and gsutil find no account, so nothing a
    # session runs can reach GCP. Scripts/server/gcp/config.sh refuses on OW_NO_GCP.
    env["CLOUDSDK_CONFIG"] = os.path.join(serve_dir, "no-gcloud")
    env["BOTO_CONFIG"] = os.devnull
    env.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
    env["OW_NO_GCP"] = "1"
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


def fast_note(event):
    """What a session's init event says about fast mode, or "" when there is
    nothing to say: it was not asked for, which is what an unopted headless
    session reports."""
    state, why = event.get("fast_mode_state"), event.get("fast_mode_disabled_reason")
    if state == "on":
        return "fast mode on"
    if why and why != "sdk_opt_in_required":
        return f"fast mode {state or 'off'}: {why}"
    return ""


def run_session(cmd, root, log_path, env, on_limits=None, pauser=None):
    """Run one session, narrating it. Returns (ok, report, result event).
    ``on_limits`` is handed each rate_limit_info the session streams. A
    ``pauser`` (devteam/pause.py) listens for the pause word meanwhile and
    interrupts the session on it; a session that ends without a result event
    returns its id alone, which is what resuming it needs."""
    narrator = Narrator(root)
    seen = {"result": {}, "session_id": None}
    # A text block is printed only once a tool call follows it: the last one
    # is the final report, which is printed in full after the session.
    pending = []

    def handle(line):
        try:
            event = json.loads(line)
        except ValueError:
            print(f"    {line.rstrip()}")
            return
        if event.get("type") == "system" and event.get("subtype") == "init":
            seen["session_id"] = event.get("session_id")
            note_fast = fast_note(event)
            print(f"    session {event.get('session_id')}"
                  + (f"  ({note_fast})" if note_fast else ""))
        elif event.get("type") == "rate_limit_event":
            if on_limits:
                on_limits(event.get("rate_limit_info"))
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
            seen["result"] = event

    with open(log_path, "a") as log:
        proc = subprocess.Popen(cmd, cwd=root, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, env=env,
                                stdin=subprocess.DEVNULL, start_new_session=True)
        watching = pauser.watching if pauser else (lambda on_pause: contextlib.nullcontext())
        try:
            with watching(lambda: interrupt(proc)):
                for line in proc.stdout:
                    log.write(line)
                    log.flush()
                    handle(line)
                proc.wait()
                proc.stdout.close()
        except KeyboardInterrupt:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait()
            raise
    result, session_id = seen["result"], seen["session_id"]
    report = (result.get("result") or "").strip()
    ok = (proc.returncode == 0 and result and not result.get("is_error")
          and not report.startswith((FAIL_MARK, FAB_MARK)))
    if not result and session_id:
        result = {"session_id": session_id, "interrupted": True}
    return bool(ok), report, result
