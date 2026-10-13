"""Game-ready meshes: one high-triangle static mesh built into a copy with
fewer triangles, a LOD chain, and an impostor (upright cards carrying a
picture of the mesh) as its last LOD.

Entry point: Scripts/build_game_ready_mesh.py, run OUTSIDE the editor. It
runs the two editor stages through uepy.py (build_game_ready_mesh_editor.py)
and makes the impostor's textures in between. The source mesh is read and
never written.

  spec          the settings and their defaults (LodSpec), and the arithmetic:
                triangle budgets per LOD and per slot, how a foliage slot is
                cut, distances to screen sizes
  jobs          a job (source, destination, overrides) and the named sets:
                ``trees`` is the forest's five
  planes        the impostor's geometry: where the cards stand, the camera
                for each, its cell in the atlas, its tangent basis
  paths         the working files under assets/generated/mesh_lod (git-ignored)
  geometry      in the editor: the source cut into each mesh LOD
  asset         in the editor: the copy, its LODs, screen sizes, collision,
                the stamp a later run skips it by
  capture       in the editor: the copy photographed per plane, base colour
                and world normals
  atlas         outside it (Pillow + numpy): the photographs made into the
                colour-and-mask and tangent-normal atlases
  impostor      in the editor: the atlases imported, M_Impostor and the
                mesh's instance of it, the cards as the last LOD
  preview       every LOD of a built mesh from one camera: shot in the editor,
                lit into one picture outside it
  editor_build  in the editor: the two stages, and the reports they leave
                (tests: dev/tests/test_mesh_lod.py cover spec, jobs, planes
                and atlas)
"""
