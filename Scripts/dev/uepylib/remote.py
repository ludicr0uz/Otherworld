"""The Python plugin's own remote execution (UDP multicast discovery + TCP).

Kept as the second transport because it is the engine's supported path, but on
this machine multicast is never delivered (see inbox.py), so in practice every
call here is a 2.5 s discovery that finds nothing.
"""

import os
import re
import sys
import time

from uepylib.paths import log, uproject
from uepylib.targets import TargetResult, label_for

# The plugin pings once a second, so a node that exists is normally seen well
# inside two seconds; a miss costs a full cold boot, so do not trim it too far.
DISCOVERY_SECONDS = 2.5
DISCOVERY_POLL = 0.1


def remote_module(engine):
    """Import the plugin's own remote_execution client.

    It ships inside the plugin rather than on sys.path, and it moved between
    Plugins/Experimental and Plugins/ across engine versions, so try both.
    """
    for mid in ("Plugins/Experimental/PythonScriptPlugin",
                "Plugins/PythonScriptPlugin"):
        path = os.path.join(engine, mid, "Content/Python")
        if os.path.isfile(os.path.join(path, "remote_execution.py")):
            sys.path.insert(0, path)
            import remote_execution
            return remote_execution
    sys.exit(f"[uepy] remote_execution.py not found under {engine}")


def node_label(node):
    return (f"{node.get('project_name', '?')} ({node.get('engine_version', '?')}) "
            f"user={node.get('user', '?')} node={node.get('node_id', '?')[:8]}")


def discover(engine, project_filter=True, seconds=DISCOVERY_SECONDS):
    """Return (remote_execution module, started instance, [node dicts]).

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
            # One more ping window so --list is not misleading with two editors.
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
# way remote execution can be actively worse than a cold boot. Written with
# getattr so an engine that renames the accessor reports "unknown" instead of
# raising -- an unknown answer must not block the run, only a confirmed PIE does.
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


def _pie_state(remote_execution, remote):
    res = remote.run_command(PIE_PROBE, exec_mode=remote_execution.MODE_EXEC_FILE)
    for entry in res.get("output") or []:
        m = re.search(r"\[uepy-pie\] (\w+)", str(entry.get("output", "")))
        if m:
            return m.group(1)
    return "unknown"


def _text(result):
    lines = []
    for entry in result.get("output") or []:
        kind = str(entry.get("type", "Info"))
        text = str(entry.get("output", "")).rstrip("\n")
        if text:
            lines.append(text if kind == "Info" else f"{kind}: {text}")
    if not result.get("success"):
        lines.append(f"Error: {result.get('result')}")
    return "\n".join(lines)


def run_remote(engine, targets, report, allow_pie=False):
    """Run targets in a multicast-discovered editor. None if none is listening."""
    remote_execution, remote, nodes = discover(engine)
    try:
        if not nodes:
            return None
        node = nodes[0]
        log(f"live editor: {node_label(node)}"
            + (f" (1 of {len(nodes)})" if len(nodes) > 1 else ""))
        remote.open_command_connection(node.get("node_id"))
        try:
            if _pie_state(remote_execution, remote) == "pie" and not allow_pie:
                log("the editor is in PIE -- asset edits would land under the "
                    "running game. Stop PIE, or pass --allow-pie / --cold.")
                return False
            for kind, value in targets:
                started = time.time()
                result = remote.run_command(
                    value, exec_mode=remote_execution.MODE_EXEC_FILE)
                report(TargetResult(label_for(kind, value), result.get("success"),
                                    time.time() - started, _text(result)))
            return True
        finally:
            remote.close_command_connection()
    finally:
        try:
            remote.stop()
        except Exception:
            pass
