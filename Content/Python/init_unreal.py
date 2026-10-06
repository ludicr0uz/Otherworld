"""
Otherworld - Unreal Engine Startup Script
Executed automatically by Unreal Engine Editor on project startup.
"""
import os
import sys
import traceback

import unreal

# The command inbox lets Scripts/dev/uepy.py push work into this already-running
# editor instead of paying 35-45 s for a cold UnrealEditor-Cmd boot -- and, more
# importantly, keeps script edits and the editor's in-memory packages from
# diverging. Guarded: a failure here must not stop the editor starting.
try:
    import uepy_inbox
except ImportError:
    uepy_inbox = None


def on_editor_ready():
    unreal.log("--------------------------------------------------")
    unreal.log("[AGY] Antigravity Unreal Integration Initialized!")
    unreal.log("[AGY] Project: Otherworld (UE 5.8)")
    unreal.log("--------------------------------------------------")

if __name__ == "__main__":
    on_editor_ready()
    if uepy_inbox is not None:
        try:
            uepy_inbox.start()
        except Exception as exc:
            unreal.log_error(f"[uepy-inbox] could not start: {exc}")
    # A probe run (Scripts/dev/uepy.py --game --probe) names its probes in the
    # environment; Scripts/probes/boot.py prepares the classes, opens the level
    # and drives them. Absent in every other editor or game, so a no-op there.
    # A network run (uepy.py --net) names each process, probes or none.
    if os.environ.get("UEPY_PROBES") or os.environ.get("UEPY_NET_WHERE"):
        try:
            sys.path.insert(0, os.path.join(unreal.Paths.convert_relative_path_to_full(
                unreal.Paths.project_dir()), "Scripts"))
            from probes import boot
            boot.start()
        except Exception:
            unreal.log_error("[PROBE] could not start: " + traceback.format_exc())
