#!/usr/bin/env python3
"""import_ui_art.py -- bring the generated HUD artwork into the project.

    Scripts/dev/uepy.py Scripts/asset_pipeline/import_ui_art.py

Reads the PNGs that Scripts/build_ui_art.py writes to assets/ui/ and imports
them to /Game/UI/Art.  Two scripts rather than one because the generator needs
Pillow and the editor's embedded Python does not have it.

── The import settings are the whole job ───────────────────────────────────

A UI texture imported on the defaults comes out wrong in three ways that all
look like "the art is bad" rather than like a settings problem:

  TEXTUREGROUP_UI      The default is TEXTUREGROUP_World, which is subject to
                       the per-group mip bias sg.TextureQuality applies. The
                       HUD would then go soft on Low -- the same mechanism
                       that greys out the monsters' skin. UI must not scale:
                       it is the one thing on screen that is measured in
                       pixels, not in metres.
  TC_EditorIcon        "UserInterface2D", i.e. uncompressed RGBA. Block
                       compression quantises to two endpoints per 4x4 block,
                       which eats hairline borders and the antialiased edge of
                       a silhouette. These textures total a couple of MB
                       uncompressed, which is not worth trading crisp edges
                       for.
  no mipmaps           A HUD texture is drawn at its authored size and never
                       minified, so mips are dead weight -- and with them the
                       renderer can pick a blurrier one.

srgb stays on: this is colour artwork, not data.
"""

import os

import unreal

PROJECT_DIR = unreal.Paths.project_dir()
SRC_DIR = os.path.join(PROJECT_DIR, "assets", "ui")
DEST = "/Game/UI/Art"


def _log(msg):
    unreal.log_warning(f"[UI-ART] {msg}")


def import_one(png, dest_dir):
    name = os.path.splitext(os.path.basename(png))[0]
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", png)
    task.set_editor_property("destination_path", dest_dir)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", True)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    tex = unreal.EditorAssetLibrary.load_asset(f"{dest_dir}/{name}")
    if not tex:
        _log(f"FAILED {name}")
        return None
    tex.set_editor_property("srgb", True)
    tex.set_editor_property(
        "compression_settings",
        unreal.TextureCompressionSettings.TC_EDITOR_ICON)
    tex.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_UI)
    tex.set_editor_property(
        "mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
    tex.set_editor_property("never_stream", True)
    unreal.EditorAssetLibrary.save_asset(f"{dest_dir}/{name}")
    return tex


def main():
    if not os.path.isdir(SRC_DIR):
        raise RuntimeError(
            f"{SRC_DIR} does not exist -- run `python3 Scripts/build_ui_art.py` "
            "first (it needs Pillow, which is why it is a separate step)")
    pngs = sorted(f for f in os.listdir(SRC_DIR) if f.endswith(".png"))
    if not pngs:
        raise RuntimeError(f"no PNGs in {SRC_DIR}")

    unreal.EditorAssetLibrary.make_directory(DEST)
    made = []
    for f in pngs:
        tex = import_one(os.path.join(SRC_DIR, f), DEST)
        if tex:
            made.append(tex)
            _log(f"  {tex.get_name():<22} "
                 f"{tex.blueprint_get_size_x()}x{tex.blueprint_get_size_y()}")

    _log("=" * 46)
    bad = []
    for tex in made:
        if tex.get_editor_property("lod_group") != unreal.TextureGroup.TEXTUREGROUP_UI:
            bad.append(f"{tex.get_name()}: not in the UI texture group")
        if tex.get_editor_property("mip_gen_settings") != \
                unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS:
            bad.append(f"{tex.get_name()}: has mipmaps")
    for b in bad:
        _log(f"  FAIL {b}")
    if bad:
        raise RuntimeError(f"{len(bad)} UI textures imported wrong")
    _log(f"{len(made)} UI textures in {DEST}, crisp and unscaled")


main()
