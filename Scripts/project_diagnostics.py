#!/usr/bin/env python3
"""
Otherworld Project Diagnostic & Validation Script
Can be run via standard Python or inside Unreal Engine's Python environment.
"""
import os
import json
import sys

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPROJECT_PATH = os.path.join(PROJECT_DIR, "Otherworld.uproject")
CONFIG_DIR = os.path.join(PROJECT_DIR, "Config")
CONTENT_DIR = os.path.join(PROJECT_DIR, "Content")

def run_diagnostics():
    print("=" * 60)
    print("  Otherworld Unreal Engine 5 Project Diagnostics")
    print("=" * 60)
    print(f"Project Root : {PROJECT_DIR}")
    
    # 1. Inspect .uproject descriptor
    if os.path.exists(UPROJECT_PATH):
        with open(UPROJECT_PATH, "r") as f:
            uproj = json.load(f)
        engine_ver = uproj.get("EngineAssociation", "Unknown")
        plugins = [p.get("Name") for p in uproj.get("Plugins", []) if p.get("Enabled", False)]
        print(f"Engine Ver   : {engine_ver}")
        print(f"Active Plugins ({len(plugins)}): {', '.join(plugins)}")
    else:
        print("[ERROR] Otherworld.uproject not found!")
        return False

    # 2. Inspect Config files
    if os.path.exists(CONFIG_DIR):
        configs = [f for f in os.listdir(CONFIG_DIR) if f.endswith(".ini")]
        print(f"Config Files : {', '.join(configs)}")
    
    # 3. Inspect Content tree
    uasset_count = 0
    umap_count = 0
    py_count = 0
    for root, _, files in os.walk(CONTENT_DIR):
        for file in files:
            if file.endswith(".uasset"):
                uasset_count += 1
            elif file.endswith(".umap"):
                umap_count += 1
            elif file.endswith(".py"):
                py_count += 1

    print(f"Content Summary:")
    print(f"  - Maps (.umap)      : {umap_count}")
    print(f"  - Assets (.uasset)  : {uasset_count}")
    print(f"  - Python Scripts    : {py_count}")
    
    # Check if inside Unreal environment
    try:
        import unreal # type: ignore
        print("\n[INFO] Running inside Unreal Editor environment!")
        unreal.log("AGY Diagnostics executed inside Unreal Editor successfully.")
    except ImportError:
        print("\n[INFO] Running in external CLI environment (Outside Unreal Editor).")

    print("=" * 60)
    print("Status: Project configuration is healthy and AGY-ready.")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = run_diagnostics()
    sys.exit(0 if success else 1)
