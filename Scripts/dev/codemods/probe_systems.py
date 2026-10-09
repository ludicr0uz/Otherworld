"""One-off: propose a SYSTEMS tuple for each Scripts/probes/probe_*.py and write it.

Usage: python3 Scripts/dev/codemods/probe_systems.py [--write]
Tags come from the file name's words first, then the probe's imports. Without
--write it only prints the table. A probe that already has SYSTEMS is skipped.
"""

import glob
import os
import re
import sys

PROBES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "probes")

NAME_RULES = [
    (r"^net_", "net"), (r"^net_load|perf_audit", "load"), (r"title|join_dead", "title"),
    (r"gun|shot|sight|ads|scope|headshot|hold_breath|carry|bullet|reload|recoil", "weapons"),
    (r"inventory|slots|pickup|drag|glimmer|record|item", "inventory"),
    (r"health|death|dead|respawn|hit_react|hit_bodies|bleed|kill", "health"),
    (r"knife|axe|punch|melee|chop|hot_blade|swing", "melee"),
    (r"throw|stick", "throw"),
    (r"survival|consume|campfire|night_cold|bleeding|lit_stick", "survival"),
    (r"clothing", "clothing"), (r"loot", "loot"),
    (r"wendigo|zombie|npc", "npc"),
    (r"hud|legal|umg|hit_marker", "hud"),
    (r"menu|tuning|tune_keep|save_exit|look_sensitivity|dev_all", "menu"),
    (r"sound|ambience", "sound"),
    (r"day_night|night_sky|^wind$|world", "world"),
    (r"stance|gas_|hold_poses|player_gait|metahuman|bound_|shotgun_h|shotgun_t|head_hide", "animation"),
    (r"sprint|move|slide|gas_locomotion|gas_traversal|stance", "movement"),
]
IMPORT_RULES = {"survival": "survival", "npc": "npc", "loot": "loot", "world": "world",
                "graphics_menu": "menu", "clothing": "clothing", "net": "net", "combat": "weapons"}


def propose(path):
    name = os.path.basename(path)[len("probe_"):-3]
    src = open(path).read()
    tags = [t for pat, t in NAME_RULES if re.search(pat, name)]
    if not tags:
        for mod in re.findall(r"^(?:from|import) (\w+)", src, re.M):
            if mod in IMPORT_RULES and IMPORT_RULES[mod] not in tags:
                tags.append(IMPORT_RULES[mod])
    return name, src, tags or ["weapons"]


def write(path, src, tags):
    line = f"SYSTEMS = ({', '.join(repr(t) for t in tags)}{',' if len(tags) == 1 else ''})\n"
    m = re.search(r'^(""".*?"""\n)', src, re.S)
    if not m:
        return line + "\n" + src
    return src[:m.end()] + "\n" + line + src[m.end():]


def main():
    do_write = "--write" in sys.argv
    for path in sorted(glob.glob(os.path.join(PROBES, "probe_*.py"))):
        name, src, tags = propose(path)
        if re.search(r"^SYSTEMS\s*=", src, re.M):
            continue
        print(f"{name:34} {', '.join(tags)}")
        if do_write:
            open(path, "w").write(write(path, src, tags))


if __name__ == "__main__":
    main()
