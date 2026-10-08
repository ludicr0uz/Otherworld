"""manifest.py -- a vault pack against the manifest the launcher saved for it.

The launcher keeps a JSON manifest for each pack it downloads
(VaultCache/FabLibrary/<pack>-<id>/unreal-engine/manifest): every file's path
and sha1, the sha1 written as twenty three-digit decimals. Matching it says
the files on disk are the ones Epic served, and that the manifest lists no
file the scan did not see. It says nothing about whether they are safe.
"""

import glob
import hashlib
import json
import os

from asset_pipeline.fab_intake import rules
from asset_pipeline.fab_intake.scan import Finding


def find_for(source):
    """The JSON manifest for the vault pack at ``source`` (its data folder), or None."""
    pack = os.path.dirname(os.path.abspath(source))
    library = os.path.join(os.path.dirname(pack), "FabLibrary")
    for path in sorted(glob.glob(os.path.join(library, "*", "*", "manifest"))):
        try:
            if _load(path).get("AppNameString") == os.path.basename(pack):
                return path
        except (ValueError, OSError):
            continue
    return None


def _load(path):
    with open(path) as fh:
        return json.load(fh)


def _sha1_hex(decimals):
    return bytes(int(decimals[i:i + 3]) for i in range(0, len(decimals), 3)).hex()


def check(source, manifest_path):
    """Findings for every file that differs from, or is missing from, the manifest."""
    findings = []
    listed = set()
    for entry in _load(manifest_path).get("FileManifestList", []):
        rel = entry["Filename"]
        listed.add(rel)
        path = os.path.join(source, *rel.split("/"))
        if not os.path.isfile(path):
            findings.append(Finding(rules.BLOCK, rel, "in the manifest but not on disk"))
            continue
        with open(path, "rb") as fh:
            sha1 = hashlib.sha1(fh.read()).hexdigest()
        if sha1 != _sha1_hex(entry["FileHash"]):
            findings.append(Finding(rules.BLOCK, rel, "differs from what Epic served (sha1)"))
    for dirpath, _dirs, files in os.walk(source):
        for name in files:
            rel = os.path.relpath(os.path.join(dirpath, name), source).replace(os.sep, "/")
            if rel not in listed and name not in rules.IGNORED_NAMES:
                findings.append(Finding(rules.BLOCK, rel, "on disk but not in the manifest"))
    return findings
