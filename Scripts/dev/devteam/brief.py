"""What a session must still know once its context has been compacted.

A session's context is summarised when it passes session.COMPACT_WINDOW, and a
summary keeps the gist, not the wording: the task as it was put, the gate's
table and a fix prompt's list of regressions would all come back paraphrased.
So each task keeps two files in the run directory, outside the transcript:

  task-NN-brief.md   every prompt dev-team sent the session, word for word
                     (``add``), in the order it sent them
  task-NN-notes.md   the session's own working notes, which its prompt asks
                     it to keep: the plan, what is decided, what is proven,
                     what is left

and a SessionStart hook on ``compact`` (``hooks``) prints both back into the
session straight after the summary (``render``; this file run as a script is
the hook's command). The standing rules need neither: they are the system
prompt (session.build_system), which no compaction touches.
"""

import os
import shlex
import sys

HEADER = """\
dev-team: this session's context has just been compacted, so what is above is \
a summary. Below is everything dev-team asked of this session, word for word \
and in order (the last is the one in hand), and then the notes you kept. Trust \
these over the summary, and check the tree (`git status`, `git log`) before \
you redo anything."""
NO_NOTES = "(no notes file was kept: rebuild the state from `git status` and `git diff`)"
# A notes file is a page, not a log; one that grew past this is cut to its end.
NOTES_LIMIT = 12000


def paths(run_dir, n):
    """(the brief, the notes) of task ``n``."""
    return (os.path.join(run_dir, f"task-{n:02d}-brief.md"),
            os.path.join(run_dir, f"task-{n:02d}-notes.md"))


def add(path, prompt):
    """Append one prompt dev-team sent to the brief."""
    count = 0
    if os.path.isfile(path):
        with open(path) as f:
            count = sum(1 for line in f if line.startswith("## Prompt "))
    with open(path, "a") as f:
        f.write(f"## Prompt {count + 1}\n\n{prompt.strip()}\n\n")


def _read(path):
    try:
        with open(path, errors="replace") as f:
            return f.read().strip()
    except OSError:
        return ""


def render(brief, notes):
    """What the hook prints: the header, the brief, the notes."""
    kept = _read(notes)
    if len(kept) > NOTES_LIMIT:
        kept = "(the start is cut)\n..." + kept[-NOTES_LIMIT:]
    return "\n\n".join([HEADER, _read(brief) or "(the brief is missing)",
                        f"## Your notes ({notes})", kept or NO_NOTES])


def hooks(brief, notes):
    """The settings fragment that runs ``render`` after every compaction."""
    command = " ".join(shlex.quote(part) for part in
                       ("python3", os.path.abspath(__file__), brief, notes))
    return {"SessionStart": [{"matcher": "compact",
                              "hooks": [{"type": "command", "command": command}]}]}


if __name__ == "__main__":
    print(render(sys.argv[1], sys.argv[2]))
