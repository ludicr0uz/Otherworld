"""verify.crawl_direction -- the crawl goes the way the player moves (P2):
the weapon layers' event graph keeps the pawn's eased velocity in its own
frame and the five weights read off it (combat/crawl_direction.py), the
stance line blends a loop per direction by them (combat/stance_clips.py),
and each direction's clip lies on the ground in place.

Called by verify.stance_clips, which finds the crawl's blend and the lift.
"""

import unreal

from asset_pipeline.ik_follow import off_cm
from asset_pipeline.rig_util import _bone_world
from combat import anim_vars as AN
from combat.body_pose import PRONE_HIPS_CM
from combat.crawl_consts import (
    CRAWL_FULL_CMS, DIRECTION_FIELDS, SLIDE_CMS, STEP_GAIN, TURN_SPEED,
)
from combat.crawl_direction import crawl_sets
from combat.stance_clips import BLEND_CLASS, PLAYER_CLASS, direction_nodes
from combat.verify.common import BEL, PIN, check, graph, load, num_pin
from uebp.pose_share import fed as linked

# The prone capsule's top, and how far under it a crawling head stays.
PRONE_TOP_CM = 80.0
HEAD_CLEAR_CM = 30.0
# The side loop lifts the hips over the arm it shuffles across (6.6 cm on the
# pack's rig); the others hold them as the forward crawl does.
HIPS_RISE_CM = {"prone_left": 9.0, "prone_right": 9.0,
                "prone_fwd_left": 3.0, "prone_fwd_right": 3.0}
# Where each direction's player hangs in the tree: the pins from the crawl's
# blend down, and the variable on each blend passed.
TREE = {
    "forward": ("BAAA", (AN.CrawlMove, AN.CrawlSide, AN.CrawlDiag, AN.CrawlBack)),
    "back": ("BAAB", (AN.CrawlMove, AN.CrawlSide, AN.CrawlDiag, AN.CrawlBack)),
    "left": ("BBA", (AN.CrawlMove, AN.CrawlSide, AN.CrawlRight)),
    "right": ("BBB", (AN.CrawlMove, AN.CrawlSide, AN.CrawlRight)),
    "forward left": ("BABAA", (AN.CrawlMove, AN.CrawlSide, AN.CrawlDiag, AN.CrawlBack,
                               AN.CrawlRight)),
    "forward right": ("BABAB", (AN.CrawlMove, AN.CrawlSide, AN.CrawlDiag, AN.CrawlBack,
                                AN.CrawlRight)),
    "back left": ("BABBA", (AN.CrawlMove, AN.CrawlSide, AN.CrawlDiag, AN.CrawlBack,
                            AN.CrawlRight)),
    "back right": ("BABBB", (AN.CrawlMove, AN.CrawlSide, AN.CrawlDiag, AN.CrawlBack,
                             AN.CrawlRight)),
}


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ") if n else None


def _up(node, pin):
    fed = linked(BEL.find_input_pin(node, pin)) if node else []
    return PIN.get_owning_node(fed[0]) if fed else None


def _cls(node):
    return node.get_class().get_name() if node else None


def _feeds(node, pin):
    seen, stack = [], [BEL.find_input_pin(node, pin)]
    while stack and len(seen) < 24:
        for q in PIN.list_connected_pins(stack.pop()):
            n = PIN.get_owning_node(q)
            if n not in seen and _cls(n) != "K2Node_Event":
                seen.append(n)
                stack.extend(p for p in BEL.list_input_pins(n)
                             if str(PIN.get_pin_name(p)) != "execute")
    return seen


def _reach(crawl, path):
    """(the node at the end of ``path`` from the crawl's blend, the variable
    read by each blend on the way)."""
    node, read = crawl, []
    for pin in path:
        if _cls(node) != BLEND_CLASS:
            return None, read
        read.append((_title(_up(node, "Alpha")) or "").replace("Get ", ""))
        node = _up(node, pin)
    return node, read


def check_direction_tree(skin, crawl, idle_ok):
    check(f"prone: the idle loop still, and the crawl as {AN.CrawlMove} rises",
          _cls(crawl) == BLEND_CLASS and idle_ok
          and _title(_up(crawl, "Alpha")) == f"Get {AN.CrawlMove}",
          f"{_cls(crawl)} by {_title(_up(crawl, 'Alpha'))}")
    for name, (clip, rate) in direction_nodes(skin).items():
        path, variables = TREE[name]
        node, read = _reach(crawl, path)
        seq = node.get_editor_property("node").get_editor_property("sequence") \
            if _cls(node) == PLAYER_CLASS else None
        got = seq.get_path_name().split(".")[0] if seq else None
        played = node.get_editor_property("node").get_editor_property("play_rate") \
            if seq else None
        check(f"crawling {name}: {clip.rsplit('_Prone_', 1)[-1]} at {rate:g}x"
              + (" (in reverse)" if rate < 0 else "")
              + f", chosen by {', '.join(str(v) for v in variables[1:])}; the slide left "
              f"is {SLIDE_CMS[name]:g} cm/s",
              got == clip and played is not None and abs(played - rate) < 1e-6
              and read == [str(v) for v in variables],
              f"{got} @ {played} by {read}")
    clips = [c for c, _r in direction_nodes(skin).values()]
    check("...eight directions, and only forward and back play the forward loop",
          len(direction_nodes(skin)) == 8 and clips.count(skin.prone_crawl) == 2
          and all(clips.count(getattr(skin, f)) == (1 if "fwd" not in f else 2)
                  for f in DIRECTION_FIELDS), str(sorted(set(clips))))
    _check_events(skin)


def _check_events(skin):
    events = graph(load(skin.anim_bp))
    sets = {_title(n).replace("Set ", ""): n for n in crawl_sets(events)}
    check(f"the event graph writes each of {', '.join(str(v) for v in AN.CRAWL)} once",
          sorted(sets) == sorted(str(v) for v in AN.CRAWL)
          and len(crawl_sets(events)) == len(AN.CRAWL), str(sorted(sets)))
    if sorted(sets) != sorted(str(v) for v in AN.CRAWL):
        return
    for var, axis in ((AN.CrawlAhead, "GetActorForwardVector"),
                      (AN.CrawlAcross, "GetActorRightVector")):
        feeds = _feeds(sets[str(var)], str(var))
        titles = {_title(n) for n in feeds}
        ease = [n for n in feeds if _title(n) == "FInterpTo"]
        check(f"{var}: the pawn's velocity along its own "
              f"{'forward' if var is AN.CrawlAhead else 'right'}, eased from {var} at "
              f"{TURN_SPEED:g}/s by the update's own delta time (what every machine has: "
              "no replicated variable, no RPC)",
              {"GetVelocity", axis, "TryGetPawnOwner", f"Get {var}"} <= titles
              and len(ease) == 1 and num_pin(ease[0], "InterpSpeed") == TURN_SPEED
              and _cls(_up(ease[0], "DeltaTime")) == "K2Node_Event", str(sorted(titles)))
    both = {f"Get {AN.CrawlAhead}", f"Get {AN.CrawlAcross}"}
    for var, need in ((AN.CrawlMove, {"Hypotenuse"}), (AN.CrawlDiag, {"Atan2 (Degrees)"}),
                      (AN.CrawlSide, {"Atan2 (Degrees)"})):
        titles = {_title(n) for n in _feeds(sets[str(var)], str(var))}
        check(f"{var} is read off the eased pair, clamped to 0..1",
              both | need <= titles and _title(_up(sets[str(var)], str(var))) == "Clamp (Float)"
              and "GetVelocity" not in titles, str(sorted(titles)))
    scale = _up(_up(sets[str(AN.CrawlMove)], str(AN.CrawlMove)), "Value")
    check(f"...{AN.CrawlMove} full at {CRAWL_FULL_CMS:g} cm/s",
          scale is not None and abs(num_pin(scale, "B") - 1.0 / CRAWL_FULL_CMS) < 1e-6)
    for var, source, gain in ((AN.CrawlBack, AN.CrawlAhead, -STEP_GAIN),
                              (AN.CrawlRight, AN.CrawlAcross, STEP_GAIN)):
        clamp = _up(sets[str(var)], str(var))
        scale = _up(clamp, "Value")
        check(f"{var} is a step: clamp({source} x {gain:g}, 0, 1)",
              _title(clamp) == "Clamp (Float)" and scale is not None
              and num_pin(scale, "B") == gain and _title(_up(scale, "A")) == f"Get {source}",
              f"{_title(clamp)} <- {_title(scale)} <- {_title(_up(scale, 'A')) if scale else None}")


def check_direction_clips(skin, lying, lift):
    """Each side and diagonal loop lies on the ground by the prone's one lift."""
    hips = skin.pose_bones["hips"]
    for field in DIRECTION_FIELDS:
        clip = load(getattr(skin, field))
        length = clip.get_editor_property("sequence_length")
        poses = [{b: _bone_world(clip, b, length * i / 32) + unreal.Vector(0.0, 0.0, lift)
                  for b in lying + ["root"]} for i in range(33)]
        low = min(p[k].z for p in poses for k in lying)
        top = max(p["Head"].z for p in poses)
        hz = [p[hips].z for p in poses]
        travel = max(max(getattr(p[k], a) for p in poses) - min(getattr(p[k], a) for p in poses)
                     for k in ("root", hips) for a in "xy")
        rise = HIPS_RISE_CM[field]
        check(f"{field}: no hand, knee or foot is under the ground, the hips lie "
              f"{PRONE_HIPS_CM:g} cm up and rise no more than {rise:g}, the head stays "
              f"{HEAD_CLEAR_CM:g} cm under the capsule's top",
              low > 0.0 and min(hz) > PRONE_HIPS_CM - 2.0 and max(hz) < PRONE_HIPS_CM + rise
              and top < PRONE_TOP_CM - HEAD_CLEAR_CM,
              f"hips {min(hz):.1f}..{max(hz):.1f}, lowest {low:.1f}, head {top:.1f}")
        check(f"{field}: in place (root and hips travel under 0.5 cm), no root motion, "
              "its IK feet on its feet",
              travel < 0.5 and not clip.get_editor_property("enable_root_motion")
              and off_cm(clip) < 0.5, f"{travel:.2f} cm, IK feet {off_cm(clip):.2f} cm off")
