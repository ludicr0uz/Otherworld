"""Where things are: the engine, the .uproject and uepy's Saved/ directories."""

import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))  # Scripts/dev/uepylib

_project_override = None   # set from --project / $UE_PROJECT


def log(msg):
    print(f"[uepy] {msg}", flush=True)


def set_project(path):
    global _project_override
    _project_override = path


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


def editor_cmd(engine):
    path = os.path.join(engine, "Binaries/Mac/UnrealEditor-Cmd")
    if not os.path.isfile(path):
        sys.exit(f"[uepy] no UnrealEditor-Cmd at {path}")
    return path


def uproject():
    """The .uproject to act on: --project, then $UE_PROJECT, then this repo."""
    override = _project_override or os.environ.get("UE_PROJECT")
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


def saved_uepy(*parts):
    """A path under <project>/Saved/uepy."""
    return os.path.join(os.path.dirname(uproject()), "Saved", "uepy", *parts)


def serve_inbox():
    """$UEPY_SERVE: the inbox of this caller's own warm editor (uepylib/server.py),
    or None. dev-team sets it so its sessions never reach the user's editor."""
    path = os.environ.get("UEPY_SERVE")
    return os.path.abspath(path) if path else None


def editor_inbox():
    """The inbox a UI editor polls (Content/Python/uepy_inbox.py), or the
    warm editor's under $UEPY_SERVE."""
    return serve_inbox() or saved_uepy()


def game_inbox():
    """The inbox a uepy-launched -game run polls: its own, never the editor's."""
    return saved_uepy("game")
