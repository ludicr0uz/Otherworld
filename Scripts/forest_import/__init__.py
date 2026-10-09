"""In-editor steps the generated import_<Level>.py / verify_<Level>.py scripts
call, rather than carrying inline. Unlike forest_generator/, these import
``unreal`` and only run inside the editor.

  bushes          Plant the bushes from the grass sidecar as per-cell HISMs, and verify them
  foliage_assets  Build the generated grass and bush meshes, and their material, in the editor
  grass           Plant the grass sidecar into the open level as per-cell HISMs, and verify it
  tree_assets     Build the derived tree meshes under /Game/Forest/Trees, and verify them
  trees           Plant the trees into the open level as per-cell HISMs, and verify them
  wind            Wind in the materials: MPC_Wind, and the world-position offset (WPO) that makes the grass and the trees move
"""
