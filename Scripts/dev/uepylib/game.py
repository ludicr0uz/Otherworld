"""Headless -game runs: a smoke test of the level, or a probe run.

A plain run boots the level for a fixed time and counts what the log says. A
probe run (``--probe``) hands Scripts/probes/boot.py the probe files through
the environment, boots into the empty Entry map so boot.py can prepare the
classes before the level loads, and ends the moment the probes write their
results -- a run is as long as its probes, not as long as a guessed timer.

Both kinds get their own inbox directory (UEPY_INBOX_DIR), so the game never
takes a job meant for an open editor; ``uepy.py --in-game`` reaches it.
"""

import json
import os
import re
import subprocess
import tempfile
import time

from uepylib.paths import editor_cmd, game_inbox, log, uproject

# Long enough to see every NPC spawn and the first chase decisions; spawn-path
# bugs show in the first two seconds.
GAME_SECONDS = 25
# The ceiling on a probe run. It normally ends far sooner, when the probes do.
PROBE_SECONDS = 240
DEFAULT_MAP = "/Game/Maps/Lvl_Forest_200m"
# Boot here, prepare, then open the level (Scripts/probes/boot.py says why).
# A plain GameModeBase, so nothing of ours spawns into the throwaway world.
ENTRY_URL = "/Engine/Maps/Entry?game=/Script/Engine.GameModeBase"

# Lines worth counting in any -game log.
GAME_PATTERNS = (
    ("blueprint runtime errors", r"Blueprint Runtime Error"),
    ("accessed None", r"Accessed None"),
    ("script warnings", r"LogScript: Warning"),
    ("NPC spawns", r"NPC-SPAWN"),
    ("NPC falls", r"NPC-FELL"),
    # What a player carries changed and nothing marked its record
    # (Scripts/combat/dirty.py): logged by the record's audit, which
    # Scripts/probes/boot.py switches on for every probe run.
    ("stale records", r"INVENTORY-RECORD-STALE"),
)
FAILING = ("blueprint runtime errors", "accessed None", "stale records")
NOTABLE = re.compile(r"Blueprint Runtime Error|Accessed None|NPC-FELL|INVENTORY-RECORD-STALE")
MAX_NOTABLE = 15


def count_patterns(text, patterns):
    return [(label, len(re.findall(pattern, text))) for label, pattern in patterns]


def notable_lines(text):
    hits = [l.strip() for l in text.splitlines() if NOTABLE.search(l)]
    shown = [h[:200] for h in hits[:MAX_NOTABLE]]
    if len(hits) > MAX_NOTABLE:
        shown.append(f"(+{len(hits) - MAX_NOTABLE} more)")
    return shown


def probe_report(payload):
    """(lines, ok) for a probes results payload (boot.py's JSON)."""
    if payload is None:
        return ["[probe] no results -- the probes never finished (see the log)"], False
    lines, ok = [], True
    for err in payload.get("setup_errors") or []:
        lines.append(f"[probe] SETUP FAILED: {err}")
        ok = False
    for probe in payload.get("probes") or []:
        checks = probe.get("checks") or []
        passed = sum(1 for c in checks if c.get("ok"))
        good = not probe.get("error") and passed == len(checks)
        ok = ok and good
        lines.append(f"[probe] {'ok  ' if good else 'FAIL'}  {probe.get('name')}  "
                     f"{passed}/{len(checks)} checks passed")
        for c in checks:
            mark = "PASS" if c.get("ok") else "FAIL"
            detail = f" -- {c['detail']}" if c.get("detail") else ""
            lines.append(f"         {mark} {c.get('label')}{detail}")
        for n in probe.get("notes") or []:
            lines.append(f"         note: {n}")
        if probe.get("error"):
            lines.extend("         " + l for l in str(probe["error"]).splitlines()[-6:])
    return lines, ok


def game_env(base, level, probes, results_path, probe_timeout, title=False):
    """The environment for the -game process."""
    env = dict(base)
    env["UEPY_INBOX_DIR"] = game_inbox()
    env.pop("UEPY_TITLE", None)
    if title:
        env["UEPY_TITLE"] = "1"     # Scripts/probes/boot.py: the title pauses the level
    if probes:
        env["UEPY_PROBES"] = os.pathsep.join(probes)
        env["UEPY_PROBE_MAP"] = level
        env["UEPY_PROBE_RESULTS"] = results_path
        if probe_timeout:
            env["UEPY_PROBE_TIMEOUT"] = str(probe_timeout)
    return env


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


# A --game run draws nothing unless asked: -nullrhi. A windowed one renders
# into a small window, which is the only way to check what depends on the
# window itself (widget geometry, the mouse cursor).
WINDOW_ARGS = ("-windowed", "-ResX=1280", "-ResY=720")


def render_args(windowed):
    """How the -game process draws: a window, or not at all."""
    return list(WINDOW_ARGS) if windowed else ["-nullrhi"]


def title_args(level, title=False):
    """How the process meets the title menu, and which level its title is.

    -nomenu: the HUD opens on a paused title menu (build_graphics_menu.py,
    SKIP_MENU_SWITCH). A run has nobody to press Enter, so without it the log
    would be a title screen sitting still. ``title`` (``--title``) leaves it
    out, for a probe that works the title itself.

    A join that fails, or a server left, returns the process to the engine's
    GameDefaultMap, which is the 1 km level: the run's own level is named
    instead, so "back to the title" is back to the level under test.
    """
    args = [f"-ini:Engine:[/Script/EngineSettings.GameMapsSettings]:GameDefaultMap={level}"]
    return args if title else ["-nomenu"] + args


def run_game(engine, level, seconds, extra_patterns=(), probes=(), probe_timeout=None,
             windowed=False, title=False):
    """Boot the level in -game and summarise the log. Returns True when clean.

    The process is killed at the end, which the engine records as a crash via
    GracefulTerminationHandler -- expected, and not a failure of the run.
    """
    tmp = tempfile.mkdtemp(prefix="uepy-game-")
    logfile = os.path.join(tmp, "game.log")
    results_path = os.path.join(tmp, "probes.json")
    os.makedirs(game_inbox(), exist_ok=True)
    what = f"{len(probes)} probe(s) in {level}" if probes else level
    log(f"-game {what}, up to {seconds}s -> {logfile}")
    started = time.time()
    proc = subprocess.Popen(
        [editor_cmd(engine), uproject(), ENTRY_URL if probes else level, "-game",
         *render_args(windowed), "-unattended", *title_args(level, title), "-forcelogflush",
         f"-abslog={logfile}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env=game_env(os.environ, level, probes, results_path, probe_timeout, title))
    # Kill on a timer in-process rather than shelling out to `timeout`, which
    # is not in the macOS base system.
    deadline = started + seconds
    while time.time() < deadline and proc.poll() is None:
        if probes and os.path.exists(results_path):
            break
        time.sleep(0.25)
    if proc.poll() is None:
        proc.kill()
        proc.wait()
    if not os.path.isfile(logfile):
        log("the run produced no log")
        return False
    with open(logfile, errors="replace") as fh:
        text = fh.read()
    clean = True
    for label, count in count_patterns(text, tuple(GAME_PATTERNS) + tuple(extra_patterns)):
        print(f"  {label:<28} {count}", flush=True)
        if count and label in FAILING:
            clean = False
    for line in notable_lines(text):
        print(f"  | {line}", flush=True)
    if probes:
        lines, ok = probe_report(_read_json(results_path))
        for line in lines:
            print(line, flush=True)
        clean = clean and ok
    log(f"{time.time() - started:.0f}s; log kept at {logfile}")
    return clean
