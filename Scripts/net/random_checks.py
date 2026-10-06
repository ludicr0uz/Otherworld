"""The verifiers' check that every random draw is audited (net/random_consts.py).

Chance that changes the game is rolled once, by the server; a builder that
adds a draw has to say which kind it is. Two scans, as owner_checks.py makes:

    scan_sources      the builder modules that name one of the catalog's
                      draws: exactly the audit's rows
    scan_blueprints   the Blueprints holding a Random node: none outside the
                      ones those builders author

    check_random_audit   both, and that the table itself is whole (the menu
                         verifier: the HUD is built last)
"""

import os

import unreal

from net import random_consts as R
from net.owner_checks import ALSO
from net.state_checks import _bare, _packages

BEL = unreal.BlueprintEditorLibrary
BGE = unreal.BlueprintGraphEditor
SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Not builders: the catalog itself, this audit, the dev tooling, the probes and
# the packages that run outside the editor's graphs.
NOT_BUILDERS = ("uebp/nodes/", "net/random_", "dev/", "probes/")
# A verifier names a draw to find it, not to make it.
CHECKS = ("verify", "_checks.py")


def scan_sources():
    """The modules under Scripts/ that name one of the catalog's draws."""
    found = []
    for root, _dirs, files in os.walk(SCRIPTS):
        for f in sorted(files):
            if not f.endswith(".py"):
                continue
            rel = os.path.relpath(os.path.join(root, f), SCRIPTS)
            if rel.startswith(NOT_BUILDERS) or any(c in rel for c in CHECKS):
                continue
            with open(os.path.join(root, f), encoding="utf-8") as fh:
                text = fh.read()
            if any(name in text for name in R.CATALOG_NAMES):
                found.append(rel)
    return sorted(found)


def scan_blueprints():
    """{Blueprint name: how many Random nodes its graphs hold}."""
    found = {}
    for package in sorted({*_packages(), *ALSO}):
        bp = unreal.load_asset(package)
        if not bp or not BEL.generated_class(bp):
            continue
        for graph in BEL.list_graph_names(bp):
            ed = BGE.get_graph_editor_by_name(bp, str(graph))
            if not ed:
                continue
            for n in ed.list_all_nodes():
                title = _bare(n)
                if "Random" in title and not title.startswith(("Get", "Set")) \
                        or title.startswith("GetRandom") and "Radius" in title:
                    name = package.rsplit("/", 1)[-1]
                    found[name] = found.get(name, 0) + 1
    return found


def check_random_audit(check):
    rows = [r.module for r in R.AUDIT]
    whole = all(r.kind in (R.STATE, R.COSMETIC) and r.what and r.where for r in R.AUDIT)
    check("random rolls: the audit has one row per builder, each state or "
          "cosmetic, saying what is drawn and on which machine",
          whole and len(set(rows)) == len(rows), f"{len(rows)} rows")
    named = scan_sources()
    check("random rolls: every builder that draws a random number is in the "
          "audit (net/random_consts.py), and every row's builder still draws",
          named == sorted(rows),
          f"not audited: {sorted(set(named) - set(rows))}; "
          f"no longer drawing: {sorted(set(rows) - set(named))}")
    drawn = scan_blueprints()
    strays = sorted(b for b in drawn if not b.startswith(R.BLUEPRINTS))
    missing = sorted(b for b in R.BLUEPRINTS if not any(d.startswith(b) for d in drawn))
    check("random rolls: the only Blueprints with a Random node are the ones "
          "the audited builders author, and the scan finds the nodes in each",
          not strays and not missing,
          f"unaudited: {strays}; none found in: {missing}; "
          f"{sum(drawn.values())} nodes in {len(drawn)} Blueprints")
