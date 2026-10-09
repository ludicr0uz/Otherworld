"""Named probe sets: which probes dev-team's gate runs before and after a task.

``SMOKE`` covers each system once: one single-player ``--game`` launch and one
``--net --clients 2`` launch. ``FULL`` is every probe on disk. A set is
``{"game": [...], "title": [...], "net": [...], "clients": N}`` of probe names
(file stems); ``resolve`` turns a set's name into one. Plain data and the
standard library only: the gate imports it outside the editor.
"""

import ast
import glob
import os

PROBES_DIR = os.path.dirname(os.path.abspath(__file__))

SMOKE = {
    # Order matters: the probes share one boot, so those that read the level as
    # it starts come first and the ones that fight (and may get the player killed) last.
    "game": [
        "probe_slots",              # inventory
        "probe_main_menu",          # menu
        "probe_clothing",           # clothing
        "probe_consume_heal",       # survival
        "probe_day_night",          # world
        "probe_gas_locomotion",     # animation, movement
        "probe_corpse_loot",        # loot
        "probe_hit_react",          # health
        "probe_npc_behavior_tree",  # npc
        "probe_headshot",           # weapons
        "probe_knife",              # melee
        "probe_throw",              # throw
    ],
    "title": [],
    "net": [
        "probe_net_join",
        "probe_net_fire",
        "probe_net_inventory",
        "probe_net_melee",
        "probe_net_survival",
        "probe_net_see_each_other",
        "probe_net_pvp",
        "probe_net_death",
    ],
    "clients": 2,
}

NAMES = ("SMOKE", "FULL")


def _declared(path):
    """(SYSTEMS, RUNS_ON) of a probe file, read from its source."""
    found = {}
    with open(path, encoding="utf-8") as fh:
        for node in ast.parse(fh.read()).body:
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if getattr(t, "id", "") in ("SYSTEMS", "RUNS_ON"):
                        found[t.id] = ast.literal_eval(node.value)
    return tuple(found.get("SYSTEMS") or ()), found.get("RUNS_ON")


def parse(text):
    """Probe names from a comma- or space-separated list ("a, b c")."""
    return [w for w in text.replace(",", " ").split() if w]


def full(probes_dir=PROBES_DIR):
    """Every probe, grouped by the launch that runs it. A probe that needs
    ``--bots`` (system ``load``) is left out; one that only runs on a server
    and its clients is a net probe, the rest run in one single-player game."""
    out = {"game": [], "title": [], "net": [], "clients": 1}
    for path in sorted(glob.glob(os.path.join(probes_dir, "probe_*.py"))):
        name = os.path.basename(path)[:-3]
        systems, runs_on = _declared(path)
        if "load" in systems:
            continue
        on = tuple(runs_on or ())
        if on and "standalone" not in on and any(r.startswith(("server", "client")) for r in on):
            out["net"].append(name)
            for r in on:
                if r.startswith("client "):
                    out["clients"] = max(out["clients"], int(r.split()[1]))
        elif "title" in systems:
            out["title"].append(name)
        else:
            out["game"].append(name)
    out["clients"] = max(out["clients"], 2)
    return out


def resolve(name, probes_dir=PROBES_DIR):
    """The set called ``name`` (SMOKE or FULL, any case), or a list of probe names
    after ``probes:``. Raises ValueError for anything else."""
    key = name.strip()
    if key.upper() == "SMOKE":
        return {k: list(v) if isinstance(v, list) else v for k, v in SMOKE.items()}
    if key.upper() == "FULL":
        return full(probes_dir)
    raise ValueError(f"unknown probe set {name!r} (one of {', '.join(NAMES)}, or none)")


def missing(probe_set, probes_dir=PROBES_DIR):
    """Names in a set with no file on disk."""
    return [n for kind in ("game", "title", "net") for n in probe_set[kind]
            if not os.path.isfile(os.path.join(probes_dir, n + ".py"))]
