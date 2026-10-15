"""verify.tree_chop -- the axe swung at a tree (weapon_component/punch.py's
_author_tree_clip, on the knife's Strike): TreeChopAnim is the worn skin's
UAL2 TreeChopping_Loop, its axe hand is at the trunk when the blow lands, and
in Fx_Slash the clip plays only with the axe's ready pose in hand and the
blow's own sweep meeting an instanced mesh (a tree), ahead of the other clips.
"""

from combat.anim_blueprint import AIM_SLOT
from combat.skin import player_skin
from combat.tuning import COMBAT
from combat.verify.common import BEL, PIN, by_pins, check, load, pin_value
from combat.verify import fx as fxv
from combat import fx_vars as FX
from combat.verify.fixtures import w, wg
from combat.verify.knife import is_knife_play, is_knife_sweep
from combat.verify.punch import _feeders, _feeds, _reach, _title
from combat.weapon_component.knife import AXE_POSE_VAR
from combat.weapon_component.look_vars import HandPose
from combat.weapon_component.vars import TreeChopAnim as TREE_VAR


def is_tree_play(node):
    return any(_title(f) == f"Get {TREE_VAR}" for f in _feeders(node, "Asset"))


def check_tree_clip():
    skin = player_skin()
    clip = w.get_editor_property(TREE_VAR)
    check(f"{TREE_VAR} is the worn skin's chop at a tree (or none without one)",
          (clip is None and skin.tree_chop is None)
          or (clip is not None and clip == load(skin.tree_chop)), f"{clip} vs {skin.tree_chop}")
    if skin.gas:
        check("...on the motion-matching skin, Quaternius UAL2's TreeChopping_Loop "
              "(retarget_to_uefn.py)",
              skin.tree_chop is not None and skin.tree_chop.endswith("UAL2_TreeChopping_Loop"),
              str(skin.tree_chop))
    if clip is None:
        return
    worn = load(skin.mesh)
    check("...in place, on the worn skeleton",
          not clip.get_editor_property("enable_root_motion")
          and clip.get_editor_property("skeleton") == worn.get_editor_property("skeleton"))
    hand = skin.pose_bones["hand_r"]
    t = COMBAT.knife_impact_s
    reach = [_reach(clip, hand, i * 0.05) for i in range(int(clip.get_play_length() / 0.05) + 1)]
    back, out_, at = min(reach), max(reach), _reach(clip, hand, t)
    check("...the axe hand is at the trunk when the blow lands (COMBAT.knife_impact_s): "
          "at least 80% of the way out, and the clip outlasts the blow",
          t < clip.get_play_length() and out_ - back > 30.0
          and at >= back + 0.8 * (out_ - back),
          f"{hand} {at:.0f} cm of {back:.0f}..{out_:.0f}")


def check_tree_play():
    plays = [n for n in by_pins(wg, "Asset", "SlotNodeName") if is_tree_play(n)]
    check("one play of the chop at a tree, in Fx_Slash (verify/fx.py)",
          len(plays) == 1 and fxv.in_fx(FX.SLASH, plays) == plays, str(len(plays)))
    if len(plays) != 1:
        return
    play = plays[0]
    check(f"...into {AIM_SLOT}, once",
          pin_value(play, "SlotNodeName") == AIM_SLOT
          and int(float(pin_value(play, "LoopCount"))) == 1)
    cast = _feeders(play, "execute")
    check("...behind a cast of the sweep's hit component to InstancedStaticMeshComponent",
          len(cast) == 1 and "instancedstaticmesh" in _title(cast[0]).lower().replace(" ", ""),
          str([_title(c) for c in cast]))
    if len(cast) != 1:
        return
    hit = _feeders(cast[0], "execute")
    trace = _feeders(hit[0], "execute") if len(hit) == 1 else []
    check("...of a hit off the blow's own sweep (the knife's radius)",
          len(trace) == 1 and is_knife_sweep(trace[0]), str([_title(t) for t in trace]))
    if len(trace) != 1:
        return
    armed = _feeders(trace[0], "execute")
    asked = ({_title(x) for x in _feeds(BEL.find_input_pin(armed[0], "Condition"))}
             if len(armed) == 1 else set())
    check("...swept only with the axe's ready pose in hand and the clip set",
          {f"Get {HandPose}", f"Get {AXE_POSE_VAR}", f"Get {TREE_VAR}"} <= asked,
          str(sorted(asked)))
    # Every way out of the test (no axe, no hit, no tree) goes on to the
    # axe's or the knife's clip.
    if len(armed) == 1:
        nxt = [PIN.get_owning_node(q) for p in (BEL.find_else_pin(armed[0]),
               BEL.find_else_pin(hit[0])) for q in PIN.list_connected_pins(p)]
        check("...and anything else goes on to the axe's or the knife's swing",
              len(nxt) == 2 and len({n.get_path_name() for n in nxt}) == 1
              and any(is_knife_play(x) for x in _feeds_exec(nxt[0])),
              str([_title(n) for n in nxt]))


def _feeds_exec(branch):
    """The nodes the Branch's two arms run first."""
    return [PIN.get_owning_node(q) for p in (BEL.find_then_pin(branch), BEL.find_else_pin(branch))
            for q in PIN.list_connected_pins(p)]


def run():
    check_tree_clip()
    check_tree_play()
