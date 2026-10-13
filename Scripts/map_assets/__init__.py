"""The asset browser: one HTML page of every mesh in the project (the pieces a
map is built from, the weapons, the items, the clothing, the characters),
with its picture and how many triangles it is made of.

Entry point: Scripts/build_map_asset_browser.py, run OUTSIDE the editor. It
runs the scan inside the editor (scan_map_assets.py, through uepy.py) and
writes the page here. Nothing lists the meshes: each run asks the asset
registry what exists, so a pack added since the last run is on the page.

  paths      where the scan, the passes, the pictures and the page go
             (assets/generated, git-ignored), and a mesh's file names
  kinds      what a mesh is, from its path alone: the table that names its
             category (the page's tabs) and its kind, and its pack
  view       the camera's numbers, which the capture and the shading share,
             and the turn's: how many frames round the mesh
  inventory  in the editor: every StaticMesh and SkeletalMesh under /Game from the registry's
             tags (no mesh is loaded), and the levels that use each
  thumbs     in the editor: each mesh alone before a SceneCapture2D, written
             as base colour and normals, from its picture's view and from
             all round it; only the new and the changed
  shade      outside it (Pillow + numpy): those passes lit into the picture,
             and the turn's into one strip of frames
  page       outside it: the page, with the scan embedded in it and the
             pictures beside it; a click on a picture opens it large, where
             a drag turns the mesh (tests: dev/tests/test_map_assets.py cover
             kinds and page)
"""
