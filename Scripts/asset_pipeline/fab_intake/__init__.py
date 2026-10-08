"""fab_intake -- check a downloaded Fab pack before it reaches Content/.

A pack is scanned where the launcher left it (the vault cache, or a throwaway
project it was added to), never loaded by the editor, and only copied into this
project once the scan is clean. Entry point: asset_pipeline/fab_scan.py.
Host-side, standard library only, no ``unreal``.

    rules.py        constants: allowed file types, executable signatures, the
                    names inside a package that earn a human look
    scan.py         walk a pack: file types, signatures, links, the name scan,
                    a sha256 per file -> a Report of findings
    manifest.py     the launcher's manifest beside a vault pack: does each file
                    still have the sha1 Epic served
    promote.py      copy a scanned pack into Content/, write its intake record
                    (assets/cache/fab/intake/), and check Content against it later

Tests: dev/tests/test_fab_intake.py.
"""
