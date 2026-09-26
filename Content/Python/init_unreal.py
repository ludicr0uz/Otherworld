"""
Otherworld - Unreal Engine Startup Script
Executed automatically by Unreal Engine Editor on project startup.
"""
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
