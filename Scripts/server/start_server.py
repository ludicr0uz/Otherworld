#!/usr/bin/env python3
"""Start the Otherworld dedicated server on this machine, on macOS or Windows.

    python3 Scripts/server/start_server.py                 # the default map, port 7777
    python3 Scripts/server/start_server.py --port 17777 --map /Game/Maps/Lvl_Forest_200m
    python3 Scripts/server/start_server.py --dry-run       # print the command, run nothing
    python3 Scripts/server/start_server.py -- -NoVerifyGC  # anything after -- goes to Unreal

A client joins with ``open <this machine's address>:<port>`` in the console, or
through the title's menu. UDP on the port must reach this machine.

The server is the editor binary run with ``-server``, as serversupportsysdesign.md
4.4 prescribes for local work (``UnrealEditor-Cmd <uproject> <map> -server``): no
packaged build is needed. ``--binary`` runs a packaged server instead
(OtherworldServer, OtherworldServer.exe) when one has been made.

The engine is found from ``--engine``, then ``$UE_ENGINE_DIR``, then the standard
Epic install root of the platform (``/Users/Shared/Epic Games`` on a Mac,
``C:\\Program Files\\Epic Games`` on Windows), preferring the version named by the
.uproject's EngineAssociation.

Logs go to the project's Saved/Logs/Server.log (``--log-file`` to change it) and
to this terminal. Ctrl-C stops the server. The process gets its own uepy inbox
(UEPY_INBOX_DIR), so it never takes a job meant for an open editor.
"""

import argparse
import glob
import json
import os
import platform
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(HERE))          # Scripts/server
DEFAULT_PORT = 7777
WINDOWS = platform.system() == "Windows"

if WINDOWS:
    EPIC_ROOTS = [os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                               "Epic Games")]
    EDITOR_CMD = os.path.join("Binaries", "Win64", "UnrealEditor-Cmd.exe")
else:
    EPIC_ROOTS = ["/Users/Shared/Epic Games"]
    EDITOR_CMD = os.path.join("Binaries", "Mac", "UnrealEditor-Cmd")


def fail(message):
    sys.exit(f"[start_server] {message}")


def uproject(root=PROJECT_ROOT):
    hits = glob.glob(os.path.join(root, "*.uproject"))
    if not hits:
        fail(f"no .uproject in {root}")
    return hits[0]


def engine_association(project):
    """The engine version the .uproject names ("5.8"), or ""."""
    try:
        with open(project, encoding="utf-8") as fh:
            return str(json.load(fh).get("EngineAssociation", ""))
    except (OSError, ValueError):
        return ""


def version_key(path):
    """Sort key for an install folder: UE_5.8 after UE_5.6, UE_5.10 after both."""
    numbers = re.findall(r"\d+", os.path.basename(os.path.dirname(path)))
    return tuple(int(n) for n in numbers)


def engine_dir(override=None, wanted="", roots=EPIC_ROOTS, environ=os.environ):
    """The Engine/ folder of the install to run: --engine, $UE_ENGINE_DIR, else
    the install under the Epic root that matches ``wanted``, else the newest."""
    for candidate in (override, environ.get("UE_ENGINE_DIR")):
        if candidate:
            if not os.path.isdir(candidate):
                fail(f"no engine at {candidate}")
            return candidate
    installs = []
    for root in roots:
        installs += glob.glob(os.path.join(root, "UE_*", "Engine"))
    if not installs:
        fail("no engine found under " + ", ".join(roots)
             + " -- pass --engine or set UE_ENGINE_DIR")
    for install in installs:
        if wanted and os.path.basename(os.path.dirname(install)) == f"UE_{wanted}":
            return install
    return sorted(installs, key=version_key)[-1]


def default_map(project):
    """GameDefaultMap from Config/DefaultEngine.ini, as the asset path."""
    ini = os.path.join(os.path.dirname(project), "Config", "DefaultEngine.ini")
    try:
        with open(ini, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("GameDefaultMap="):
                    return line.split("=", 1)[1].strip().split(".")[0]
    except OSError:
        pass
    fail(f"no GameDefaultMap in {ini} -- pass --map")


def command(binary, project, level, port, log_file, extra=()):
    """The command line. A packaged server takes no .uproject argument."""
    packaged = not os.path.basename(binary).startswith("UnrealEditor")
    argv = [binary] + ([] if packaged else [project])
    return argv + [level, "-server", f"-port={port}", "-log", "-unattended",
                   "-forcelogflush", f"-abslog={log_file}", *extra]


def environment(project, base=os.environ):
    env = dict(base)
    for inherited in ("UEPY_SERVE", "UEPY_SERVING"):
        env.pop(inherited, None)
    env["UEPY_INBOX_DIR"] = os.path.join(os.path.dirname(project), "Saved", "uepy", "server")
    return env


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog="Arguments after -- are passed to Unreal as they are.")
    p.add_argument("--map", help="level to serve (default: GameDefaultMap of DefaultEngine.ini)")
    p.add_argument("--port", type=int, default=DEFAULT_PORT,
                   help=f"UDP port to listen on (default {DEFAULT_PORT})")
    p.add_argument("--project", help="the .uproject (default: this repo's)")
    p.add_argument("--engine", help="the engine's Engine/ folder (default: see above)")
    p.add_argument("--binary", help="a packaged server to run instead of the editor binary")
    p.add_argument("--log-file", help="where the server writes its log "
                                      "(default: <project>/Saved/Logs/Server.log)")
    p.add_argument("--dry-run", action="store_true", help="print the command and exit")
    p.add_argument("extra", nargs="*", help=argparse.SUPPRESS)
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not 1024 <= args.port <= 65535:
        fail(f"--port {args.port}: expected 1024-65535")
    project = os.path.abspath(args.project) if args.project else uproject()
    if not os.path.isfile(project):
        fail(f"no such project: {project}")
    if args.binary:
        binary = os.path.abspath(args.binary)
    else:
        binary = os.path.join(engine_dir(args.engine, engine_association(project)), EDITOR_CMD)
    if not os.path.isfile(binary):
        fail(f"no server binary at {binary}")
    level = args.map or default_map(project)
    log_file = os.path.abspath(args.log_file) if args.log_file else os.path.join(
        os.path.dirname(project), "Saved", "Logs", "Server.log")
    argv = command(binary, project, level, args.port, log_file, args.extra)
    print(f"[start_server] {level} on UDP {args.port}, log {log_file}", flush=True)
    if args.dry_run:
        print(subprocess.list2cmdline(argv))
        return 0
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    process = subprocess.Popen(argv, env=environment(project))
    try:
        return process.wait()
    except KeyboardInterrupt:
        print("\n[start_server] stopping the server", flush=True)
        process.terminate()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
        return 130


if __name__ == "__main__":
    sys.exit(main())
