#!/usr/bin/env python3
"""Package the Otherworld game for the machine this runs on: a Mac build on a
Mac, a Windows build on Windows.

    python3 package_game.py                    # Development, into Saved/Packages
    python3 package_game.py --config Shipping
    python3 package_game.py --out ~/Desktop/Builds
    python3 package_game.py --dry-run          # print the command, run nothing
    python3 package_game.py -- -clean          # anything after -- goes to BuildCookRun

This is the editor's Platforms > Package Project, run without the editor: the
same AutomationTool command (BuildCookRun: build, cook, stage, pak, package,
archive). The editor's own button does nothing while Slate.bAllowNotifications
is False (Config/DefaultEngine.ini): it drops the job when it gets no toast.

The build lands in ``<out>/Mac/Otherworld.app`` or ``<out>/Windows/``. The
levels in it are the MapsToCook list of Config/DefaultGame.ini: the title and
the play level.

The engine is found as start_server.py finds it: ``--engine``, then
``$UE_ENGINE_DIR``, then the platform's Epic install root, preferring the
version the .uproject names. The output is AutomationTool's, on this terminal;
its full log is where it says at the start. The exit code is AutomationTool's.
"""

import argparse
import os
import platform
import subprocess
import sys

# start_server.py finds the project and the engine; this script stands at the
# project's root, beside the .uproject.
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "Scripts", "server"))

import start_server  # noqa: E402

# platform.system() -> (BuildCookRun's -platform, RunUAT under Engine/Build/BatchFiles)
PLATFORMS = {
    "Darwin": ("Mac", "RunUAT.command"),
    "Windows": ("Win64", "RunUAT.bat"),
}
CONFIGS = ("Development", "Shipping", "Test", "DebugGame")
TARGET = "Otherworld"


def fail(message):
    sys.exit(f"[package_game] {message}")


def host(system=None):
    """(-platform, RunUAT's file name) of this machine."""
    system = system or platform.system()
    if system not in PLATFORMS:
        fail(f"no packaging on {system}: this runs on a Mac or on Windows")
    return PLATFORMS[system]


def installed(engine):
    """An engine from the Epic launcher, not built from source: it cannot
    compile the editor or AutomationTool, and is told not to try."""
    return os.path.isfile(os.path.join(engine, "Build", "InstalledBuild.txt"))


def command(engine, project, target_platform, run_uat, config, out, extra=()):
    """The command line: the one the editor's Package Project runs."""
    argv = [os.path.join(engine, "Build", "BatchFiles", run_uat),
            f"-ScriptsForProject={project}", "BuildCookRun", f"-project={project}",
            f"-target={TARGET}", f"-platform={target_platform}", f"-clientconfig={config}",
            f"-unrealexe={os.path.join(engine, start_server.EDITOR_CMD)}",
            "-nop4", "-utf8output", "-build", "-cook", "-zenstore", "-stage", "-pak",
            "-iostore", "-compressed", "-prereqs", "-package", "-archive",
            f"-archivedirectory={out}"]
    if installed(engine):
        argv += ["-installed", "-nocompileeditor", "-skipbuildeditor", "-nocompile",
                 "-nocompileuat"]
    return argv + list(extra)


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog="Arguments after -- are passed to BuildCookRun as they are.")
    p.add_argument("--config", choices=CONFIGS, default="Development",
                   help="build configuration (default Development)")
    p.add_argument("--out", help="where the build is archived "
                                 "(default: <project>/Saved/Packages)")
    p.add_argument("--project", help="the .uproject (default: this repo's)")
    p.add_argument("--engine", help="the engine's Engine/ folder (default: see above)")
    p.add_argument("--dry-run", action="store_true", help="print the command and exit")
    p.add_argument("extra", nargs="*", help=argparse.SUPPRESS)
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    target_platform, run_uat = host()
    project = os.path.abspath(args.project) if args.project else start_server.uproject(ROOT)
    if not os.path.isfile(project):
        fail(f"no such project: {project}")
    engine = start_server.engine_dir(args.engine, start_server.engine_association(project))
    out = os.path.abspath(os.path.expanduser(args.out)) if args.out else os.path.join(
        os.path.dirname(project), "Saved", "Packages")
    argv = command(engine, project, target_platform, run_uat, args.config, out, args.extra)
    if not os.path.isfile(argv[0]):
        fail(f"no AutomationTool at {argv[0]}")
    print(f"[package_game] {target_platform} {args.config} into {out}", flush=True)
    if args.dry_run:
        print(subprocess.list2cmdline(argv))
        return 0
    os.makedirs(out, exist_ok=True)
    process = subprocess.Popen(argv)
    try:
        code = process.wait()
    except KeyboardInterrupt:
        print("\n[package_game] stopping", flush=True)
        process.terminate()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
        return 130
    print(f"[package_game] {'done: ' + out if code == 0 else f'failed, exit code {code}'}",
          flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
