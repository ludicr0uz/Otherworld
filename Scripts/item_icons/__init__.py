"""The items' inventory icons: pictures of their own 3D models.

Entry point: Scripts/build_item_icons.py, run OUTSIDE the editor. It runs the
three steps in order: the capture inside the editor (capture_item_icons.py),
the compose here (Pillow + numpy), and the import
(asset_pipeline/import_ui_art.py). CLAUDE.md beside this file has the rules.

  items     the table: each item's DisplayName, Blueprint, camera view and
            share of the slot; the texture's name and size; the white tint
  portrait  the character's portrait (the I panel's): the player's MetaHuman
            from the front, posed; its texture's name and size, the meshes,
            the grooms, the clip
  portrait_capture  in the editor: that body, face and hair stood before the
            camera in the idle's first frame, and shot through capture's passes
  paths     where the passes, the PNGs and the contact sheet go (assets/);
            the names of a picture's part masks
  parts     outside it: what light mends by the part masks (the seam between
            face and body, the hair's missing normals)
  capture   in the editor: the item alone before an orthographic
            SceneCapture2D, written as base colour, normals, a mask and depth
  exr       outside it: reads the depth pass (an EXR, which Pillow cannot)
  light     outside it: light the passes as a studio shot (cast shadows and
            occlusion from the depth, key and fill, gloss), then level
  compose   outside it: crop the lit picture, fit it to the canvas, draw the
            thin black contour round it; the contact sheet
  checks    check_item_icons, for verify_graphics_menu.py
"""
