"""verify.reload_clip -- the reload's clip (weapon_component/reload_clip.py):
the AKM and the sniper change their magazine in Lyra's rifle reload, the
pistol and the SMG in its pistol reload, each on the player's skeleton and
at the rate that fits its gun's reload, played by Fx_Reload into the
upper-body slot on every machine that plays the clack; the keep-alive and
the equip leave it there and the ready pose takes over at its end; the left
hand's hold down the sights lets go for it.
"""

import unreal

from asset_pipeline import lyra_paths as LYRA
from combat import item_vars as IV
from combat.anim_blueprint import AIM_SLOT
from combat.fx_vars import RELOAD, fx_event
from combat.finger_pose import clip_for
from combat.gun_rows import gun_row
from combat.reload_tuning import (
    RELOAD_BLEND_IN_S, RELOAD_BLEND_OUT_S, RELOAD_CLIP_GUNS, RELOAD_HANDOVER_S)
from combat.skin import player_skin
from combat.verify.common import BEL, by_pins, cdo, check, in_pins, load, num_pin, pin_value
from combat.verify.fixtures import w, wg
from combat.verify.fx import in_fx
from combat.verify.interact import _exec_from, _title
from combat.verify.punch import _feeds
from combat.weapon_component import vars as WV
from combat.weapon_component.look_vars import HandPose
from combat.weapon_specs import _weapon_specs

ANIM = unreal.AnimationLibrary
ROOT_MOTION = "enable_root_motion"
# How far the left hand has to leave where the clip starts it, in the right
# hand's frame: a magazine change, not a pose. Measured 100 cm in the
# rifle's (it reaches for the pouch 0.6 s in, 87 cm from the right hand).
HAND_TRAVEL_CM = 15.0
# The skin's clips and the Lyra clip each is.
SOURCES = {"reload_rifle": LYRA.RELOAD_RIFLE, "reload_pistol": LYRA.RELOAD_PISTOL}


def _path(asset):
    return asset.get_path_name().split(".")[0] if asset else None


def _reads_clip(node):
    return any(_title(f) == f"Get {WV.ReloadAnim}"
               for f in _feeds(BEL.find_input_pin(node, "Asset")))


def is_reload_play(node):
    """The play of the reload's clip: a play (it has a rate) whose Asset is
    ReloadAnim. The readers of the slot take it through an Asset pin too."""
    return "InPlayRate" in in_pins(node) and _reads_clip(node)


def _bone(clip, bone, t):
    at = unreal.Transform()
    for b in ANIM.find_bone_path_to_root(clip, bone):
        at = at * ANIM.get_bone_pose_for_time(clip, b, t, False)
    return at


def hand_travel(clip, skin, steps=22):
    """The furthest the left hand gets from where the clip starts it, in the
    right hand's frame (cm)."""
    left, right = skin.pose_bones["hand_l"], skin.pose_bones["hand_r"]
    length = clip.get_play_length()

    def at(t):
        return unreal.MathLibrary.inverse_transform_location(
            _bone(clip, right, t), _bone(clip, left, t).translation)
    first = at(0.0)
    return max((at(length * i / steps) - first).length() for i in range(1, steps + 1))


def _rows():
    """What the component's three arrays should hold: (gun, ready pose,
    clip, reload seconds) for each gun whose clip the worn skin has."""
    skin = player_skin()
    return [(name, clip_for(name), getattr(skin, field), gun_row(display)["reload_s"])
            for name, (display, field) in RELOAD_CLIP_GUNS.items() if getattr(skin, field)]


def check_clip():
    """The clips themselves, the guns each is for and its rate."""
    skin = player_skin()
    rows = _rows()
    poses = [_path(c) for c in w.get_editor_property(str(WV.ReloadFor))]
    clips = [_path(c) for c in w.get_editor_property(str(WV.ReloadClips))]
    rates = [float(r) for r in w.get_editor_property(str(WV.ReloadRates))]
    check(f"the guns that reload with a clip are {', '.join(RELOAD_CLIP_GUNS)}, each by "
          f"its own ready clip ({WV.ReloadFor}; none on a skin without the clips)",
          poses == [r[1] for r in rows] and len(set(poses)) == len(poses), str(poses))
    guns = {sp["path"].rsplit("/", 1)[1]: _path(cdo(load(sp["path"])).get_editor_property(
        str(IV.AimPose))) for sp in _weapon_specs()}
    wrong = sorted(name for name, pose in guns.items()
                   if (pose in poses) != (name in [r[0] for r in rows])
                   or (pose in poses and poses.index(pose) != [r[0] for r in rows].index(name)))
    check("...which is what each of those guns is held in, and no other gun "
          "(the shotgun reloads with its sound alone)", not wrong, f"wrong: {wrong}")
    check(f"...each with its clip beside it ({WV.ReloadClips}: the rifle's for the AKM "
          "and the sniper, the pistol's for the pistol and the SMG)",
          clips == [r[2] for r in rows], str(clips))
    check(f"{WV.ReloadAnim} and {WV.ReloadPose} are the play's to write: none until a "
          "reload",
          w.get_editor_property(str(WV.ReloadAnim)) is None
          and w.get_editor_property(str(WV.ReloadPose)) is None)
    if clips != [r[2] for r in rows]:
        return
    fits = [f"{name} {rate:.2f} for {load(clip).get_play_length() / secs:.2f}"
            for (name, _pose, clip, secs), rate in zip(rows, rates)
            if abs(rate - load(clip).get_play_length() / secs) > 0.005]
    check(f"...and the rate that ends the clip with the gun's reload ({WV.ReloadRates}: "
          "the clip's length over the row's reload time)",
          len(rates) == len(rows) and not fits, f"{[round(r, 2) for r in rates]}; {fits}")
    for field, source_path in SOURCES.items():
        path = getattr(skin, field)
        if not path:
            continue
        clip, source = load(path), load(source_path)
        label = source_path.rsplit("/", 1)[1]
        check(f"{field} is Lyra's {label} on the player's skeleton, as long as Lyra's, "
              "and in place (a slot play with root motion roots the player)",
              path == LYRA.uefn_clip(source_path)
              and clip.get_editor_property("skeleton")
              == load(skin.mesh).get_editor_property("skeleton")
              and abs(clip.get_play_length() - source.get_play_length()) < 0.05
              and not clip.get_editor_property(ROOT_MOTION),
              f"{clip.get_play_length():.2f} s against {source.get_play_length():.2f}")
        travel = hand_travel(clip, skin)
        check(f"...in which the left hand leaves the gun: over {HAND_TRAVEL_CM:g} cm from "
              "where the clip starts it, in the right hand's frame",
              travel > HAND_TRAVEL_CM, f"{travel:.1f} cm")
    shortest = min((load(clip).get_play_length() / rate
                    for (_n, _p, clip, _s), rate in zip(rows, rates)), default=None)
    check(f"the ready pose takes over {RELOAD_HANDOVER_S:g} s before a clip's end: "
          f"before its own blend out ({RELOAD_BLEND_OUT_S:g} s) begins, and under half "
          "of the shortest reload",
          shortest is None or RELOAD_BLEND_OUT_S < RELOAD_HANDOVER_S < shortest / 2,
          f"the shortest lasts {shortest}")


def check_play():
    """Fx_Reload plays it, behind a clip and a gun that reloads with it."""
    plays = [n for n in by_pins(wg, "Asset", "SlotNodeName", "InPlayRate") if _reads_clip(n)]
    fx_plays = in_fx(RELOAD, plays)
    check(f"the clip is played once, in {fx_event(RELOAD)} (so by the owner as its "
          f"prediction and by everyone else at the server's word), into {AIM_SLOT}, "
          f"whole, at its gun's rate (the row of {WV.ReloadRates})",
          len(plays) == 1 and fx_plays == plays
          and pin_value(plays[0], "SlotNodeName") == AIM_SLOT
          and f"Get {WV.ReloadRates}" in {
              _title(f) for f in _feeds(BEL.find_input_pin(plays[0], "InPlayRate"))}
          and num_pin(plays[0], "LoopCount") in (None, 1.0)
          and num_pin(plays[0], "InTimeToStartMontageAt") in (None, 0.0)
          and num_pin(plays[0], "BlendInTime") == RELOAD_BLEND_IN_S
          and num_pin(plays[0], "BlendOutTime") == RELOAD_BLEND_OUT_S,
          f"{len(plays)} play(s), {len(fx_plays)} in the cosmetic")
    if len(plays) != 1:
        return
    # Before the play, the two it reads back: the clip chosen and its pose.
    gates, wrote = _exec_from(plays[0]), []
    while len(gates) == 1 and _title(gates[0][0]).startswith("Set ") and len(wrote) < 2:
        wrote.append(gates[0][0])
        gates = _exec_from(gates[0][0])
    fed = {_title(n): {_title(f) for f in _feeds(BEL.find_input_pin(
        n, _title(n).split(" ", 1)[1]))} for n in wrote}
    check(f"the play writes what the slot's readers ask for first: {WV.ReloadAnim}, the "
          f"row's clip of {WV.ReloadClips}, and {WV.ReloadPose}, the {HandPose} it is for",
          sorted(fed) == [f"Set {WV.ReloadAnim}", f"Set {WV.ReloadPose}"]
          and f"Get {WV.ReloadClips}" in fed[f"Set {WV.ReloadAnim}"]
          and f"Get {HandPose}" in fed[f"Set {WV.ReloadPose}"],
          str({k: sorted(v) for k, v in fed.items()}))
    asked = ({_title(f) for f in _feeds(BEL.find_input_pin(gates[0][0], "Condition"))}
             if len(gates) == 1 and _title(gates[0][0]) == "Branch" else set())
    check(f"...only for a gun that reloads with a clip: a Branch on where {HandPose} is "
          f"in {WV.ReloadFor} ({HandPose}, which every machine's copy has, and not "
          "Held), with the rows read behind it",
          len(gates) == 1 and gates[0][1] == "then"
          and {f"Get {WV.ReloadFor}", f"Get {HandPose}"} <= asked
          and not {"Get Held", f"Get {WV.ReloadClips}", f"Get {WV.ReloadRates}"} & asked,
          str(sorted(asked)))
    ends = [n for n in wg if _title(n) == f"Set {WV.ReloadClipEnds}"]
    fed = ({_title(f) for f in _feeds(BEL.find_input_pin(ends[0], str(WV.ReloadClipEnds)))}
           if len(ends) == 1 else set())
    check(f"...and {WV.ReloadClipEnds} is stamped right after it: now + the clip's "
          f"length over its rate - {RELOAD_HANDOVER_S:g} s",
          len(ends) == 1 and _exec_from(ends[0]) == [(plays[0], "then")]
          and {f"Get {WV.ReloadAnim}", f"Get {WV.ReloadRates}"} <= fed
          and any("Play Length" in t.replace("Get", "Get ").replace("  ", " ")
                  or "PlayLength" in t.replace(" ", "") for t in fed),
          str(sorted(fed)))
    sounds = [n for n in in_fx(RELOAD, by_pins(wg, "Sound", "Location"))]
    check("the clack still plays whether the clip did or not (both arms of the "
          "clip's Branch reach it)",
          len(sounds) == 1 and _reaches(gates[0][0], "else", sounds[0])
          and _reaches(ends[0] if ends else None, "then", sounds[0]),
          f"{len(sounds)} sound(s)")


def _reaches(node, pin, target, limit=6):
    """Does ``node``'s exec output ``pin`` lead to ``target`` within a few
    nodes?"""
    if node is None:
        return False
    back = [(target, None)]
    for _ in range(limit):
        back = [(n, p) for b, _p in back for n, p in _exec_from(b)]
        if any(n == node and p == pin for n, p in back):
            return True
    return False


def check_slot_kept():
    """The keep-alive and the equip leave the clip in the slot, and the
    keep-alive hands over at its end."""
    readers = [n for n in by_pins(wg, "Asset", "SlotNodeName")
               if "InPlayRate" not in in_pins(n) and _reads_clip(n)]
    poses = [n for n in by_pins(wg, "Asset", "SlotNodeName", "InPlayRate")
             if [_title(f) for f in _feeds(BEL.find_input_pin(n, "Asset"), 3)]
             == [f"Get {HandPose}"]]
    asked = []
    for play in poses:
        seen, at = set(), [play]
        for _ in range(4):
            at = [n for b in at for n, _p in _exec_from(b)]
            for n in at:
                if _title(n) == "Branch":
                    seen |= {f.get_path_name()
                             for f in _feeds(BEL.find_input_pin(n, "Condition"))}
        asked.append(sum(1 for r in readers if r.get_path_name() in seen))
    check("the ready pose's two plays (the equip, the keep-alive) each ask whether "
          "the reload's clip is in the slot first: the equip once (held), the "
          "keep-alive twice (held: leave it; its time up: take over)",
          len(poses) == 2 and sorted(asked) == [1, 2], f"{len(poses)} play(s), asks {asked}")
    same = [n for n in by_pins(wg, "A", "B")
            if {_title(f) for f in _feeds(BEL.find_input_pin(n, "A"), 3)
                | _feeds(BEL.find_input_pin(n, "B"), 3)}
            == {f"Get {HandPose}", f"Get {WV.ReloadPose}"}]
    check(f"...the equip only while {HandPose} is still {WV.ReloadPose}, the pose the "
          "clip was played for: another gun taken out cuts it, one with a reload "
          "clip of its own too", len(same) == 1, f"{len(same)} comparison(s)")
    timed = [n for n in wg if _title(n) == f"Get {WV.ReloadClipEnds}"]
    check(f"...each against {WV.ReloadClipEnds}, as the left hand's hold does",
          len(readers) == 4 and len(timed) == 4,
          f"{len(readers)} reader(s) of the slot, {len(timed)} of the time")
    posed = [n for n in by_pins(wg, "Asset", "SlotNodeName")
             if "InPlayRate" not in in_pins(n)
             and [_title(f) for f in _feeds(BEL.find_input_pin(n, "Asset"), 3)]
             == [f"Get {HandPose}"]]
    check("the take-over is one frame's: it asks whether the ready pose is in the "
          "slot already (the clip is still there while the pose blends it out)",
          len(posed) == 1, f"{len(posed)} reader(s) of the slot for {HandPose}")
    eases = [n for n in wg if _title(n) == f"Set {WV.ReloadHand}"]
    fed = ({_title(f) for f in _feeds(BEL.find_input_pin(eases[0], str(WV.ReloadHand)))}
           if len(eases) == 1 else set())
    check(f"{WV.ReloadHand} is eased once a frame towards the clip being held in the "
          "slot (verify/support_hand.py has what it weights)",
          len(eases) == 1 and {f"Get {WV.ReloadHand}", f"Get {WV.ReloadAnim}",
                               f"Get {WV.ReloadClipEnds}"} <= fed
          and any("InterpTo" in t.replace(" ", "") for t in fed), str(sorted(fed)))


def run():
    check_clip()
    check_play()
    check_slot_kept()
