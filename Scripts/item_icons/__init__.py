"""The items' inventory icons: pictures of their own 3D models.

Entry point: Scripts/build_item_icons.py, run OUTSIDE the editor. It runs the
three steps in order: the capture inside the editor (capture_item_icons.py),
the compose here (Pillow + numpy), and the import
(asset_pipeline/import_ui_art.py). CLAUDE.md beside this file has the rules.

  items     the table: each item's DisplayName, Blueprint, camera view and
            share of the slot; the texture's name and size; the white tint
  portrait  the character's portrait (the I panel's): the player's body from
            the front, posed; its texture's name and size, the mesh, the clip
  paths     where the passes, the PNGs and the contact sheet go (assets/)
  capture   in the editor: the item alone before an orthographic
            SceneCapture2D, written as base colour, normals and a mask
  compose   outside it: light the passes, level, crop, fit to the canvas
  checks    check_item_icons, for verify_graphics_menu.py
"""
