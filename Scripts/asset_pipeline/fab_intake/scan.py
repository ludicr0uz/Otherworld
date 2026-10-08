"""scan.py -- walk a downloaded pack and report what does not belong in it.

Nothing here loads a package: each file is read as bytes. The name scan is a
search for known strings, not a parse of the package, so it says a name is
present, not how it is used. That is enough to put the asset in front of a
person before the editor opens it.

A source is a folder holding ``Content/``: a vault pack's ``data`` folder, or a
project the pack was added to. In a project only Content/ is looked at, and
``only`` names the top-level Content folders that belong to the pack.
"""

import hashlib
import os
import stat
from dataclasses import dataclass, field

from asset_pipeline.fab_intake import rules


@dataclass
class Finding:
    level: str                  # rules.BLOCK / REVIEW / NOTE
    path: str                   # relative to Content/, or to the source
    what: str


@dataclass
class Report:
    source: str
    files: dict = field(default_factory=dict)       # rel -> {"sha256", "size"}
    findings: list = field(default_factory=list)

    def at(self, level):
        return [f for f in self.findings if f.level == level]

    @property
    def verdict(self):
        return ("blocked" if self.at(rules.BLOCK)
                else "review" if self.at(rules.REVIEW) else "clean")

    def tops(self):
        """The top-level Content folders the pack writes."""
        return sorted({rel.split("/")[0] for rel in self.files})


def content_root(source):
    root = os.path.join(source, "Content")
    return root if os.path.isdir(root) else None


def _is_project(source):
    return any(n.endswith(".uproject") for n in os.listdir(source))


def _magic_finding(head):
    for magic, label in rules.EXECUTABLE_MAGIC:
        if head.startswith(magic):
            return label
    if head.startswith(b"MZ") and len(head) >= 0x40:
        pe = int.from_bytes(head[0x3c:0x40], "little")
        if head[pe:pe + 4] == b"PE\0\0":
            return "Windows executable"
    return None


def check_file(path, rel):
    """One file's findings and its {"sha256", "size"}. ``rel`` is for the report."""
    findings = []
    with open(path, "rb") as fh:
        data = fh.read()
    info = {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
    ext = os.path.splitext(rel)[1].lower()
    if os.path.basename(rel).startswith("."):
        findings.append(Finding(rules.BLOCK, rel, "hidden file"))
    if ext not in rules.ALLOWED_EXT:
        findings.append(Finding(rules.BLOCK, rel,
                                f"file type {ext or '(none)'} is not content"))
    label = _magic_finding(data[:4096])
    if label:
        findings.append(Finding(rules.BLOCK, rel, f"is a {label}"))
    if os.stat(path).st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
        findings.append(Finding(rules.REVIEW, rel, "is marked executable"))
    if ext in rules.PACKAGE_EXT:
        if not data.startswith(rules.PACKAGE_TAG):
            findings.append(Finding(rules.BLOCK, rel, "is not an Unreal package"))
        else:
            findings += _name_findings(data, rel)
    return findings, info


def _name_findings(data, rel):
    lowered = data.lower()
    found = [Finding(rules.REVIEW, rel, what)
             for needle, what in rules.REVIEW_NAMES if needle in lowered]
    for needle, what in rules.NOTE_NAMES:       # most specific first; one is enough
        if needle in lowered:
            found.append(Finding(rules.NOTE, rel, what))
            break
    return found


def scan(source, only=()):
    """Scan the pack under ``source``. ``only``: top-level Content folders to take."""
    source = os.path.abspath(source)
    report = Report(source)
    root = content_root(source)
    if root is None:
        report.findings.append(Finding(rules.BLOCK, ".", "no Content/ folder here"))
        return report
    if _is_project(source):
        if not only:
            report.findings.append(Finding(
                rules.BLOCK, ".", "a project: name the pack's Content folders with --only"))
            return report
    else:
        for name in sorted(os.listdir(source)):
            if name != "Content" and name not in rules.IGNORED_NAMES:
                report.findings.append(Finding(
                    rules.BLOCK, name, "outside Content/: a content pack carries only content"))
    wanted = {o.strip("/").lower() for o in only}
    for top in sorted(os.listdir(root)):
        if top in rules.IGNORED_NAMES or (wanted and top.lower() not in wanted):
            continue
        if top.lower() in rules.RESERVED_TOP:
            report.findings.append(Finding(
                rules.BLOCK, top, "writes Content/" + top + ", which the editor auto-loads"))
        _walk(os.path.join(root, top), root, report)
    missing = wanted - {t.lower() for t in report.tops()}
    for name in sorted(missing):
        report.findings.append(Finding(rules.BLOCK, name, "no such folder with files in Content/"))
    if not report.files and not report.findings:
        report.findings.append(Finding(rules.BLOCK, ".", "Content/ is empty"))
    return report


def _walk(path, root, report):
    rel = os.path.relpath(path, root).replace(os.sep, "/")
    if os.path.islink(path):
        report.findings.append(Finding(rules.BLOCK, rel, "is a symbolic link"))
    elif os.path.isdir(path):
        for name in sorted(os.listdir(path)):
            if name not in rules.IGNORED_NAMES:
                _walk(os.path.join(path, name), root, report)
    elif os.path.isfile(path):
        findings, info = check_file(path, rel)
        report.files[rel] = info
        report.findings += findings
    else:
        report.findings.append(Finding(rules.BLOCK, rel, "is not a regular file"))
