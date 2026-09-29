"""Render the tree HISMs from their light fallback mesh instead of Nanite, and
verify it.

Called by the generated import_<Level>.py (step 5, per tree HISM) and
verify_<Level>.py (step 4).

Why. The tree meshes are dense scans (hundreds of thousands of triangles and
up) with masked, two-sided leaf cards. A masked material pushes Nanite onto its
programmable raster path: every leaf pixel runs the alpha test, card after
card, in the main view and again in every shadow cascade. Looking up into the
canopy stacks the most cards, and that is where the frame rate fell.

Every Nanite mesh also carries a fallback mesh -- a few thousand triangles here
-- for platforms without Nanite. ``disallow_nanite`` on the component draws
that instead, through classic rendering, which lays depth down first so each
screen pixel is shaded once however many leaf cards sit behind it.

This is a component setting, not an asset one, on purpose: the meshes keep
their Nanite data (so it is one flag to go back), and turning Nanite off on
the asset itself would render the full-density scan instead of the fallback.
"""

import unreal


def configure_tree_component(comp):
    """Called on each tree HISM as it is created."""
    comp.set_editor_property("disallow_nanite", True)


def verify_tree_component(check, spec_name, comp):
    """Checks on one tree HISM, through the verify script's harness."""
    check(f"{spec_name} Draws Fallback Mesh (Nanite Disallowed)",
          comp.get_editor_property("disallow_nanite"))
    # The fallback only exists while the asset keeps its Nanite data.
    mesh = comp.get_editor_property("static_mesh")
    settings = mesh.get_editor_property("nanite_settings") if mesh else None
    check(f"{spec_name} Mesh Keeps Nanite Data",
          bool(settings and settings.get_editor_property("enabled")))
