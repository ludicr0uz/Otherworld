"""Fab assets: the one thing a dev-team session can need but never get itself.

Acquiring from Fab means the user's Epic sign-in, a licence and the plugin's
browser (asset_pipeline/fab_library.py says why), so every acquisition goes
through the user, at the terminal, and nothing else waits for them:

  before a task   each ``fab:`` hint in the task file that the library does not
                  hold yet is asked for before the session starts;
  after a session a report whose first line is FAB-REQUIRED lists what the
                  session found it needs; dev-team asks for those, records them
                  and resumes the session (``--resume``) to carry on.

Asking means: say what is needed and where it should land, wait for the
content path it actually landed in, check that folder holds assets, and record
it in fab_library.json. 's' skips (the task fails, listing what it needed);
'q' stops the run. Without a terminal there is nobody to ask, so the task is
blocked -- failed, with the list -- rather than waited on.

One request per line, in the task file and in a report alike:

    <listing name> | url: <fab.com listing> | at: /Game/<folder> | why: <reason>

Only the name is required.
"""

import re

from asset_pipeline import fab_library

from devteam.accounting import merge_results
from devteam.session import FAB_MARK

FIELDS = ("url", "at", "why")
MAX_ROUNDS = 3          # FAB-REQUIRED -> acquire -> resume, per task


class FabStop(Exception):
    """The user asked to stop the run while being asked for an asset."""


class FabRequest(object):

    def __init__(self, name, url="", at="", why=""):
        self.name, self.url, self.at, self.why = name, url, at, why

    def __repr__(self):
        return f"FabRequest({self.name!r}, url={self.url!r}, at={self.at!r})"

    def line(self):
        parts = [self.name] + [f"{k}: {getattr(self, k)}" for k in FIELDS if getattr(self, k)]
        return " | ".join(parts)


def parse_request(text):
    """One request line (a leading '- ' allowed); None when it names nothing."""
    text = re.sub(r"^[-*](?:\s+|$)", "", text.strip())
    parts = [p.strip() for p in text.split("|")]
    if not parts or not parts[0]:
        return None
    req = FabRequest(parts[0])
    for part in parts[1:]:
        key, _, value = part.partition(":")
        if key.strip().lower() in FIELDS and value.strip():
            setattr(req, key.strip().lower(), value.strip())
    return req


def requests_in(report):
    """The requests of a FAB-REQUIRED report, or [] for any other report.

    The list items after the mark's line, up to the first line that is neither
    an item nor blank."""
    lines = (report or "").strip().splitlines()
    if not lines or not lines[0].startswith(FAB_MARK):
        return []
    out = []
    for line in lines[1:]:
        if not line.strip():
            continue
        if not line.lstrip().startswith(("- ", "* ")):
            break
        req = parse_request(line)
        if req:
            out.append(req)
    return out


def unmet(requests, items, project=fab_library.PROJECT_DIR):
    """The requests the library does not hold, or holds but not on disk."""
    missing = []
    for req in requests:
        item = fab_library.find(items, req.name, req.url)
        if item is None or not fab_library.is_present(item, project):
            missing.append(req)
    return missing


def _ask_one(req, ask, say, project, library):
    say(f"\n  Fab asset needed: {req.name}")
    if req.url:
        say(f"    listing: {req.url}")
    if req.why:
        say(f"    why:     {req.why}")
    default = req.at or fab_library.DEFAULT_ROOT
    say("    Add it to your Fab library and import it into this project -- the Fab\n"
        "    plugin in the editor (Window > Fab), or the launcher's 'Add to project'.\n"
        "    Quit the editor when it has imported; dev-team closes any left open.")
    while True:
        answer = ask(f"    content path it landed in [{default}], s = skip task, "
                     "q = stop run: ").strip()
        if answer.lower() == "q":
            raise FabStop(req.name)
        if answer.lower() == "s":
            return None
        path = answer or default
        item = fab_library.FabItem(req.name, path.rstrip("/"), req.url, note=req.why)
        if fab_library.content_dir(item.content, project) is None:
            say(f"    {path} is not under /Game -- give the /Game/... folder it imported to.")
        elif not fab_library.is_present(item, project):
            say(f"    no assets under {fab_library.content_dir(item.content, project)} yet.")
        else:
            fab_library.record(item, library)
            say(f"    recorded {item.name} -> {item.content}")
            return item


def acquire(requests, ask=input, say=print, interactive=True,
            project=fab_library.PROJECT_DIR, library=fab_library.LIBRARY):
    """Ask the user for each unmet request.

    Returns (the library entry of every request now met, requests still
    unmet). Raises FabStop on 'q'. Asks nothing when not interactive:
    everything unmet stays unmet."""
    todo = unmet(requests, fab_library.load(library), project)
    held = [fab_library.find(fab_library.load(library), r.name, r.url)
            for r in requests if r not in todo]
    if not todo:
        return held, []
    if not interactive:
        say("    Fab: this task needs assets that only you can add, and there is no "
            "terminal to ask on:")
        for req in todo:
            say(f"      - {req.line()}")
        return held, todo
    say(f"    Fab: {len(todo)} asset(s) need your manual action (sessions cannot "
        "sign in to Fab).")
    left = []
    for req in todo:
        item = _ask_one(req, ask, say, project, library)
        if item:
            held.append(item)
        else:
            left.append(req)
    return held, left


def unmet_report(left):
    """The failure report for a task whose Fab needs were not met."""
    return (f"FAILED: needs Fab assets the user has not added ({len(left)}):\n"
            + "\n".join(f"- {r.line()}" for r in left)
            + "\nAdd them (fab_library.py --add), then re-run the task.")


RESUME = """\
The user added the Fab assets you asked for:

{items}

They are recorded in Scripts/asset_pipeline/fab_library.json. First refresh \
the index -- `python3 Scripts/dev/uepy.py Scripts/asset_pipeline/fab_index.py` \
-- and read assets/cache/fab/index.md, then carry on with the task and end \
with the same kind of report."""


def build_resume_prompt(items):
    return RESUME.format(items="\n".join(f"- {i.name} -> {i.content}" for i in items))


EDITOR_LEFT = ("FAILED: an editor of this project was still running after the Fab "
               "import and could not be closed")


def preflight(hints, close_editors, **ask):
    """Before a session: ask for the task's ``fab:`` hints that are unmet.

    None when the task may start, else its failure report. ``ask`` goes to
    acquire() (ask, say, interactive, project, library)."""
    requests = [r for r in map(parse_request, hints) if r]
    if not requests:
        return None
    _items, left = acquire(requests, **ask)
    if left:
        return unmet_report(left)
    if not close_editors():
        return EDITOR_LEFT
    return None


def follow_up(ok, report, result, resume, close_editors, **ask):
    """After a session: serve its FAB-REQUIRED reports.

    Each one is asked of the user, then the session is resumed with
    resume(prompt) -> (ok, report, result), up to MAX_ROUNDS times. Returns
    (ok, every report in order, the merged result)."""
    reports, rounds = [report], 0
    while True:
        requests = requests_in(report)
        if not requests:
            return ok, reports, result
        if rounds == MAX_ROUNDS or not result.get("session_id"):
            reports.append(f"FAILED: the session still needs Fab assets after "
                           f"{rounds} round(s) of adding them")
            return False, reports, result
        rounds += 1
        items, left = acquire(requests, **ask)
        if left:
            reports.append(unmet_report(left))
            return False, reports, result
        if not close_editors():
            reports.append(EDITOR_LEFT)
            return False, reports, result
        ok, report, more = resume(build_resume_prompt(items))
        result = merge_results(result, more)
        reports.append(report)
