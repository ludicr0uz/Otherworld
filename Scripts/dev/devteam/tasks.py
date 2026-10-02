"""The task file: a Markdown list, one top-level item per task.

Indented or following lines up to the next item belong to the item, so a task
can run to several paragraphs. Headings and text before the first item are
ignored. A continuation line of the form ``effort: <level>`` or
``model: <name>`` is a hint for that task's session, not part of its text.
So is ``fab: <request>`` (devteam/fab.py has the format), which may repeat:
a Fab asset the task needs, asked of the user before its session starts:

    - [ ] Raise the inventory size to 12.
          effort: low
    - [ ] Add a campfire that raises Temperature within 5 m.
          It should burn for 3 minutes, then go out.
          model: opus
    - [ ] Give the wanderers the Game Animation Sample's locomotion.
          fab: Game Animation Sample | at: /Game/GameAnimationSample

The file is the queue for the whole run, not only at its start: dev-team reads
it again after each task (``requeue``), so an item added while a session was
working is run in the same run, and a waiting one ticked or deleted is not.
"""

import re

ITEM = re.compile(r"^(?:[-*+]|\d+[.)])\s+(?:\[( |x|X)\]\s+)?(.*)$")
HINT = re.compile(r"^(effort|model):\s*(\S+)\s*$", re.IGNORECASE)
FAB_HINT = re.compile(r"^fab:\s*(\S.*?)\s*$", re.IGNORECASE)


class Task(object):

    def __init__(self, text, line=None, done=False, effort=None, model=None, fab=None):
        self.text, self.line, self.done = text, line, done
        self.effort, self.model = effort, model
        self.triage = None          # why devteam/triage.py lowered the effort
        self.fab = list(fab or [])

    @property
    def title(self):
        first = self.text.splitlines()[0]
        return first if len(first) <= 70 else first[:67] + "..."


def parse_tasks(source):
    """Top-level list items of a Markdown file, with their continuation lines."""
    tasks, current = [], None
    for i, raw in enumerate(source.splitlines()):
        m = ITEM.match(raw)
        if m:
            current = Task(m.group(2).strip(), line=i,
                           done=(m.group(1) or " ").lower() == "x")
            tasks.append(current)
        elif current and raw.strip() and not raw.startswith("#"):
            hint, fab = HINT.match(raw.strip()), FAB_HINT.match(raw.strip())
            if fab:
                current.fab.append(fab.group(1))
            elif hint:
                setattr(current, hint.group(1).lower(), hint.group(2))
            else:
                current.text += "\n" + raw.strip()
        elif current and not raw.strip():
            current.text += "\n"
    for t in tasks:
        t.text = t.text.strip()
    return [t for t in tasks if t.text]


def requeue(pending, attempted, fresh):
    """The queue once the task file has been read again, mid-run.

    ``pending`` are the tasks still waiting, ``attempted`` the ones this run
    has already run that are still unticked (a failure under --keep-going, or
    one ``tick`` could not find), ``fresh`` the file as it parses now. Returns
    (queue, added, dropped): the file's unticked items in file order, less the
    attempted ones; which of them were not waiting before; and which waiting
    ones are gone from the file or ticked there.

    A task is known by its text, so one reworded while it waits counts as
    dropped and added. A waiting task keeps the effort triage gave it unless
    the file now has a hint of its own.
    """
    tried = [t.text for t in attempted]
    waiting = list(pending)
    queue, added = [], []
    for task in fresh:
        if task.done:
            continue
        if task.text in tried:
            # One item per attempt: a second copy of a failed task is new work.
            tried.remove(task.text)
            continue
        was = next((t for t in waiting if t.text == task.text), None)
        if was is None:
            added.append(task)
        else:
            waiting.remove(was)
            if was.triage and not task.effort:
                task.effort, task.triage = was.effort, was.triage
        queue.append(task)
    return queue, added, waiting


def tick(path, task):
    """Mark one task done in its file, touching nothing else. False if the
    task is no longer there to tick."""
    try:
        with open(path) as f:
            lines = f.read().split("\n")
    except OSError as exc:
        print(f"    (could not read {path} to tick this task: {exc})")
        return False
    # The file may have been edited during the run: find the item again by its
    # first line rather than trusting the line number it had at parse time.
    first = task.text.splitlines()[0]
    hits = [i for i, l in enumerate(lines)
            if (m := ITEM.match(l)) and m.group(2).strip() == first
            and (m.group(1) or " ") == " "]
    if not hits:
        print(f"    (could not find this task in {path} to tick it)")
        return False
    task.line = min(hits, key=lambda i: abs(i - task.line))
    line = lines[task.line]
    if re.match(r"^\s*(?:[-*+]|\d+[.)])\s+\[ \]", line):
        line = line.replace("[ ]", "[x]", 1)
    else:
        line = re.sub(r"^((?:[-*+]|\d+[.)])\s+)", r"\1[x] ", line, count=1)
    lines[task.line] = line
    with open(path, "w") as f:
        f.write("\n".join(lines))
    return True
