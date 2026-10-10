"""One task from start to finish: its session, the verifier gate round it, the
write-up -- and being paused part way and picked up again (devteam/pause.py).

dev-team's loop calls ``run_one`` per task and ``write_up`` after it. A typed
``pause`` surfaces from ``run_one`` as pause.Paused, which ``park_task`` turns
into a branch, a session backup and a record; ``resume`` is the other half,
behind ``dev-team resume <branch>``.
"""

import datetime
import hashlib
import os
import time

from devteam import baseline_cache, fab, gate, limits, pause, probe_gate
from devteam.accounting import (
    describe_time, describe_tokens, git, git_head, merge_results, tag_commit,
    token_usage,
)
from devteam.session import (
    build_cmd, build_fix_prompt, build_limit_resumed_prompt, build_prompt,
    build_resumed_prompt, build_uncommitted_prompt, run_session, session_env,
)
from devteam.tasks import Task, tick
from uepylib import editors, server

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "..", ".."))
LOG_ROOT = os.path.join(ROOT, "Saved", "DevTeam")
SERVE_DIR = os.path.join(ROOT, "Saved", "uepy", "devteam")

# What a pause keeps of the run's options, for the resumed half of the task.
KEPT_ARGS = ("commit", "gate", "permission_mode", "fix_attempts", "budget",
             "model", "effort")
TASK_FIELDS = ("text", "line", "effort", "model", "triage", "fast", "fab")


def close_editors():
    """True when no editor of the project is left running, the session's warm
    one included (asked to stop first; close_editors would only signal it)."""
    if server.stop(SERVE_DIR):
        print("    stopped the session's warm editor")
    _closed, left = editors.close_editors()
    for proc in left:
        print(f"    could not close {proc.binary} {proc.pid}")
    return not left


def tree_state():
    """What a sweep's result depends on: HEAD plus the uncommitted changes."""
    return (git(ROOT, "rev-parse", "HEAD").stdout.strip(),
            git(ROOT, "status", "--porcelain").stdout)


def tree_fingerprint():
    """What the working tree holds beyond HEAD, as one hash: the diff against
    HEAD (an edit to a file that was already dirty changes it) and the list
    of untracked files."""
    digest = hashlib.sha1()
    for out in (git(ROOT, "diff", "HEAD").stdout, git(ROOT, "status", "--porcelain").stdout):
        digest.update(out.encode("utf-8", "replace"))
    return digest.hexdigest()


def _sweep_and_probes(log_path, probe_set, serve_dir=None):
    rows = gate.run_sweep(ROOT, log_path, serve_dir)
    if rows is not None and probe_set:
        rows.update(probe_gate.run_probes(ROOT, probe_set, log_path))
    return rows


def sweep(label, log_path, pauser=None, probe_set=None, warm=False, timings=None):
    """One verifier sweep, then the probe set if there is one. A pause typed
    meanwhile is heard, and acted on by the caller once the sweep is back."""
    started = time.time()
    serve = SERVE_DIR if warm else None
    if pauser:
        with pauser.watching():
            rows = _sweep_and_probes(log_path, probe_set, serve)
    else:
        rows = _sweep_and_probes(log_path, probe_set, serve)
    if timings is not None:
        timings[label] = f"{time.time() - started:.0f}s" + (" (warm)" if warm else " (cold)")
    if rows is None:
        print(f"    gate: {label} sweep failed to run ({time.time() - started:.0f}s)")
    else:
        bad = [l for l, r in rows.items() if not r.get("ok")]
        print(f"    gate: {label} {len(rows)} suites, "
              + (f"failing: {', '.join(bad)}" if bad else "all passing")
              + f" ({time.time() - started:.0f}s)")
    return rows


def run_one(task, n, total, args, run_dir, progress, cache, meter, pauser=None,
            parked=None):
    """One task, gate included -- or, given ``parked`` (a pause's record), the
    rest of one that was paused.

    Returns (ok, reports, result, gate_table, final sweep or None). Raises
    pause.Paused when the user paused it."""
    log_path = os.path.join(run_dir, f"task-{n:02d}.jsonl")
    sweep_log = os.path.join(run_dir, f"task-{n:02d}-sweeps.txt")
    timings = {}
    env = session_env(os.environ, SERVE_DIR)
    ask = dict(interactive=args.interactive)
    baseline = parked.get("baseline") if parked else None
    probes = getattr(args, "probe_set", None)
    ran = probe_gate.labels(probes)         # what an after-sweep is asked for

    def paused(stage, result=None, reports=None):
        if pauser and pauser.requested:
            raise pause.Paused(stage, result, baseline, reports)

    def session(prompt, opts, **how):
        """One session -- waited for when the session limit is spent, and
        when the limit stops it part way, waited for again and resumed (or
        started over, if it had not begun). Returns (ok, report, result)."""
        limits.wait(meter, pauser)
        if pauser and pauser.requested:        # paused while waiting: nothing ran
            return False, "", {"session_id": how.get("resume"), "interrupted": True}
        ok, report, result = run_session(build_cmd(prompt, args.permission_mode, **how, **opts),
                                         ROOT, log_path, env, meter.see, pauser)
        while limits.limited(result):
            print(f"    the session limit stopped this session ({limits.clock(time.time())})")
            limits.wait(meter, pauser, refused=True)
            if pauser and pauser.requested:
                break
            if result.get("session_id"):
                again = dict(how, resume=result["session_id"])
                again.pop("name", None)
                ok, report, more = run_session(
                    build_cmd(build_limit_resumed_prompt(args.commit), args.permission_mode,
                              **again, **opts), ROOT, log_path, env, meter.see, pauser)
                result = merge_results(result, more)
            else:
                ok, report, result = run_session(
                    build_cmd(prompt, args.permission_mode, **how, **opts),
                    ROOT, log_path, env, meter.see, pauser)
        return ok, report, result

    def ensure_committed(ok, reports, result, head0, tree0):
        """A session that ended well but left new changes uncommitted (six of
        77 did, each waiting on a background run) is sent back once to commit."""
        if not (ok and args.commit and result.get("session_id")):
            return ok, reports, result
        if git_head(ROOT) != head0 or tree_fingerprint() == tree0:
            return ok, reports, result
        print("    the session ended without committing while the tree changed; "
              "sending it back to finish")
        ok, report, more = session(build_uncommitted_prompt(), common,
                                   resume=result["session_id"])
        return ok, reports + [report], merge_results(result, more)

    if parked is None:
        blocked = fab.preflight(task.fab, close_editors, **ask)
        if blocked:
            return False, [blocked], {}, None, None
        if args.gate:
            state = tree_state()
            baseline = cache.get(state)
            if baseline is None:
                baseline = baseline_cache.load(ROOT, state, ran)
                if baseline:
                    print("    gate: baseline from the cache (tree unchanged)")
                    timings["baseline"] = "cached"
            if baseline is None:
                baseline = sweep("baseline", sweep_log, pauser, probes, warm=True,
                                 timings=timings)
                baseline_cache.save(ROOT, state, baseline, ran)
        limits.wait(meter, pauser)
        paused("start")
        prompt = build_prompt(task, n, total, progress,
                              gate.table(baseline) if baseline else None, args.commit)
        # Decided once: the task's follow-ups keep the speed its session began at.
        task.fast, why = meter.decide(time.time())
        print(f"    fast mode {'on' if task.fast else 'off'} -- {why}")
    common = dict(model=task.model or args.model, effort=task.effort or args.effort,
                  budget=args.budget, fast=task.fast)
    earlier = list(parked.get("reports") or []) if parked else []
    head0, tree0 = git_head(ROOT), tree_fingerprint()
    if parked is None:
        ok, report, result = session(prompt, common,
                                     name=f"dev-team {n}/{total}: {task.title}")
    elif parked["stage"] == "session":
        result = parked.get("result") or {}
        ok, report, more = session(build_resumed_prompt(parked.get("branch"), args.commit),
                                   common, resume=result["session_id"])
        result = merge_results(result, more)
    else:                                   # its session had ended; the gate had not
        ok, report, result = True, earlier.pop() if earlier else "", parked.get("result") or {}
    paused("session", result, earlier)

    def resume(follow_prompt):
        return session(follow_prompt, common, resume=result["session_id"])

    ok, reports, result = fab.follow_up(ok, report, result, resume, close_editors, **ask)
    reports = earlier + reports
    paused("session", result, reports[:-1])
    ok, reports, result = ensure_committed(ok, reports, result, head0, tree0)
    paused("session", result, reports[:-1])
    gate_table = None
    if not (ok and args.gate):
        return ok, reports, result, gate_table, None
    close_editors()
    after = sweep("after", sweep_log, pauser, probes, timings=timings)
    paused("gate", result, reports)
    problems = gate.regressions(baseline, after, gate.load_known(), ran)
    attempts = 0
    while problems and attempts < args.fix_attempts and result.get("session_id"):
        attempts += 1
        print(f"    gate: {len(problems)} regression(s); sending the session back "
              f"({attempts}/{args.fix_attempts})")
        for p in problems:
            print(f"      - {p[:200]}")
        fix = build_fix_prompt(problems, gate.table(baseline, after, probes=ran), args.commit)
        # Triage guessed low and the gate disagrees: fix at the default effort.
        fix_opts = dict(common, effort=args.effort) if task.triage else common
        head0, tree0 = git_head(ROOT), tree_fingerprint()
        ok, report, fixed = session(fix, fix_opts, resume=result["session_id"])
        result = merge_results(result, fixed)
        paused("session", result, reports)
        reports.append(report)
        ok, reports, result = ensure_committed(ok, reports, result, head0, tree0)
        paused("session", result, reports)
        if not ok:
            break
        after = sweep("after fix", sweep_log, pauser, probes, timings=timings)
        paused("gate", result, reports)
        problems = gate.regressions(baseline, after, gate.load_known(), ran)
    gate_table = gate.table(baseline, after, timings, ran)
    if problems:
        ok = False
        reports.append("FAILED: the verifier gate still regresses:\n"
                       + "\n".join(f"- {p}" for p in problems))
    return ok, reports, result, gate_table, after


def write_up(task, n, ok, args, before, reports, result, gate_table, run_dir, progress,
             note=""):
    """Print a finished task's outcome, record it in progress.md and put the
    time and token trailers on its commit. Returns (status, cost)."""
    cost = result.get("total_cost_usd") or 0.0
    status = "done" if ok else "FAILED"
    tokens = describe_tokens(token_usage(result), cost)
    took = describe_time(result.get("duration_ms"))
    after = git_head(ROOT)
    if before and after and after != before:
        after = tag_commit(ROOT, before, after, took, tokens)
    commits = f", commits {before}..{after}" if after and after != before else ""
    print(f"    {status} in {took}, ${cost:.2f}{commits}  (log: {run_dir})")
    print(f"    tokens {tokens}")
    report = "\n\n".join(r for r in reports if r)
    if report:
        print("    " + report.replace("\n", "\n    "))
    with open(progress, "a") as f:
        f.write(f"\n## Task {n}: {status}{note}\n\n{task.text}\n\n"
                f"Session: {result.get('session_id', '?')}{commits}\n"
                f"Time: {took}\nTokens: {tokens}\n"
                f"Effort: {task.effort or args.effort or 'default'}"
                + (f" (triage: {task.triage})" if task.triage else "")
                + (", fast mode" if task.fast else "") + "\n\n"
                + (f"### Verifier gate\n\n{gate_table}\n\n" if gate_table else "")
                + f"### Report\n\n{report or '(no report)'}\n")
    return status, cost


def _kept(task_file):
    """The paths a pause leaves alone: the task file, whose ticks belong to
    the run and not to the task in hand."""
    if not task_file:
        return []
    rel = os.path.relpath(task_file, ROOT)
    return [] if rel.startswith("..") else [rel]


def park_task(stop, task, n, total, args, run_dir, before, task_file, parked=None):
    """Act on a pause: park the work, back the session up, write the record.
    ``parked`` is the earlier record when a resumed task is paused again."""
    if stop.stage == "start":
        print("dev-team: paused before this task's session began -- nothing to park; "
              "it stays unticked and the next run takes it")
        return
    if server.stop(SERVE_DIR):
        print("    stopped the session's warm editor")
    stamp = datetime.datetime.now().strftime("%m%d-%H%M")
    name = parked["name"] if parked else pause.slug(task.title, stamp)
    session_id = stop.result.get("session_id")
    into = pause.pause_dir(LOG_ROOT, name)
    source = pause.backup_session(session_id, os.path.join(into, "session"))
    branch, original, error = pause.park(
        ROOT, name, task.title, branch=parked.get("branch") if parked else None,
        original=parked.get("original") if parked else None, keep=_kept(task_file))
    pause.save(LOG_ROOT, name, dict(
        branch=branch, original=original, title=task.title, stage=stop.stage,
        task={k: getattr(task, k) for k in TASK_FIELDS}, task_file=task_file,
        n=n, total=total, run_dir=run_dir, before=before, result=stop.result,
        baseline=stop.baseline, reports=stop.reports, session_source=source,
        args={k: getattr(args, k) for k in KEPT_ARGS},
        paused_at=datetime.datetime.now().isoformat(timespec="seconds")))
    print(f"dev-team: paused -- {task.title}")
    if error and branch:
        print(f"    {error}")
    elif error:
        print(f"    not parked on a branch: {error}")
        print("    the work is left uncommitted where it is")
    else:
        print(f"    work parked on {branch} (one WIP commit); back on {original}")
    print(f"    session {session_id or '?'} "
          + (f"backed up in {into}" if source else "has no transcript to back up"))
    print(f"    carry on with:  Scripts/dev/dev-team resume {branch or name}")


def resume(args, wanted, meter, pauser):
    """``dev-team resume <branch>``: the rest of a paused task. Returns the
    exit code."""
    record = pause.find(LOG_ROOT, wanted)
    if not record:
        known = pause.listing(LOG_ROOT)
        print(f"dev-team: no paused task called {wanted}"
              + ("; these are on record:\n" + "\n".join(known) if known
                 else " (none is on record)"))
        return 1
    name, branch = record["name"], record.get("branch")
    task = Task(record["task"]["text"])
    for key in TASK_FIELDS:
        setattr(task, key, record["task"].get(key))
    for key, value in (record.get("args") or {}).items():
        setattr(args, key, value)
    print(f"dev-team: resuming -- {task.title}")
    session_id = (record.get("result") or {}).get("session_id")
    backup = os.path.join(pause.pause_dir(LOG_ROOT, name), "session")
    if record["stage"] == "session" and not pause.restore_session(
            session_id, backup, record.get("session_source")):
        print(f"dev-team: session {session_id} has no transcript, here or in {backup}; "
              "it cannot be resumed")
        return 1
    if not close_editors():
        print("dev-team: stopping -- an editor of this project is still running")
        return 1
    if branch:
        error = pause.unpark(ROOT, name, branch, keep=_kept(record.get("task_file")))
        if error:
            print(f"dev-team: {error}")
            return 1
        print(f"    on {branch}, the parked work uncommitted again")
    run_dir = record.get("run_dir") or ""
    if not os.path.isdir(run_dir):
        run_dir = os.path.join(LOG_ROOT, datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
        os.makedirs(run_dir)
    progress = os.path.join(run_dir, "progress.md")
    n, total = record.get("n") or 1, record.get("total") or 1
    try:
        ok, reports, result, gate_table, _swept = run_one(
            task, n, total, args, run_dir, progress, {}, meter, pauser, parked=record)
    except pause.Paused as stop:
        park_task(stop, task, n, total, args, run_dir, record.get("before"),
                  record.get("task_file"), parked=record)
        return 1
    except KeyboardInterrupt:
        print(f"\ndev-team: interrupted -- the work is uncommitted on "
              f"{branch or 'this branch'}; resume {branch or name} again to carry on")
        return 1
    finally:
        if server.stop(SERVE_DIR):
            print("    stopped the session's warm editor")
    write_up(task, n, ok, args, record.get("before"), reports, result, gate_table,
             run_dir, progress, note=" (resumed after a pause)")
    pause.forget(LOG_ROOT, name)
    if not ok:
        print(f"dev-team: the resumed task failed; its work is on {branch or 'this branch'}")
        return 1
    if branch:
        print(f"dev-team: {pause.land(ROOT, branch, record.get('original'))}")
    task_file = record.get("task_file")
    if task_file and task.line is not None and os.path.isfile(task_file):
        tick(task_file, task)
    return 0
