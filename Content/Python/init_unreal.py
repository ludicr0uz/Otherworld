"""
Otherworld - Unreal Engine Startup Script
Executed automatically by Unreal Engine Editor on project startup.
"""
import unreal

def on_editor_ready():
    unreal.log("--------------------------------------------------")
    unreal.log("[AGY] Antigravity Unreal Integration Initialized!")
    unreal.log("[AGY] Project: Otherworld (UE 5.8)")
    unreal.log("--------------------------------------------------")

if __name__ == "__main__":
    on_editor_ready()
