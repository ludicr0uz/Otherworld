"""Which probes a change can affect: a path maps to systems, systems to probes.

`uepy.py --probes-for [paths]` runs the probes whose SYSTEMS (Scripts/probes/systems.py)
meet the systems of the changed paths, one --game launch for the single-player ones and
one --net launch for the networked ones. The first matching rule wins; a path no rule
knows maps to nothing, and the caller says so.
"""
import ast
import glob
import os
import subprocess

PROBES_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                           "..", "..", "probes"))
ROOT = os.path.normpath(os.path.join(PROBES_DIR, "..", ".."))

# (path prefix or substring marker, systems). Prefix rules match the start of the
# repo-relative path; a "*word*" rule matches when `word` is in the file name.
RULES = (
    ("Source/Otherworld/*Shot*", ("weapons", "net")),
    ("Source/Otherworld/*Move*", ("movement", "net")),
    ("Source/Otherworld/*Pose*", ("animation", "net")),
    ("Source/Otherworld/*Inventory*", ("inventory", "net")),
    ("Source/Otherworld/", ("net", "movement", "weapons")),
    ("Source/OtherworldEditor/", ()),
    ("Scripts/combat/weapon_component/", ("weapons",)),
    ("Scripts/combat/*gas_*", ("movement", "animation")),
    ("Scripts/combat/*player_move*", ("movement", "net")),
    ("Scripts/combat/*heal*", ("health",)),
    ("Scripts/combat/*health*", ("health",)),
    ("Scripts/combat/*knife*", ("melee", "throw")),
    ("Scripts/combat/*axe*", ("melee", "throw")),
    ("Scripts/combat/*melee*", ("melee",)),
    ("Scripts/combat/", ("weapons", "health", "inventory")),
    ("Scripts/npc/", ("npc",)),
    ("Scripts/forest_generator/npc_", ("npc",)),
    ("Scripts/forest_generator/", ("world",)),
    ("Scripts/graphics_menu/", ("menu", "hud", "title")),
    ("Scripts/survival/", ("survival", "health")),
    ("Scripts/world/", ("world",)),
    ("Scripts/loot/", ("loot",)),
    ("Scripts/clothing/", ("clothing", "inventory")),
    ("Scripts/Sound/", ("sound",)),
    ("Scripts/net/", ("net",)),
    ("Scripts/probes/", ()),
)


def systems_for(path):
    """The systems a repo-relative path can affect (empty: no rule, or none)."""
    path = path.replace(os.sep, "/")
    for rule, systems in RULES:
        if "*" in rule:
            prefix, word = rule.split("*", 1)[0], rule.split("*")[1]
            if path.startswith(prefix) and word.lower() in os.path.basename(path).lower():
                return systems
        elif path.startswith(rule):
            return systems
    return ()


def changed_paths(root=ROOT):
    """`git diff --name-only` against HEAD plus untracked files."""
    out = []
    for cmd in (["git", "diff", "--name-only", "HEAD"],
                ["git", "ls-files", "--others", "--exclude-standard"]):
        r = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
        out += [ln for ln in r.stdout.splitlines() if ln]
    return out


def _literal(tree, name):
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == name for t in node.targets):
            return ast.literal_eval(node.value)
    return None


def declared(path):
    """(SYSTEMS, RUNS_ON) of a probe file, read from source."""
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    return tuple(_literal(tree, "SYSTEMS") or ()), _literal(tree, "RUNS_ON")


def probe_kind(systems, runs_on):
    """'net', 'title' (game with the title kept), 'load' (needs bots) or 'game'."""
    if "title" in systems and runs_on is not None and "client" in str(runs_on):
        return "net-title"
    if "load" in systems:
        return "load"
    if runs_on and "standalone" not in runs_on and any(r.startswith(("server", "client")) for r in runs_on):
        return "net"
    return "title" if "title" in systems else "game"


def clients_needed(runs_on):
    """Clients a net probe wants: the highest 'client N' it names, at least 1."""
    n = 1
    for r in runs_on or ():
        if r.startswith("client "):
            n = max(n, int(r.split()[1]))
    return n


def plan(paths, probes_dir=PROBES_DIR):
    """Map paths to launches: {'systems': set, 'unmapped': [...], 'game': [...],
    'title': [...], 'net': [...], 'net-title': [...], 'load': [...]} (probe file paths)."""
    systems, unmapped = set(), []
    for p in paths:
        s = systems_for(p)
        if s:
            systems.update(s)
        elif not p.startswith(("Scripts/probes/", "Scripts/dev/", "Content/")):
            unmapped.append(p)
    out = {"systems": systems, "unmapped": unmapped, "game": [], "title": [],
           "net": [], "net-title": [], "load": [], "clients": 1}
    for path in sorted(glob.glob(os.path.join(probes_dir, "probe_*.py"))):
        tags, runs_on = declared(path)
        if not systems.intersection(tags):
            continue
        kind = probe_kind(tags, runs_on)
        out[kind].append(path)
        if kind in ("net", "net-title"):
            out["clients"] = max(out["clients"], clients_needed(runs_on))
    return out
