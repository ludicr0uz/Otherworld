"""Pause and resume: park a task's work on a branch, pick it up again later.

Typing ``pause`` (and Enter) at the terminal of a running dev-team stops the
task in hand:

  1. its session is interrupted (SIGINT to its process group, then harder);
  2. everything uncommitted (but the task file, whose ticks belong to the
     run) is committed as one WIP commit on a new branch,
     ``paused/<task>-<time>``, and the branch the run was on is checked out
     again, so the tree is clean and free for other work;
  3. the session's transcript is copied to Saved/DevTeam/paused/<name>/, with
     a record of where the task had got to (pause.json).

``dev-team resume <branch>`` checks the branch out, takes the WIP commit off
again (the work is uncommitted once more, as the session left it), puts the
transcript back if Claude Code has cleaned it up meanwhile, and resumes the
same session. When the task then finishes, the branch it was paused from is
fast-forwarded to it if it has not moved, and the pause branch deleted.

The WIP commit holds *everything* that was uncommitted, edits that were there
before the task began included: they are parked with the task and come back
with it. A commit the session had already made stays on the branch it made it
on. If the WIP commit is refused (the pre-commit hook: a file over 5 MB, or
content), nothing is parked: the work stays uncommitted where it is, and the
pause is resumed by its name instead of a branch.

``pause`` is read only while a session or a verifier sweep is running, never
while dev-team itself is asking something at the terminal (a Fab asset).

Typing ``stop`` instead lets the task in hand finish (session, gate and
write-up as usual) and ends the run after it, with the rest of the queue not
run: no session is interrupted and nothing is parked. ``pause`` typed after
``stop`` still pauses at once.
"""

import contextlib
import glob
import json
import os
import re
import select
import shutil
import signal
import threading
import time

from devteam.accounting import git

WORD = "pause"
STOP_WORD = "stop"                  # the run ends once the task in hand is done
MARK = "Dev-Team-Pause"             # the WIP commit's trailer: the pause's name
MANIFEST = "pause.json"
INTERRUPT_WAITS = ((signal.SIGINT, 20.0), (signal.SIGTERM, 10.0), (signal.SIGKILL, 5.0))


class Paused(Exception):
    """Raised through a task when the user paused it. ``stage`` is where it
    had got to: "start" (no session yet), "session" (one was interrupted) or
    "gate" (its session had ended; the verifier gate had not)."""

    def __init__(self, stage, result=None, baseline=None, reports=None):
        Exception.__init__(self, stage)
        self.stage, self.result = stage, result or {}
        self.baseline, self.reports = baseline, list(reports or [])


class Pauser(object):
    """Listens for the pause word on a stream while told to.

    ``with pauser.watching(on_pause):`` reads lines from the stream for as
    long as the block runs; the pause word sets ``requested`` and calls
    on_pause once, from the listening thread. The stop word sets
    ``stop_requested`` and interrupts nothing: the run's loop reads it once
    the task in hand is done. Outside a block nothing is read, so a prompt
    dev-team itself puts to the user gets its answer."""

    def __init__(self, stream, enabled=True, say=print):
        self.stream, self.enabled, self.say = stream, enabled, say
        self.requested = False
        self.stop_requested = False

    def _listen(self, done, on_pause):
        while not done.is_set() and not self.requested:
            try:
                ready, _, _ = select.select([self.stream], [], [], 0.2)
            except (OSError, ValueError):
                return
            if not ready:
                continue
            line = self.stream.readline()
            if not line:                    # EOF: no terminal to hear from
                self.enabled = False
                return
            word = line.strip().lower()
            if word == WORD:
                self.requested = True
                self.say("\ndev-team: pausing -- stopping the work in hand")
                if on_pause:
                    on_pause()
            elif word == STOP_WORD:
                if not self.stop_requested:
                    self.stop_requested = True
                    self.say("\ndev-team: stopping after this task -- the rest of the "
                             f"queue will not run (type '{WORD}' to stop it now)")
            elif word:
                self.say(f"    (type '{WORD}' and Enter to pause this task, "
                         f"'{STOP_WORD}' to stop after it)")

    @contextlib.contextmanager
    def watching(self, on_pause=None):
        if not self.enabled or self.requested:
            yield self
            return
        done = threading.Event()
        thread = threading.Thread(target=self._listen, args=(done, on_pause), daemon=True)
        thread.start()
        try:
            yield self
        finally:
            done.set()
            thread.join()


def interrupt(proc, waits=None):
    """Stop a session and everything it started (its process group): asked
    first, so Claude Code closes its transcript, then made to."""
    for sig, wait in waits or INTERRUPT_WAITS:
        try:
            os.killpg(proc.pid, sig)
        except (ProcessLookupError, PermissionError):
            return
        deadline = time.time() + wait
        while time.time() < deadline:
            if proc.poll() is not None:
                return
            time.sleep(0.1)


# ---- the session's transcript --------------------------------------------

def claude_projects():
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(
        os.path.expanduser("~"), ".claude")
    return os.path.join(base, "projects")


def transcript(session_id, projects=None):
    """Where Claude Code keeps a session: its .jsonl, or None."""
    if not session_id:
        return None
    hits = glob.glob(os.path.join(projects or claude_projects(), "*", session_id + ".jsonl"))
    return hits[0] if hits else None


def backup_session(session_id, into, projects=None):
    """Copy a session's transcript (and its side directory, if it has one)
    into ``into``. Returns the transcript's own path, or None if not found."""
    source = transcript(session_id, projects)
    if not source:
        return None
    os.makedirs(into, exist_ok=True)
    shutil.copy2(source, os.path.join(into, os.path.basename(source)))
    side = source[: -len(".jsonl")]
    if os.path.isdir(side):
        shutil.copytree(side, os.path.join(into, os.path.basename(side)),
                        dirs_exist_ok=True)
    return source


def restore_session(session_id, backup, source):
    """Put a backed-up transcript back where Claude Code looks for it, unless
    it is still there. True if the session can be resumed."""
    if not session_id:
        return False
    if source and os.path.isfile(source):
        return True
    saved = os.path.join(backup, session_id + ".jsonl")
    if not (source and os.path.isfile(saved)):
        return False
    os.makedirs(os.path.dirname(source), exist_ok=True)
    shutil.copy2(saved, source)
    side = os.path.join(backup, session_id)
    if os.path.isdir(side):
        shutil.copytree(side, source[: -len(".jsonl")], dirs_exist_ok=True)
    return True


# ---- the branch ------------------------------------------------------------

def slug(title, stamp):
    words = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40].strip("-")
    return f"{words or 'task'}-{stamp}"


def current_branch(root):
    return git(root, "branch", "--show-current").stdout.strip()


def is_wip(root, name, rev="HEAD"):
    """True if ``rev`` is the WIP commit of the pause called ``name``."""
    body = git(root, "log", "-1", "--format=%B", rev).stdout
    return f"{MARK}: {name}" in body


def _dirty(root, keep=()):
    """The uncommitted paths, less the ones a pause leaves alone."""
    lines = git(root, "status", "--porcelain").stdout.splitlines()
    return [l[3:] for l in lines if l[3:].strip('"') not in keep]


def park(root, name, title, branch=None, original=None, keep=()):
    """Commit everything uncommitted (but the ``keep`` paths) as a WIP commit
    on the pause's branch and go back to the branch the work was on.
    ``branch`` and ``original`` are given when the work is already on its
    pause branch: a resumed task paused again.

    Returns (branch or None, original branch, error or None); a branch of
    None means nothing was parked and the work is still uncommitted here."""
    made_here = branch is None
    if made_here:
        original = current_branch(root)
        branch = f"paused/{name}"
        made = git(root, "switch", "-c", branch)
        if made.returncode:
            return None, original, f"could not create {branch}: {made.stderr.strip()}"
    git(root, "add", "-A", "--", ".", *(f":(exclude){k}" for k in keep))
    done = git(root, "commit", "--allow-empty", "-m",
               f"WIP: {title}\n\nPaused by dev-team; `dev-team resume {branch}` takes this "
               f"commit off again and carries on.\n\n{MARK}: {name}")
    if done.returncode:
        why = (done.stdout + done.stderr).strip()
        git(root, "reset", "-q")
        if made_here and original:
            git(root, "switch", original)
            git(root, "branch", "-D", branch)
            return None, original, f"the WIP commit was refused:\n{why}"
        return None, original, f"the WIP commit was refused (still on {branch}):\n{why}"
    if original and git(root, "switch", original).returncode:
        return branch, original, f"parked on {branch}, but could not go back to {original}"
    return branch, original, None


def unpark(root, name, branch, keep=()):
    """Check the pause's branch out and take its WIP commit off, leaving the
    work uncommitted. Returns an error, or None."""
    if current_branch(root) != branch:
        dirty = _dirty(root, keep)
        if dirty:
            return (f"{len(dirty)} uncommitted change(s) in the working tree "
                    f"({', '.join(dirty[:3])}{', ...' if len(dirty) > 3 else ''}): commit "
                    "or stash them before resuming, since the paused work is checked "
                    "out over them")
        moved = git(root, "switch", branch)
        if moved.returncode:
            return f"could not check out {branch}: {moved.stderr.strip()}"
    if is_wip(root, name):
        undone = git(root, "reset", "-q", "HEAD~1")
        if undone.returncode:
            return f"could not take the WIP commit off: {undone.stderr.strip()}"
    return None


def land(root, branch, original):
    """After a resumed task finished: fast-forward the branch it was paused
    from, if that has not moved, and delete the pause branch. Returns one
    line saying where the work is now."""
    if not original or not branch or original == branch:
        return f"the work is on {branch or current_branch(root)}"
    if git(root, "merge-base", "--is-ancestor", original, branch).returncode:
        return (f"{original} has moved since the pause, so the work stays on {branch}: "
                f"merge it when you are ready")
    # Move the name, then change to it: the same commit, so nothing uncommitted
    # (the task file's tick, edits parked with the task) is in the way.
    if (git(root, "branch", "-f", original, branch).returncode
            or git(root, "switch", original).returncode):
        return f"could not move {original} up; the work stays on {branch}"
    git(root, "branch", "-d", branch)
    return f"{original} now has the work; {branch} is deleted"


# ---- the record ------------------------------------------------------------

def pause_dir(log_root, name):
    return os.path.join(log_root, "paused", name)


def save(log_root, name, record):
    into = pause_dir(log_root, name)
    os.makedirs(into, exist_ok=True)
    path = os.path.join(into, MANIFEST)
    with open(path + ".tmp", "w") as fh:
        json.dump(dict(record, name=name), fh, indent=1)
    os.replace(path + ".tmp", path)
    return into


def find(log_root, wanted):
    """The record of the pause called, or parked on the branch called,
    ``wanted`` -- or None."""
    for path in sorted(glob.glob(os.path.join(log_root, "paused", "*", MANIFEST))):
        try:
            with open(path) as fh:
                record = json.load(fh)
        except (OSError, ValueError):
            continue
        if wanted in (record.get("name"), record.get("branch"),
                      f"paused/{record.get('name')}"):
            return record
    return None


def listing(log_root):
    """One line per pause on record, newest last."""
    lines = []
    for path in sorted(glob.glob(os.path.join(log_root, "paused", "*", MANIFEST)),
                       key=os.path.getmtime):
        try:
            with open(path) as fh:
                r = json.load(fh)
        except (OSError, ValueError):
            continue
        lines.append(f"  {r.get('branch') or r.get('name')}  -- {r.get('title', '?')}")
    return lines


def forget(log_root, name):
    shutil.rmtree(pause_dir(log_root, name), ignore_errors=True)
