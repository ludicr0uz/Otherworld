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


# Which verifier reads what a path's builder writes: `uepy.py --verify-for [paths]`
# runs exactly those, instead of a suite. A verifier is one script under Scripts/
# (or a generated level's own). The first matching rule wins; a path no rule names
# maps to no verifier: probes, docs, Scripts/dev and tests change nothing a
# verifier reads, and the gate runs the whole suite around the session anyway.
WEAPONS = "verify_weapons_and_combat.py"
LEVELS = tuple(f"generated_levels/{n}/verify_{n}.py"
               for n in ("Lvl_Probe_50m", "Lvl_Forest_200m", "Lvl_Forest_1000m"))
VERIFIER_RULES = (
    ("Scripts/generated_levels/Lvl_Probe_50m/", LEVELS[:1]),
    ("Scripts/generated_levels/Lvl_Forest_200m/", LEVELS[1:2]),
    ("Scripts/generated_levels/Lvl_Forest_1000m/", LEVELS[2:]),
    ("Scripts/forest_generator/", LEVELS),
    ("Scripts/combat/", (WEAPONS,)),
    ("Scripts/loot/", (WEAPONS,)),
    ("Scripts/net/", (WEAPONS,)),
    ("Scripts/Sound/", (WEAPONS,)),
    ("Scripts/npc/", ("verify_npc_blueprints.py",)),
    ("Scripts/graphics_menu/", ("verify_graphics_menu.py",)),
    ("Scripts/survival/", ("verify_survival.py",)),
    ("Scripts/world/", ("verify_day_night.py",)),
    ("Scripts/clothing/", ("verify_clothing.py",)),
    ("Scripts/build_weapons_and_combat.py", (WEAPONS,)),
    ("Scripts/build_sound.py", (WEAPONS,)),
    ("Scripts/build_npc_blueprints.py", ("verify_npc_blueprints.py",)),
    ("Scripts/build_graphics_menu.py", ("verify_graphics_menu.py",)),
    ("Scripts/build_survival.py", ("verify_survival.py",)),
    ("Scripts/build_day_night.py", ("verify_day_night.py",)),
    ("Scripts/build_clothing.py", ("verify_clothing.py",)),
    # The C++ module: what the weapon component, the NPCs and the levels load.
    ("Source/Otherworld/", (WEAPONS, "verify_npc_blueprints.py") + LEVELS),
)


def verifiers_for(paths):
    """The verifier scripts (repo-relative, under Scripts/) the paths map to,
    in suite order, each once. A path that is a verifier maps to itself."""
    out = []
    for path in paths:
        path = path.replace(os.sep, "/")
        found = ()
        base = os.path.basename(path)
        if path.startswith("Scripts/") and base.startswith("verify_") and base.endswith(".py"):
            found = (path[len("Scripts/"):],)
        else:
            for rule, scripts in VERIFIER_RULES:
                if path.startswith(rule):
                    found = scripts
                    break
        for script in found:
            if script not in out:
                out.append(script)
    return [os.path.join("Scripts", s) for s in sorted(out, key=_suite_order)]


def _suite_order(script):
    """The gate's order: the top-level verifiers by name, then the levels."""
    return (script.startswith("generated_levels/"), script)


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
