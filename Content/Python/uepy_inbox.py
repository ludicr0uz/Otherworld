"""A command inbox for the running editor, polled on the Slate tick.

Why this exists instead of the Python plugin's own remote execution: that
protocol discovers editors over UDP **multicast** (239.0.0.1:6766), and on this
machine multicast is not delivered even to a listener on the same host -- proven
with a plain Python sender/receiver pair, no Unreal involved, on both lo0 and
en0. macOS Local Network privacy drops it silently, so the editor's socket is
bound and ticking and simply never hears a ping. Nothing in the logs says so.

So the transport here is the filesystem, which needs no permission and no
network at all:

    Saved/uepy/heartbeat        <- this module touches it every second
    Saved/uepy/<id>.request     <- the client writes a job
    Saved/uepy/<id>.result      <- this module writes the outcome

``Scripts/dev/uepy.py`` prefers multicast when discovery works (it is the
engine's own supported path), falls back to this inbox when the editor is
listening on it, and cold-boots only when neither is available.

Everything runs on the game thread inside the tick callback, which is exactly
where editor scripting has to run -- the same place -ExecutePythonScript would
put it.
"""

import json
import os
import runpy
import sys
import time
import traceback

import unreal

POLL_SECONDS = 0.25          # how often the inbox is checked
HEARTBEAT_SECONDS = 1.0      # how often liveness is published
RESULT_TTL_SECONDS = 300.0   # results nobody collected are swept after this

_state = {"handle": None, "last_poll": 0.0, "last_beat": 0.0}


def inbox_dir():
    # A -game run launched by uepy.py gets its own directory (UEPY_INBOX_DIR),
    # so a job meant for the open editor can never be picked up by the game --
    # both would otherwise poll the same Saved/uepy.
    path = (os.environ.get("UEPY_INBOX_DIR")
            or os.path.join(unreal.Paths.project_saved_dir(), "uepy"))
    os.makedirs(path, exist_ok=True)
    return os.path.abspath(path)


# Capturing sys.stdout only catches print(); this project's scripts report
# through unreal.log_warning (every [NPC] / [VERIFY] line), which goes to the UE
# log and nowhere near stdout. Wrapping those three functions for the duration
# of a job is exact and needs no guess about where the log file lives -- the
# editor may have been started with -abslog, and the Python API exposes the log
# *directory* but not the filename, so the tail-the-logfile approach silently
# captures nothing in exactly the case you cannot see.
_LOG_FUNCS = ("log", "log_warning", "log_error")


def _patch_logs(sink):
    """Tee unreal.log* into sink. Returns a restore callable (or None)."""
    originals = {}
    try:
        for name in _LOG_FUNCS:
            original = getattr(unreal, name)
            originals[name] = original

            def make(orig, label):
                def wrapper(arg):
                    sink.append(f"{label}{arg}\n")
                    return orig(arg)
                return wrapper

            label = {"log": "", "log_warning": "Warning: ",
                     "log_error": "Error: "}[name]
            setattr(unreal, name, make(original, label))
    except (AttributeError, TypeError):
        for name, original in originals.items():
            try:
                setattr(unreal, name, original)
            except Exception:
                pass
        return None

    def restore():
        for name, original in originals.items():
            try:
                setattr(unreal, name, original)
            except Exception:
                pass
    return restore


def _log_path():
    """Best guess at the log file, used only when unreal.log* cannot be wrapped."""
    name = unreal.Paths.get_base_filename(unreal.Paths.get_project_file_path())
    return os.path.join(unreal.Paths.project_log_dir(), f"{name}.log")


def _in_pie():
    try:
        sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        getter = getattr(sub, "get_game_world", None)
        if getter is not None:
            return getter() is not None
    except Exception:
        pass
    return False


def _write_atomic(path, payload):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    os.replace(tmp, path)


def _forget_project_modules():
    """Drop every module imported from the project's Scripts/ directory.

    The editor's interpreter outlives every job, so a module a job imported is
    still in sys.modules for the next one: edit Scripts/combat/tuning.py, rerun
    the builder, and the builder silently uses the old numbers. A cold boot
    never has this problem, so the inbox would be the one transport whose
    results depend on what ran before. Forgetting them makes each job import
    what is on disk, exactly as a cold boot would.
    """
    project = os.path.abspath(unreal.Paths.convert_relative_path_to_full(
        unreal.Paths.project_dir()))
    scripts = os.path.join(project, "Scripts") + os.sep
    for name, module in list(sys.modules.items()):
        path = getattr(module, "__file__", None) or ""
        if os.path.abspath(path).startswith(scripts):
            del sys.modules[name]


def _execute(job):
    """Run one job on the game thread, returning (success, output)."""
    try:
        _forget_project_modules()
    except Exception:
        traceback.print_exc()
    captured = []
    restore_logs = _patch_logs(captured)

    log_file = None if restore_logs else _log_path()
    start_at = 0
    if log_file:
        try:
            start_at = os.path.getsize(log_file)
        except OSError:
            log_file = None

    class _Tee(object):
        """Keep the editor's Output Log working while also capturing."""

        def __init__(self, inner):
            self._inner = inner

        def write(self, text):
            captured.append(text)
            try:
                self._inner.write(text)
            except Exception:
                pass

        def flush(self):
            try:
                self._inner.flush()
            except Exception:
                pass

    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = _Tee(old_out), _Tee(old_err)
    ok = True
    try:
        if job.get("kind") == "file":
            runpy.run_path(job["value"], run_name="__main__")
        else:
            exec(compile(job["value"], "<uepy-inbox>", "exec"),
                 {"__name__": "__main__"})
    except SystemExit as exc:
        ok = not exc.code
    except BaseException:
        ok = False
        captured.append(traceback.format_exc())
    finally:
        sys.stdout, sys.stderr = old_out, old_err
        if restore_logs:
            restore_logs()

    # Anything the run sent to the UE log rather than to stdout.
    tail = ""
    if log_file:
        try:
            unreal.log_flush()
            with open(log_file, errors="replace") as fh:
                fh.seek(start_at)
                tail = fh.read()
        except OSError:
            tail = ""
    return ok, "".join(captured) + tail


def _sweep(path, now):
    for name in os.listdir(path):
        if not name.endswith(".result"):
            continue
        full = os.path.join(path, name)
        try:
            if now - os.path.getmtime(full) > RESULT_TTL_SECONDS:
                os.remove(full)
        except OSError:
            pass


def _tick(_delta):
    """Slate post-tick. Must never raise: an exception here kills the ticker."""
    now = time.time()
    try:
        path = inbox_dir()
        if now - _state["last_beat"] >= HEARTBEAT_SECONDS:
            _state["last_beat"] = now
            _write_atomic(os.path.join(path, "heartbeat"), {
                "pid": os.getpid(),
                "time": now,
                "pie": _in_pie(),
                "project": unreal.Paths.get_project_file_path(),
            })
        if now - _state["last_poll"] < POLL_SECONDS:
            return
        _state["last_poll"] = now
        _sweep(path, now)

        for name in sorted(n for n in os.listdir(path)
                           if n.endswith(".request")):
            full = os.path.join(path, name)
            job_id = name[: -len(".request")]
            try:
                with open(full, encoding="utf-8") as fh:
                    job = json.load(fh)
            except (OSError, ValueError):
                try:
                    os.remove(full)
                except OSError:
                    pass
                continue
            # Delete first: a request that hard-crashes the interpreter must not
            # be retried on the next tick, forever.
            try:
                os.remove(full)
            except OSError:
                pass

            if _in_pie() and not job.get("allow_pie"):
                _write_atomic(os.path.join(path, job_id + ".result"), {
                    "success": False,
                    "output": "[uepy-inbox] refused: the editor is in PIE. "
                              "Stop PIE, or send allow_pie.",
                    "seconds": 0.0,
                })
                continue

            started = time.time()
            ok, output = _execute(job)
            _write_atomic(os.path.join(path, job_id + ".result"), {
                "success": ok,
                "output": output,
                "seconds": time.time() - started,
            })
    except Exception:
        # Report, but keep the ticker alive.
        try:
            unreal.log_error("[uepy-inbox] " + traceback.format_exc())
        except Exception:
            pass
    return True


def start():
    """Register the tick callback (idempotent)."""
    if _state["handle"] is not None:
        return _state["handle"]
    _state["handle"] = unreal.register_slate_post_tick_callback(_tick)
    unreal.log_warning(f"[uepy-inbox] listening in {inbox_dir()}")
    return _state["handle"]


def stop():
    if _state["handle"] is not None:
        unreal.unregister_slate_post_tick_callback(_state["handle"])
        _state["handle"] = None
