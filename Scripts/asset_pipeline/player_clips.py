"""player_clips -- the table of the player's Mixamo clips: which download
plays which role (player_clips.csv, a row per role), and the rules a swap of
one holds to.  Plain Python (no ``unreal``, and nothing of this package), so
mixamo_paths reads its PLAYER_CLIPS from here and the dev unit tests run it.

    role,pack,clip,hit_s
    axe_swing,MeleeAxe,StandingMeleeAttackDownward,0.85

``pack`` is a short name of mixamo_paths.PLAYER_PACKS, ``clip`` the FBX's
name as mixamo_paths.clip_stem spells it, and ``hit_s`` the time in Mixamo's
clip at which a swing strikes (combat/melee_clips.py cuts the bake to it;
empty for a role that is not a swing).  The file is a table and not a dict in
a module because a command rewrites it: Scripts/dev/swap_clip.py changes one
row, and the diff of a swap is that row.
"""

import collections
import os

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "player_clips.csv")
HEADER = "role,pack,clip,hit_s"

Row = collections.namedtuple("Row", "role pack clip hit_s")

# {role: (what it is, the weapons build's steps that bake it)}.  The steps
# are combat/build_steps.py's (``uepy.py --only``); a melee role's own clip is
# baked first, alone (melee_clips.build_melee_clips(skin, roles)), so a swing
# needs no step: nothing else is made from it.  A ready pose is also what its
# item's grip is solved in, and the crawl is a node of the worn anim graph.
ROLES = {
    "knife_ready": ("the knife held ready, looping", ("knife",)),
    "knife_swing": ("the knife's swing", ()),
    "axe_ready": ("the axe held ready, looping", ("axe",)),
    "axe_swing": ("the axe's swing", ()),
    "prone_crawl": ("the crawl while prone", ("body", "anim_patches")),
}
SWINGS = ("knife_swing", "axe_swing")


def parse(text):
    """The rows of the table's text, in order.  A malformed line raises."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines or lines[0].strip() != HEADER:
        raise ValueError(f"player_clips.csv: the first line is not {HEADER!r}")
    rows = []
    for line in lines[1:]:
        cells = [c.strip() for c in line.split(",")]
        if len(cells) != 4 or not all(cells[:3]):
            raise ValueError(f"player_clips.csv: not role,pack,clip,hit_s: {line!r}")
        rows.append(Row(cells[0], cells[1], cells[2], float(cells[3]) if cells[3] else None))
    return rows


def read_rows(path=CSV_PATH):
    with open(path, encoding="utf-8") as f:
        return parse(f.read())


def line_of(row):
    return (f"{row.role},{row.pack},{row.clip},"
            + ("" if row.hit_s is None else f"{row.hit_s:.2f}"))


def set_row(text, row):
    """``text`` with ``row.role``'s line replaced, every other line as it
    was.  A role with no line is an error: a swap never adds one."""
    check_role(row.role, [r.role for r in parse(text)])
    lines = text.splitlines()
    at = [i for i, ln in enumerate(lines) if ln.split(",")[0].strip() == row.role]
    lines[at[0]] = line_of(row)
    return "\n".join(lines) + "\n"


def write_row(row, path=CSV_PATH):
    """Rewrite ``row.role``'s line of the file; returns the row it replaced."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    new = set_row(text, row)
    with open(path, "w", encoding="utf-8") as f:
        f.write(new)
    return next(r for r in parse(text) if r.role == row.role)


def check_role(role, roles=None):
    """Raise, naming the roles there are, unless ``role`` is one."""
    roles = list(ROLES if roles is None else roles)
    if role not in roles:
        raise ValueError(f"no such role {role!r}; the roles: "
                         + ", ".join(f"{r} ({ROLES[r][0]})" if r in ROLES else r
                                     for r in roles))


# ─── the strike ──────────────────────────────────────────────────────────────
# A swing's blow is timed and not notified, so the bake has to know when the
# clip strikes.  Read off the hand's path forward (cm, one sample per frame):
# the thrust is spent at the first frame after the hand's fastest forward
# frame that the hand reaches at under SPENT of that speed.  On the clips the
# moments were first read off by eye it gives 0.97 s for the stab (0.97) and
# 0.83 s for the chop (0.85): a frame is 0.03 s.
SPENT = 0.25
MIN_TRAVEL_CM = 30.0        # verify/melee_clips.TRAVEL_CM: under it, no swing


def strike_s(forward, fps):
    """When a swing whose hand is ``forward[i]`` cm ahead of the body at frame
    ``i`` strikes (s, to the hundredth).  None when the hand never travels
    MIN_TRAVEL_CM forward: not a swing the blow can be timed to."""
    steps = [b - a for a, b in zip(forward, forward[1:])]
    if not steps or max(forward) - min(forward) < MIN_TRAVEL_CM:
        return None
    peak = max(range(len(steps)), key=lambda i: steps[i])
    for i in range(peak + 1, len(steps)):
        if steps[i] < SPENT * steps[peak]:
            # steps[i] is the move from frame i to frame i + 1.
            return round((i + 1) / float(fps), 2)
    return round((len(forward) - 1) / float(fps), 2)
