"""collect.py -- walk a raw download: what is taken, what stays, what is wrong.

Taken is a mesh or a texture, by extension and by how the file starts. What
stays behind is listed and never copied: the launcher's own files, a readme,
an archive (never opened), a sidecar this import has no use for. A file that
stays is still looked at for one thing, being a program, because a download
that carries one is not what it claims to be.

The per-file checks (hidden, executable, symbolic link, the sha256) are
fab_intake.scan's, so a raw download and a pack are held to the same ones.
"""

import os
from dataclasses import dataclass, field

from asset_pipeline.fab_intake import rules as intake_rules
from asset_pipeline.fab_intake import scan as intake_scan
from asset_pipeline.fab_intake.scan import Finding
from asset_pipeline.fab_raw import listing, rules, textures

BLOCK, REVIEW, NOTE = intake_rules.BLOCK, intake_rules.REVIEW, intake_rules.NOTE


@dataclass
class Item:
    source: str
    title: str = ""
    url: str = ""
    seller: str = ""
    slug: str = ""
    files: dict = field(default_factory=dict)       # rel -> {"sha256", "size"}, the taken
    meshes: list = field(default_factory=list)      # rel
    sets: dict = field(default_factory=dict)        # set key -> {role: rel}
    loose: list = field(default_factory=list)       # textures with no role
    left: list = field(default_factory=list)        # (rel, why): not taken
    findings: list = field(default_factory=list)

    def at(self, level):
        return [f for f in self.findings if f.level == level]

    @property
    def verdict(self):
        return ("blocked" if self.at(BLOCK) else "review" if self.at(REVIEW) else "clean")

    def texture_files(self):
        return sorted({rel for roles in self.sets.values() for rel in roles.values()}
                      | set(self.loose))


def _signature_finding(path, rel, ext):
    wanted = rules.SIGNATURES.get(ext)
    if not wanted:
        return None
    with open(path, "rb") as fh:
        head = fh.read(32)
    if any(head.startswith(sig) for sig in wanted):
        return None
    return Finding(BLOCK, rel, f"does not start like a {ext} file")


def _program_finding(path, rel):
    with open(path, "rb") as fh:
        label = intake_scan._magic_finding(fh.read(4096))
    return Finding(BLOCK, rel, f"is a {label}") if label else None


def _why_left(rel, depth):
    name = os.path.basename(rel)
    stem, ext = os.path.splitext(name.lower())
    if depth <= 1 and name == rules.LAUNCHER_METADATA:
        return None                                     # the launcher's: not worth a line
    if depth <= 1 and stem == rules.LAUNCHER_THUMBNAIL and ext in rules.TEXTURE_EXT:
        return None
    if stem in rules.JUNK_TEXTURE_STEMS:
        return "a model viewer's ground shadow"
    if ext in rules.ARCHIVE_EXT:
        return "an archive: never opened, nothing in it is imported"
    if ext in rules.MESH_EXT or ext in rules.TEXTURE_EXT:
        return ""                                       # taken
    return "not a mesh or a texture"


def _walk(path, root, item, candidates):
    rel = os.path.relpath(path, root).replace(os.sep, "/")
    if os.path.islink(path):
        item.findings.append(Finding(BLOCK, rel, "is a symbolic link"))
    elif os.path.isdir(path):
        for name in sorted(os.listdir(path)):
            if name not in intake_rules.IGNORED_NAMES:
                _walk(os.path.join(path, name), root, item, candidates)
    elif not os.path.isfile(path):
        item.findings.append(Finding(BLOCK, rel, "is not a regular file"))
    else:
        why = _why_left(rel, rel.count("/"))
        if why == "":
            candidates.append(rel)
            return
        if why:
            item.left.append((rel, why))
        found = _program_finding(path, rel)
        if found:
            item.findings.append(found)


def _take(item, root, rel):
    path = os.path.join(root, *rel.split("/"))
    findings, info = intake_scan.check_file(path, rel)
    found = _signature_finding(path, rel, os.path.splitext(rel)[1].lower())
    item.findings += findings + ([found] if found else [])
    item.files[rel] = info


def collect(source, title=""):
    """The Item for the download at ``source`` (a folder)."""
    source = os.path.abspath(source)
    meta = listing.read(source)
    item = Item(source, title or meta["title"], meta["url"], meta["seller"])
    item.slug = listing.slug(item.title)
    candidates = []
    _walk(source, source, item, candidates)

    def ext(rel):
        return os.path.splitext(rel)[1].lower()

    sizes = {rel: os.path.getsize(os.path.join(source, *rel.split("/")))
             for rel in candidates if ext(rel) in rules.TEXTURE_EXT}
    item.sets, item.loose, repeats = textures.group(sizes)
    item.left += [(rel, "repeats a texture already taken") for rel in repeats]
    # A set with no name of its own ("Normal.png") is the item's.
    if "" in item.sets:
        item.sets[item.slug] = {**item.sets.pop(""), **item.sets.get(item.slug, {})}
    seen = {}
    for rel in sorted(r for r in candidates if ext(r) in rules.MESH_EXT):
        _take(item, source, rel)
        twin = seen.setdefault((os.path.basename(rel).lower(), item.files[rel]["sha256"]), rel)
        if twin != rel:
            del item.files[rel]
            item.left.append((rel, f"the same file as {twin}"))
        else:
            item.meshes.append(rel)
    for rel in item.texture_files():
        _take(item, source, rel)
    item.left.sort()
    if not item.meshes:
        item.findings.append(Finding(BLOCK, ".", "no mesh here (.fbx, .obj, .glb, .usd)"))
    return item
