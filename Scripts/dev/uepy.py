#!/usr/bin/env python3
"""Run Unreal Python without paying for an editor boot every time.

A cold ``UnrealEditor-Cmd -ExecutePythonScript`` costs 35-45 s of boot and
shutdown *regardless of what the script does* -- a script that dies on line 13
still takes ~33 s. That is the dominant cost of iterating on this project: a
session spending 22 minutes can easily have 10 of them in boots.

This runner sends the script to an editor that is **already open** over the
Python plugin's remote-execution channel (UDP discovery on 239.0.0.1:6766, then
a TCP command connection), which turns those 40 s into about one. It falls back
to a cold ``UnrealEditor-Cmd`` when no editor is listening, so the same command
line works either way and nothing has to be remembered about the current state
of the machine.

    Scripts/dev/uepy.py Scripts/build_npc_blueprints.py
    Scripts/dev/uepy.py Scripts/verify_*.py          # many, ONE boot/connection
    Scripts/dev/uepy.py -c "import unreal; unreal.log_warning('hi')"
    Scripts/dev/uepy.py --list                       # what is listening?
    Scripts/dev/uepy.py --game --seconds 25          # headless -game run
    Scripts/dev/uepy.py --cold Scripts/verify_level.py   # force a fresh editor

Several scripts in one invocation share a single connection (or a single boot in
cold mode), which is the other half of the speed-up: three verifiers cost one
boot, not three.

Requires ``bRemoteExecution=True`` under ``[/Script/PythonScriptPlugin.
PythonScriptPluginUserSettings]`` in Config/DefaultEngine.ini -- this project
already sets it. Remote execution only reaches an editor with a **UI**; a
``-NoUI`` commandlet does not register as a node.
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(HERE))       # Scripts/dev -> root

# Discovery timings. The plugin pings once a second, so a node that exists is
# normally seen well inside two seconds; the wait is cheap next to what it
# saves, but a miss costs a full cold boot, so do not trim it too far.
DISCOVERY_SECONDS = 2.5
DISCOVERY_POLL = 0.1

# A -game run long enough to see every NPC spawn and the first chase decisions.
# Spawn-path bugs show up in the first two seconds; only respawn *statistics*
# need the 90 s runs, so that is the flag, not the default.
GAME_SECONDS = 25
DEFAULT_MAP = "/Game/Maps/Lvl_Forest_200m"

# Lines worth pulling out of a -game log without being asked.
GAME_PATTERNS = (
    ("blueprint runtime errors", r"Blueprint Runtime Error"),
    ("accessed None", r"Accessed None"),
    ("script warnings", r"LogScript: Warning"),
    ("NPC spawns", r"NPC-SPAWN"),
    ("NPC falls", r"NPC-FELL"),
)


def log(msg):
    print(f"[uepy] {msg}", flush=True)


# ─── Locating the engine ────────────────────────────────────────────────────

def engine_dir(override=None):
    """Find the engine this project is built against.

    Preference order: an explicit --engine, then $UE_ENGINE_DIR, then the
    highest-numbered UE_* under the standard Epic install root. The .uproject's
    EngineAssociation is deliberately not consulted: on a launcher install it is
    a GUID that needs the Epic manifests to resolve, which is more moving parts
    than a glob for the same answer.
    """
    for candidate in (override, os.environ.get("UE_ENGINE_DIR")):
        if candidate:
            if not os.path.isdir(candidate):
                sys.exit(f"[uepy] no engine at {candidate}")
            return candidate
    roots = sorted(glob.glob("/Users/Shared/Epic Games/UE_*/Engine"))
    if not roots:
        sys.exit("[uepy] no engine found -- pass --engine or set UE_ENGINE_DIR")
    return roots[-1]


PROJECT_OVERRIDE = None   # set from --project / $UE_PROJECT


def uproject():
    """The .uproject to act on: --project, then $UE_PROJECT, then this repo."""
    override = PROJECT_OVERRIDE or os.environ.get("UE_PROJECT")
    if override:
        path = os.path.abspath(override)
        if os.path.isdir(path):
            hits = glob.glob(os.path.join(path, "*.uproject"))
            if not hits:
                sys.exit(f"[uepy] no .uproject in {path}")
            return hits[0]
        if not os.path.isfile(path):
            sys.exit(f"[uepy] no such project: {path}")
        return path
    hits = glob.glob(os.path.join(PROJECT_ROOT, "*.uproject"))
    if not hits:
        sys.exit(f"[uepy] no .uproject in {PROJECT_ROOT}")
    return hits[0]


def remote_module(engine):
    """Import the plugin's own remote_execution client.

    It ships inside the plugin rather than on sys.path, and it moved between
    Plugins/Experimental and Plugins/ across engine versions, so try both rather
    than hard-coding the 5.8 location.
    """
    for mid in ("Plugins/Experimental/PythonScriptPlugin",
                "Plugins/PythonScriptPlugin"):
        path = os.path.join(engine, mid, "Content/Python")
        if os.path.isfile(os.path.join(path, "remote_execution.py")):
            sys.path.insert(0, path)
            import remote_execution
            return remote_execution
    sys.exit(f"[uepy] remote_execution.py not found under {engine}")


# ─── Talking to a live editor ───────────────────────────────────────────────

class Editor(object):
    """An open command connection to a running editor, or nothing."""

    def __init__(self, remote, node):
        self.remote, self.node = remote, node

    @property
    def label(self):
        d = self.node
        return (f"{d.get('project_name', '?')} "
                f"({d.get('engine_version', '?')}) "
                f"user={d.get('user', '?')} node={d.get('node_id', '?')[:8]}")


def discover(engine, project_filter=True, seconds=DISCOVERY_SECONDS):
    """Return (remote_execution_instance, [node dicts]).

    The caller must stop() the instance. Nodes are filtered to this project by
    default: pushing a builder into some *other* project's editor would compile
    blueprints that do not exist there and is never what was meant.
    """
    remote_execution = remote_module(engine)
    remote = remote_execution.RemoteExecution()
    remote.start()
    want = os.path.splitext(os.path.basename(uproject()))[0]
    deadline = time.time() + seconds
    nodes = []
    while time.time() < deadline:
        nodes = list(remote.remote_nodes)
        if nodes:
            # Give stragglers one more ping window so --list is not misleading
            # when two editors are open.
            time.sleep(DISCOVERY_POLL * 4)
            nodes = list(remote.remote_nodes)
            break
        time.sleep(DISCOVERY_POLL)
    if project_filter:
        named = [n for n in nodes if n.get("project_name")]
        if named:
            nodes = [n for n in named if n.get("project_name") == want] or []
    return remote_execution, remote, nodes


# Is the editor mid-PIE? Recompiling a Blueprint under a running game is the one
# way remote execution can be actively worse than a cold boot: the asset changes
# beneath the instances already spawned from it, and what you then observe is
# neither the old build nor cleanly the new one. Written with getattr so an
# engine that renames the accessor reports "unknown" instead of raising -- an
# unknown answer must not block the run, only a confirmed PIE does.
PIE_PROBE = """
import unreal
state = "unknown"
try:
    sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    getter = getattr(sub, "get_game_world", None)
    if getter is not None:
        state = "pie" if getter() is not None else "idle"
except Exception as exc:
    state = "unknown"
print("[uepy-pie] " + state)
"""


def remote_pie_state(remote_execution, remote):
    res = remote.run_command(PIE_PROBE, exec_mode=remote_execution.MODE_EXEC_FILE)
    for entry in res.get("output") or []:
        m = re.search(r"\[uepy-pie\] (\w+)", str(entry.get("output", "")))
        if m:
            return m.group(1)
    return "unknown"


def echo(result, quiet=False):
    """Print a command result the way the editor logged it. Returns success."""
    for entry in result.get("output") or []:
        kind = str(entry.get("type", "Info"))
        text = str(entry.get("output", "")).rstrip("\n")
        if not text:
            continue
        if quiet and kind == "Info":
            continue
        prefix = "" if kind == "Info" else f"{kind}: "
        print(f"{prefix}{text}", flush=True)
    if not result.get("success"):
        # 'result' carries the exception text for a failed command.
        print(f"Error: {result.get('result')}", flush=True)
    return bool(result.get("success"))


def run_remote(engine, targets, quiet=False, allow_pie=False):
    """Execute targets in a live editor. Returns None if none is listening."""
    remote_execution, remote, nodes = discover(engine)
    try:
        if not nodes:
            remote.stop()
            return None
        node = nodes[0]
        editor = Editor(remote, node)
        if len(nodes) > 1:
            log(f"{len(nodes)} editors listening, using {editor.label}")
        else:
            log(f"live editor: {editor.label}")
        remote.open_command_connection(node.get("node_id"))
        try:
            state = remote_pie_state(remote_execution, remote)
            if state == "pie" and not allow_pie:
                log("the editor is in PIE -- asset edits would land under the "
                    "running game. Stop PIE, or pass --allow-pie / --cold.")
                return False
            ok = True
            for kind, value in targets:
                label = value if kind == "file" else "<statement>"
                log(f"=== {os.path.basename(label)}")
                started = time.time()
                result = remote.run_command(
                    value, exec_mode=remote_execution.MODE_EXEC_FILE)
                ok = echo(result, quiet) and ok
                log(f"--- {os.path.basename(label)} "
                    f"({time.time() - started:.1f}s)")
            return ok
        finally:
            remote.close_command_connection()
    finally:
        try:
            remote.stop()
        except Exception:
            pass


# ─── The file-based inbox (Content/Python/uepy_inbox.py) ────────────────────
#
# The engine's own remote execution discovers editors over UDP multicast, which
# does not work on this machine: a plain Python sender/receiver pair on
# 239.0.0.1 delivers nothing on lo0 *or* en0, with no Unreal in the picture
# (macOS Local Network privacy drops it silently). The editor binds its socket
# and ticks happily and never hears a ping. So there is a second transport that
# needs no network at all -- a request/result directory under Saved/uepy that
# the editor polls on its Slate tick.

INBOX_FRESH_SECONDS = 6.0     # a heartbeat older than this means "not running"
INBOX_POLL = 0.05
INBOX_TIMEOUT = 1800.0


def inbox_dir():
    return os.path.join(os.path.dirname(uproject()), "Saved", "uepy")


def inbox_heartbeat():
    """The editor's liveness record, or None."""
    path = os.path.join(inbox_dir(), "heartbeat")
    try:
        with open(path, encoding="utf-8") as fh:
            beat = json.load(fh)
    except (OSError, ValueError):
        return None
    if time.time() - float(beat.get("time", 0)) > INBOX_FRESH_SECONDS:
        return None
    return beat


def run_inbox(targets, quiet=False, allow_pie=False, timeout=INBOX_TIMEOUT):
    """Execute targets in the editor listening on the inbox, or return None."""
    beat = inbox_heartbeat()
    if not beat:
        return None
    log(f"live editor via inbox: pid={beat.get('pid')} "
        f"{os.path.basename(str(beat.get('project')))}"
        + (" [PIE]" if beat.get("pie") else ""))
    path = inbox_dir()
    ok = True
    for kind, value in targets:
        label = os.path.basename(value) if kind == "file" else "<statement>"
        job_id = uuid.uuid4().hex[:12]
        payload = {"kind": kind, "value": value, "allow_pie": allow_pie}
        tmp = os.path.join(path, job_id + ".request.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        # Atomic rename so the editor never reads a half-written request.
        os.replace(tmp, os.path.join(path, job_id + ".request"))
        log(f"=== {label}")
        result_path = os.path.join(path, job_id + ".result")
        deadline = time.time() + timeout
        result = None
        while time.time() < deadline:
            if os.path.exists(result_path):
                try:
                    with open(result_path, encoding="utf-8") as fh:
                        result = json.load(fh)
                    os.remove(result_path)
                except (OSError, ValueError):
                    result = None
                if result is not None:
                    break
            if inbox_heartbeat() is None and not os.path.exists(result_path):
                log("the editor stopped responding -- is it still running?")
                return False
            time.sleep(INBOX_POLL)
        if result is None:
            log(f"timed out after {timeout:.0f}s waiting for {label}")
            return False
        text = str(result.get("output", "")).rstrip()
        if text:
            for line in text.splitlines():
                if quiet and not re.search(
                        r"LogPython|Error|Warning|❌|✅|Traceback", line):
                    continue
                print(line, flush=True)
        ok = bool(result.get("success")) and ok
        log(f"--- {label} ({float(result.get('seconds', 0.0)):.1f}s)")
    return ok


# ─── Falling back to a cold editor ──────────────────────────────────────────

# One boot, N scripts. runpy with run_name="__main__" so a script whose work
# sits behind `if __name__ == "__main__":` still does it -- which most builders
# here do.
COLD_DRIVER = '''
import runpy, traceback
TARGETS = {targets!r}
failed = []
for kind, value in TARGETS:
    label = value if kind == "file" else "<statement>"
    print("[uepy] === " + label, flush=True)
    try:
        if kind == "file":
            runpy.run_path(value, run_name="__main__")
        else:
            exec(compile(value, "<uepy>", "exec"), {{"__name__": "__main__"}})
    except SystemExit as exc:
        if exc.code:
            failed.append(label)
    except Exception:
        traceback.print_exc()
        failed.append(label)
    print("[uepy] --- " + label, flush=True)
if failed:
    print("[uepy] FAILED: " + ", ".join(failed), flush=True)
'''


def run_cold(engine, targets, quiet=False, boot_timeout=900):
    cmd_bin = os.path.join(engine, "Binaries/Mac/UnrealEditor-Cmd")
    if not os.path.isfile(cmd_bin):
        sys.exit(f"[uepy] no UnrealEditor-Cmd at {cmd_bin}")
    tmp = tempfile.mkdtemp(prefix="uepy-")
    driver = os.path.join(tmp, "uepy_driver.py")
    with open(driver, "w", encoding="utf-8") as fh:
        fh.write(COLD_DRIVER.format(targets=targets))
    log(f"no live editor -- cold boot ({len(targets)} script(s), one launch)")
    started = time.time()
    # Log to a FILE, never to a pipe. subprocess pipes deadlock here: the editor
    # hands its inherited stdout to long-lived helpers (UnrealEditorServices and
    # friends) that outlive the run, so capture_output=True waits for an EOF
    # that never comes -- the editor process is long gone and the wait is
    # forever. Observed exactly that; a file has no such failure mode.
    outfile = os.path.join(tmp, "cold.log")
    with open(outfile, "w") as sink:
        proc = subprocess.Popen(
            [cmd_bin, uproject(), f"-ExecutePythonScript={driver}", "-NoUI",
             "-stdout"], stdout=sink, stderr=subprocess.STDOUT)
        try:
            proc.wait(timeout=boot_timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            log(f"cold run exceeded {boot_timeout}s and was killed")
    with open(outfile, errors="replace") as fh:
        out = fh.read()
    for line in out.splitlines():
        if quiet and not re.search(
                r"\[uepy\]|LogPython|Error|Warning|❌|✅|Traceback", line):
            continue
        print(line, flush=True)
    log(f"cold run finished in {time.time() - started:.0f}s")
    return "[uepy] FAILED:" not in out and "Traceback (most recent call last)" not in out


# ─── Headless -game runs ────────────────────────────────────────────────────

def run_game(engine, level, seconds, extra_patterns=()):
    """Boot the level in -game and summarise what the log says.

    The process is killed on the timer, which the engine records as a crash via
    GracefulTerminationHandler -- expected, and not a failure of the run.
    """
    cmd_bin = os.path.join(engine, "Binaries/Mac/UnrealEditor-Cmd")
    tmp = tempfile.mkdtemp(prefix="uepy-game-")
    logfile = os.path.join(tmp, "game.log")
    log(f"-game {level} for {seconds}s -> {logfile}")
    # Kill on a timer in-process rather than shelling out to `timeout`, which
    # is not in the macOS base system (it arrives with coreutils, sometimes as
    # gtimeout) -- one less thing that has to be installed for this to work.
    proc = subprocess.Popen(
        [cmd_bin, uproject(), level, "-game", "-nullrhi", "-unattended",
         "-forcelogflush", f"-abslog={logfile}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        proc.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    if not os.path.isfile(logfile):
        sys.exit("[uepy] the run produced no log")
    with open(logfile, errors="replace") as fh:
        text = fh.read()
    clean = True
    for label, pattern in tuple(GAME_PATTERNS) + tuple(extra_patterns):
        hits = re.findall(pattern, text)
        print(f"  {label:<28} {len(hits)}", flush=True)
        if len(hits) and label in ("blueprint runtime errors", "accessed None"):
            clean = False
    for line in text.splitlines():
        if re.search(r"Blueprint Runtime Error|Accessed None|NPC-FELL", line):
            print(f"  | {line.strip()[:200]}", flush=True)
    log(f"log kept at {logfile}")
    return clean


# ─── CLI ────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Run Unreal Python in a live editor when there is one.")
    ap.add_argument("scripts", nargs="*", help="script paths to execute in order")
    ap.add_argument("-c", "--code", action="append", default=[],
                    help="inline statement(s) to execute")
    ap.add_argument("--cold", action="store_true",
                    help="force a fresh UnrealEditor-Cmd boot")
    ap.add_argument("--remote-only", action="store_true",
                    help="fail rather than cold boot when no editor is live")
    ap.add_argument("--allow-pie", action="store_true",
                    help="run even though the editor is mid-PIE")
    ap.add_argument("--list", action="store_true",
                    help="list editors that are listening, then exit")
    ap.add_argument("--game", action="store_true",
                    help="headless -game run instead of a script")
    ap.add_argument("--map", default=DEFAULT_MAP, help="level for --game")
    ap.add_argument("--seconds", type=int, default=GAME_SECONDS,
                    help=f"--game duration (default {GAME_SECONDS})")
    ap.add_argument("--grep", action="append", default=[],
                    help="extra regex to count in a --game log")
    ap.add_argument("-q", "--quiet", action="store_true",
                    help="drop routine Info lines")
    ap.add_argument("--project",
                    help="run against another .uproject (file or directory)")
    ap.add_argument("--boot-timeout", type=int, default=900,
                    help="kill a cold run that overruns (seconds, default 900)")
    ap.add_argument("--engine", help="engine directory override")
    args = ap.parse_args()

    global PROJECT_OVERRIDE
    PROJECT_OVERRIDE = args.project
    engine = engine_dir(args.engine)

    if args.list:
        _, remote, nodes = discover(engine, project_filter=False)
        if not nodes:
            log("no editor answered multicast discovery (needs a UI editor "
                "with bRemoteExecution=True, and a host where multicast is "
                "actually delivered -- see Content/Python/uepy_inbox.py)")
        beat = inbox_heartbeat()
        if beat:
            log(f"inbox: pid={beat.get('pid')} "
                f"{os.path.basename(str(beat.get('project')))}"
                + (" [PIE]" if beat.get("pie") else "")
                + f" -- {inbox_dir()}")
        else:
            log(f"inbox: nothing listening in {inbox_dir()}")
        for n in nodes:
            log(f"{n.get('project_name', '?'):<20} "
                f"{n.get('engine_version', '?'):<12} "
                f"node={n.get('node_id', '?')}")
        remote.stop()
        return 0

    if args.game:
        extra = [(f"/{p}/", p) for p in args.grep]
        return 0 if run_game(engine, args.map, args.seconds, extra) else 1

    targets = [("file", os.path.abspath(s)) for s in args.scripts]
    targets += [("code", c) for c in args.code]
    if not targets:
        ap.error("nothing to run -- pass a script, -c, --game or --list")
    for kind, value in targets:
        if kind == "file" and not os.path.isfile(value):
            sys.exit(f"[uepy] no such script: {value}")

    if not args.cold:
        # Inbox first: detecting it is a single file stat, while multicast
        # discovery costs a fixed 2.5 s wait and, on a host where multicast is
        # not delivered, always costs it for nothing. Both transports execute in
        # the same editor, so preferring the cheap probe loses nothing.
        outcome = run_inbox(targets, args.quiet, args.allow_pie)
        if outcome is None:
            outcome = run_remote(engine, targets, args.quiet, args.allow_pie)
        if outcome is not None:
            return 0 if outcome else 1
        if args.remote_only:
            sys.exit("[uepy] no live editor and --remote-only was given")

    return 0 if run_cold(engine, targets, args.quiet,
                         args.boot_timeout) else 1


if __name__ == "__main__":
    sys.exit(main())
