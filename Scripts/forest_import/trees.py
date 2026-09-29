"""Keep the tree HISMs on Nanite, and verify it.

Called by the generated import_<Level>.py (step 5, per tree HISM) and
verify_<Level>.py (step 4).

Why this is pinned. The tree meshes are dense scans (hundreds of thousands of
triangles and up) with masked, two-sided leaf cards, and that is expensive on
Nanite -- looking up into the canopy is where the frame rate falls. The obvious
escape, ``disallow_nanite`` on the component, draws the mesh's fallback
instead, and it was tried: the fallbacks (auto-built, relative error 1.0) have
**zero triangles in the leaf section** -- the simplifier deletes small
disconnected cards first -- so every tree rendered bare. Turning Nanite off on
the asset renders the full scan instead, which is worse.

So the component stays on Nanite until the leaves have a real classic-render
mesh (a fallback rebuilt with more triangles, or hand-made LODs).
"""

import unreal


def configure_tree_component(comp):
    """Called on each tree HISM as it is created."""
    comp.set_editor_property("disallow_nanite", False)


def verify_tree_component(check, spec_name, comp):
    """Checks on one tree HISM, through the verify script's harness."""
    check(f"{spec_name} Renders Nanite (fallback has no leaves)",
          not comp.get_editor_property("disallow_nanite"))
    mesh = comp.get_editor_property("static_mesh")
    settings = mesh.get_editor_property("nanite_settings") if mesh else None
    check(f"{spec_name} Mesh Keeps Nanite Data",
          bool(settings and settings.get_editor_property("enabled")))
