#!/usr/bin/env python3
"""build_library.py -- turn export_poses.py's rows into the viewer's catalogue.

    python3 Scripts/dev/anim_library/build_library.py

Reads Saved/AnimLibrary/rows.jsonl and skeletons.json; writes catalog.json and
index.html beside them. Plain Python, no editor. The categories are guessed
from names and folders; to correct one, add a line to category_overrides.csv
(`<clip name>,<category>`) beside this file and run this again.
"""
import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
LIB = os.path.join(ROOT, "Saved", "AnimLibrary")

# First match wins, so the specific comes before the general.
CATEGORIES = (
    ("zombie", r"zombie"),
    ("ragdoll", r"ragdoll"),
    ("death", r"death|dying|die\b|agoniz"),
    ("hit reaction", r"hitreact|hit_|react|knockback|stumbl|shove|victim|knocked"),
    ("melee", r"melee|punch|stab|slash|sword|axe\b|chop|treechop|attack|swing|kick|hook|jab|knife|"
              r"headbutt|bite|biting|scratch|cross\b|takedown"),
    ("throw", r"throw|toss|overhand"),
    ("gun handling", r"fire|reload|equip|spawn|aim|ads\b|holster|dryfire|grenade|shoot|pistol_idle"),
    ("slide", r"slide"),
    ("prone / crawl", r"crawl|prone|swim|laytoidle|lay\b"),
    ("crouch", r"crouch"),
    ("sprint", r"sprint"),
    ("run / jog", r"run|jog"),
    ("walk", r"walk"),
    ("dodge / roll", r"dash|roll|dodge"),
    ("jump / land", r"jump|personjump|ninjajump|land|fall|apex|climb|mantle|vault|hurdle"),
    ("traversal", r"traversal|ladder|ledge|pole_|stair"),
    ("turn / pivot", r"turn|pivot|spin|reface"),
    ("idle", r"idle|break|stand_|poses|pose_|tpose"),
    ("interact", r"interact|pickup|open|consume|sit|farm|chest|fix|push|driv|spell|carry|sleep|computer|bike|reviv"),
    ("emote", r"dance|taunt|yes|no_|talk|call|thump|battlecry|emote|fingerguns|gesture"),
)
# A pattern starts at a word: "axe" is not in "relaxed", "cross" not in "across".
_COMPILED = tuple((c, re.compile(r"(?<![a-z])(?:" + p + ")")) for c, p in CATEGORIES)
HELD = ("rifle", "pistol", "shotgun", "unarmed", "axe", "knife", "sword", "shield",
        "lantern", "torch", "carry")


def read_rows():
    rows = []
    with open(os.path.join(LIB, "rows.jsonl")) as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def overrides():
    path = os.path.join(HERE, "category_overrides.csv")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return {r[0].strip(): r[1].strip() for r in csv.reader(f)
                if len(r) >= 2 and not r[0].startswith("#")}


def folder_of(r):
    parts = r["path"].split("/")
    if "Animations" in parts:
        rest = parts[parts.index("Animations") + 1:-1]
        return "/".join(rest) or "-"
    return "/".join(parts[3:-1]) or "-"


def category(r, over):
    if r["name"] in over:
        return over[r["name"]]
    text = (r["name"] + " " + folder_of(r)).lower()
    for cat, pat in _COMPILED:
        if pat.search(text):
            return cat
    return "other"


def tags(r):
    name = r["name"].lower()
    t = []
    for w in ("neutral", "relaxed", "dense"):
        if w in name or w in r["path"].lower():
            t.append(w)
    for w in HELD:
        if w in name:
            t.append(w)
    if name.endswith("lfoot"):
        t.append("L foot")
    if name.endswith("rfoot"):
        t.append("R foot")
    if re.search(r"_start|starts", name):
        t.append("start")
    if re.search(r"_stop", name):
        t.append("stop")
    if r["source"] != "GAS" and r["skeleton"] == "SK_UEFN_Mannequin":
        t.append("on the player")
    return t


# ---- what the game uses ---------------------------------------------------

SCRIPTS = os.path.join(ROOT, "Scripts")
SKIP_DIRS = {"anim_library", "tests", "probes", "__pycache__"}
COPY_PREFIXES = ("A_UEFN_Player_", "A_Zombie01_", "A_Wendigo01_", "A_Mannequin_",
                 "A_Adventurer01_", "A_Adventurer02_", "A_Adventurer03_")


def code_tokens():
    """{identifier: [files]} over the build scripts (not tests, probes or
    verifiers: a check naming a clip does not play it)."""
    out = {}
    for dirpath, dirs, files in os.walk(SCRIPTS):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith("verify")]
        for fn in files:
            if not fn.endswith(".py") or fn.startswith(("test_", "probe_", "verify_")):
                continue
            path = os.path.join(dirpath, fn)
            try:
                text = open(path, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            rel = os.path.relpath(path, SCRIPTS)
            for tok in set(re.findall(r"[A-Za-z0-9_]+", text)):
                if len(tok) > 6 and tok not in out:
                    out[tok] = []
                if tok in out and len(out[tok]) < 3:
                    out[tok].append(rel)
    return out


def table_names():
    """Clip names the build's own tables pick (Mixamo's player and creature
    clips, Lyra's), as library names."""
    names = {}
    sys.path.insert(0, SCRIPTS)
    try:
        from asset_pipeline import mixamo_paths as MX
        for role, (short, stem) in MX.PLAYER_CLIPS.items():
            names[f"A_Mx_{short}_{stem}"] = f"the player's {role.replace('_', ' ')} (mixamo_paths)"
        for _speed, (short, stem) in MX.LOCOMOTION.items():
            names[f"A_Mx_{short}_{stem}"] = "the zombie's locomotion (mixamo_paths)"
        names[f"A_Mx_{MX.MELEE[0]}_{MX.MELEE[1]}"] = "the zombie's melee (mixamo_paths)"
        names[f"A_Mx_{MX.ROAR[0]}_{MX.ROAR[1]}"] = "the wendigo's roar (mixamo_paths)"
    except Exception as e:                       # noqa: BLE001 - say, carry on
        print("note: mixamo_paths not read:", e)
    try:
        from asset_pipeline import lyra_paths as LY
        for path in LY.CLIPS:
            names[path.rsplit("/", 1)[1]] = "the player's punch and ready poses (lyra_paths)"
    except Exception as e:                       # noqa: BLE001
        print("note: lyra_paths not read:", e)
    return names


def used_levels(rows):
    """{clip id: (level, [why])}; level is "game" or "pool"."""
    try:
        usage = json.load(open(os.path.join(LIB, "usage.json")))
    except OSError:
        usage = {}
        print("note: no usage.json (run export_usage.py): only the code's evidence")
    toks, tables = code_tokens(), table_names()
    names = {r["name"] for r in rows}
    ev = {}                                       # name -> {"game": [...], "pool": [...]}

    def add(name, kind, why):
        e = ev.setdefault(name, {"game": [], "pool": []})
        if why not in e[kind] and len(e[kind]) < 5:
            e[kind].append(why)

    def originals(name):
        """The clip a retargeted copy was made from, as library names."""
        for pre in COPY_PREFIXES:
            if name.startswith(pre):
                rest = name[len(pre):]
                return [n for n in (rest, "A_" + rest) if n in names and n != name]
        return []

    for r in rows:
        name, u = r["name"], usage.get(r["id"], {})
        for ref in u.get("game", []):
            add(name, "game", "referenced by " + ref.rsplit("/", 1)[1])
        if u.get("reach"):
            sets = sorted({x.split("/")[-2] for x in u["reach"]})
            add(name, "pool", "motion-matching pool: " + ", ".join(sets[:4]))
        cands = {name}
        if name.startswith("A_"):
            cands.add(name[2:])
        for pre in COPY_PREFIXES:
            if name.startswith(pre):
                cands.add(name[len(pre):])
        for c in cands:
            for f in toks.get(c, [])[:1]:
                add(name, "game", "named in " + f)
        if name in tables:
            add(name, "game", tables[name])
    # a copy's evidence counts for its source, and the source's for the copy
    for r in rows:
        for o in originals(r["name"]):
            for kind in ("game", "pool"):
                for why in ev.get(r["name"], {}).get(kind, []):
                    add(o, kind, why + " (via the copy " + r["name"] + ")")
    out = {}
    for r in rows:
        e = ev.get(r["name"])
        if not e:
            continue
        if e["game"]:
            out[r["id"]] = ("game", e["game"] + e["pool"])
        elif e["pool"]:
            out[r["id"]] = ("pool", e["pool"])
    return out


def main():
    rows, over = read_rows(), overrides()
    skeletons = json.load(open(os.path.join(LIB, "skeletons.json")))
    clips = []
    for r in rows:
        moves = r.get("frames", 0) > 0
        speed = round(r.get("forward_cm", 0) / r["length"]) if moves and r["length"] > 0.2 else 0
        clips.append({
            "id": r["id"], "name": r["name"], "path": r["path"], "source": r["source"],
            "skeleton": r["skeleton"], "length": r["length"], "frames": r.get("frames", 0),
            "loop": bool(r.get("loops")), "speed": speed,
            "travel": r.get("travel_cm", 0), "rise": r.get("pelvis_rise_cm", 0),
            "rootMotion": r.get("root_motion", False), "folder": folder_of(r),
            "cat": category(r, over), "tags": tags(r), "additive": r["additive"] != "NONE",
        })
    used = used_levels(rows)
    for c in clips:
        level, why = used.get(c["id"], ("", []))
        c["use"], c["why"] = level, why
    clips.sort(key=lambda c: (c["cat"], c["name"]))
    cats = {}
    for c in clips:
        cats[c["cat"]] = cats.get(c["cat"], 0) + 1
    with open(os.path.join(LIB, "catalog.json"), "w") as f:
        json.dump({"skeletons": skeletons, "clips": clips}, f, separators=(",", ":"))
    with open(os.path.join(HERE, "viewer.html")) as src, \
            open(os.path.join(LIB, "index.html"), "w") as dst:
        dst.write(src.read())
    n_game = sum(1 for c in clips if c["use"] == "game")
    n_pool = sum(1 for c in clips if c["use"] == "pool")
    print(f"used: {n_game} in game, {n_pool} only in the motion-matching pool")
    print(f"{len(clips)} clips; no pose for {sum(1 for c in clips if not c['frames'])} (additive)")
    for c, n in sorted(cats.items(), key=lambda kv: -kv[1]):
        print(f"  {n:5d}  {c}")
    print(f"serve with: python3 {os.path.relpath(os.path.join(HERE, 'serve.py'), ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
