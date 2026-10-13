"""fab_raw -- take in a raw Fab download: meshes and textures, not Unreal packages.

A listing downloaded as FBX (or OBJ, GLB) has no Content/ folder: it is the
source files, and only an import makes assets of them. So the intake has two
halves that meet at assets/cache/fab/raw/<Item>/ (git-ignored): the host half
picks the files, checks them and copies them there with a plan; the editor
half imports what the plan names into /Game/Fab/<Item> and records the listing.
Entry points: asset_pipeline/fab_raw_scan.py (host), fab_raw_import.py (editor).

Host-side, standard library only, no ``unreal``:
    rules.py        constants: which files are meshes and textures, which the
                    launcher or a viewer left behind, the words that name a
                    texture's role, how a file of each type starts
    listing.py      the launcher's ``metadata`` beside a download: the
                    listing's title, seller and URL; the item's folder name
    textures.py     a texture's role and set from its file name, one file per
                    role when a download repeats them, which set a mesh's
                    material slot wears
    collect.py      walk a download: what is taken, what is left behind, and
                    the findings (the per-file checks are fab_intake's)
    stage.py        copy what was taken into the cache, each file's sha256
                    checked again, and write plan.json: the asset names, the
                    destination, the texture sets

Editor-side:
    material.py     one material per texture set, its samplers wired by role
    usd_import.py   the USD half: every file a staged layer names is another
                    staged file, and only the layers nothing names are imported
    prefixes.py     what a file named (a kit's parts, an FBX's own materials,
                    a USD stage's prims) takes the project's asset prefixes
    editor_import.py  import a staged item: textures with the settings their
                    role needs, each FBX, OBJ or GLB as a static mesh, the materials worn,
                    the checks, imported.json and the fab_library entry

Tests: dev/tests/test_fab_raw.py (the host half).
"""
