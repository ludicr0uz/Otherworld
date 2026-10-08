"""promote.py -- copy a scanned pack into Content/ and remember what was copied.

A pack keeps its /Game path (references between its assets are paths), so each
file lands at the same place under this project's Content/. A file that is
already there with other bytes is a conflict and stops the whole copy: a pack
never overwrites what the project has. Only bytes are copied, so an executable
bit or a quarantine attribute on the download does not come along.

The intake record (assets/cache/fab/intake/<pack>.json, git-ignored like the
assets) holds every file's sha256 as scanned. ``verify`` compares Content/
with it; the editor re-saving an asset is one honest reason for a difference.
"""

import datetime
import glob
import hashlib
import json
import os
import shutil

from asset_pipeline import fab_library

INTAKE_DIR = os.path.join(fab_library.INDEX_DIR, "intake")


def _sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def conflicts(report, project=fab_library.PROJECT_DIR):
    """Files the pack would overwrite with different bytes."""
    out = []
    for rel, info in sorted(report.files.items()):
        dest = os.path.join(project, "Content", *rel.split("/"))
        if os.path.lexists(dest) and (not os.path.isfile(dest) or os.path.islink(dest)
                                      or _sha256(dest) != info["sha256"]):
            out.append(rel)
    return out


def promote(report, project=fab_library.PROJECT_DIR, intake_dir=None):
    """Copy the pack's files into Content/. Returns (copied, already_there, record path)."""
    root = os.path.join(report.source, "Content")
    copied = same = 0
    for rel in sorted(report.files):
        src = os.path.join(root, *rel.split("/"))
        dest = os.path.join(project, "Content", *rel.split("/"))
        if os.path.isfile(dest):
            same += 1
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copyfile(src, dest)
        copied += 1
    return copied, same, write_record(report, intake_dir or _intake_dir(project))


def _intake_dir(project):
    return os.path.join(project, os.path.relpath(INTAKE_DIR, fab_library.PROJECT_DIR))


def write_record(report, intake_dir):
    os.makedirs(intake_dir, exist_ok=True)
    path = os.path.join(intake_dir, "+".join(report.tops()) + ".json")
    with open(path, "w") as fh:
        json.dump({
            "source": report.source,
            "scanned": datetime.datetime.now().isoformat(timespec="seconds"),
            "verdict": report.verdict,
            "content": ["/Game/" + top for top in report.tops()],
            "findings": [[f.level, f.path, f.what] for f in report.findings],
            "files": report.files,
        }, fh, indent=1, sort_keys=True)
        fh.write("\n")
    return path


def verify(project=fab_library.PROJECT_DIR, intake_dir=None):
    """[(record name, rel, "missing" | "changed")] for every promoted file that differs."""
    out = []
    for path in sorted(glob.glob(os.path.join(intake_dir or _intake_dir(project), "*.json"))):
        with open(path) as fh:
            record = json.load(fh)
        for rel, info in sorted(record["files"].items()):
            dest = os.path.join(project, "Content", *rel.split("/"))
            if not os.path.isfile(dest):
                out.append((os.path.basename(path), rel, "missing"))
            elif _sha256(dest) != info["sha256"]:
                out.append((os.path.basename(path), rel, "changed"))
    return out
