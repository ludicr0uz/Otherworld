# Otherworld - Unreal Engine 5 Project Rules

This file guides Antigravity (AGY) when interacting with the **Otherworld** Unreal Engine 5 project.

---

## 1. Engine & Project Specifications
- **Engine Version:** Unreal Engine 5.8
- **Project Name:** Otherworld
- **Key Plugins Active:**
  - `GameplayStateTree` (AI & state machines)
  - `ModelingToolsEditorMode` (In-editor 3D modeling)
  - `PythonScriptPlugin` & `EditorScriptingUtilities` (Editor automation)

---

## 2. Unreal Engine Asset Guidelines & Constraints
- **Binary Assets (`.uasset`, `.umap`):** NEVER attempt to edit `.uasset` or `.umap` files directly as text.
- **Automation & Modifications:** Use Unreal Python Editor scripting (`unreal` module) or C++ source files to generate, modify, or inspect assets.
- **Scripts Location:** Place automation and utility scripts in `Scripts/` or `Content/Python/`.

---

## 3. Asset Naming Conventions
Follow standard Unreal Engine prefix conventions:
- **Blueprints:** `BP_` (e.g., `BP_PlayerCharacter`)
- **Widget Blueprints:** `WBP_` (e.g., `WBP_HUD`)
- **State Trees:** `ST_` (e.g., `ST_EnemyBehavior`)
- **Static Meshes:** `SM_`
- **Skeletal Meshes:** `SK_`
- **Materials:** `M_`
- **Material Instances:** `MI_`
- **Textures:** `T_`
- **Audio Cues / Waves:** `A_` / `Cue_`

---

## 4. Directory Structure
```
Otherworld/
├── Config/               # Project configuration (.ini)
├── Content/              # Game assets
│   ├── Blueprints/       # Core gameplay blueprints
│   ├── Environment/      # Static meshes, foliage, levels
│   ├── Characters/       # Meshes, animations, character BPs
│   ├── UI/               # Widget blueprints, fonts, textures
│   └── Python/           # Python scripts automatically discovered by UE
├── Scripts/              # External automation & AGY helper scripts
└── Otherworld.uproject   # Project descriptor
```

---

## 5. Python Automation Patterns
For automated asset and level tasks, use Unreal's Python API:
```python
import unreal

# Example: Get Editor Asset Subsystem
asset_subsystem = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)

# Example: Get Editor Actor Subsystem
actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
```
