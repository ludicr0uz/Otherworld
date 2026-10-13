"""The reload's clip: the magazine change of the AKM and the sniper (Lyra's
MM_Rifle_Reload, PlayerSkin.reload_rifle) and of the pistol and the SMG (its
MM_Pistol_Reload, PlayerSkin.reload_pistol), each retargeted onto the
player's skeleton by asset_pipeline/import_lyra.py; reload_tuning.py has the
guns and the numbers.

Who plays it: every machine that plays the reload's clack, since it is the
start of Fx_Reload's body (shot.py): the owner as its prediction, everyone
else at the server's word. Which gun: the one whose ready pose is in hand,
HandPose found in ReloadFor (the ready clips of reload_tuning.
RELOAD_CLIP_GUNS), and not Held's class, because HandPose is on every
machine's copy (look.py) and Held is the player's item only where the keys
are. Where it is found is the row: ReloadClips has that gun's clip and
ReloadRates the rate that fits the clip to the gun's reload time
(reload_defaults, at the build). A skin with no clip (the arrays are
empty), or any other gun, plays nothing: the reload is its sound and its
pause.

The play writes ReloadAnim (the clip it chose) and ReloadPose (the ready
pose it chose it for). It plays into the upper-body slot, where the ready
pose is, so three things ask about it:

    holding(...)   ReloadAnim is in the slot and its time is not up: the
                   ready pose's keep-alive (ready_pose.py) and the equip
                   (inventory.py, which the reload's own raise of a lowered
                   gun runs a frame later) leave the slot alone. The equip
                   asks only while HandPose is still ReloadPose (same_gun),
                   so taking another gun out cuts the clip, a gun with a
                   reload clip of its own too.
    ending(...)    the clip is in the slot and its time is up
                   (ReloadClipEnds, RELOAD_HANDOVER_S before its end): the
                   keep-alive takes that for a quiet slot and plays the ready
                   pose, which blends the clip out against itself.
    hand_weight    the left hand's hold on the gun down the sights
                   (support_hand.py) times 1 - ReloadHand, eased up while the
                   clip is held: the hand goes to the magazine.

A flinch stops the clip, as it stops the ready pose (one montage group:
ready_pose.py); the keep-alive then finds a quiet slot and no clip, and puts
the ready pose back. The rounds have moved by then: the reload is the native
ReloadNow's, on the press.
"""

from combat.anim_blueprint import AIM_SLOT
from combat.finger_pose import clip_for
from combat.gun_rows import gun_row
from combat.reload_tuning import (
    RELOAD_BLEND_IN_S, RELOAD_BLEND_OUT_S, RELOAD_CLIP_GUNS, RELOAD_HAND_SPEED,
    RELOAD_HANDOVER_S, reload_rate)
from combat.skin import player_skin
from combat.weapon_component.look_vars import HandPose
from combat.weapon_component.slot_nodes import op
from combat.weapon_component import vars as WV
from uebp.g import _G
from uebp.graph import _connect, _must_load, _node, _pin, _set, out, then
from uebp.nodes.actor import FN_ANIM_INSTANCE, FN_IS_PLAYING_SLOT, FN_PLAY_LENGTH, FN_PLAY_SLOT
from uebp.nodes.array import FN_ARR_FIND, FN_ARR_GET
from uebp.nodes.math import (
    FN_ADD_FF, FN_AND, FN_BOOL_TO_FLOAT, FN_DIV_FF, FN_EQ_OO, FN_GE_II, FN_INTERP_FF,
    FN_LESS_FF, FN_MUL_FF, FN_NOT, FN_SUB_FF)
from uebp.nodes.system import FN_DELTA_SECONDS, FN_TIME_SECONDS


def _get(ed, var, keep):
    return out(keep(ed.add_get_member_variable_node(var)), var)


def _both(ed, a, b, keep):
    n = keep(_node(ed, FN_AND))
    _connect(a, _pin(n, "A"))
    _connect(b, _pin(n, "B"))
    return out(n)


def _in_slot(ed, anim_out, keep):
    playing = keep(_node(ed, FN_IS_PLAYING_SLOT))
    _connect(anim_out, _pin(playing, "self"))
    _connect(_get(ed, WV.ReloadAnim, keep), _pin(playing, "Asset"))
    _set(playing, "SlotNodeName", AIM_SLOT)
    return out(playing)


def _before_end(ed, keep):
    early = keep(_node(ed, FN_LESS_FF))
    _connect(out(keep(_node(ed, FN_TIME_SECONDS))), _pin(early, "A"))
    _connect(_get(ed, WV.ReloadClipEnds, keep), _pin(early, "B"))
    return out(early)


def holding(ed, anim_out, keep=lambda n: n):
    """Is the reload's clip in the upper-body slot with its time not up? A
    bool pin, off the anim instance pin given; ``keep`` collects the nodes."""
    return _both(ed, _in_slot(ed, anim_out, keep), _before_end(ed, keep), keep)


def ending(ed, anim_out, pose_pin, keep=lambda n: n):
    """Is the reload's clip in the slot with its time up and the ready pose
    (``pose_pin``) not yet there: the pose's to take over? A bool pin.

    The last term makes it one frame's answer. The clip is still in the slot
    while the pose blends it out, and a pose played again on each of those
    frames starts from nothing every time: the slot emptied for the length of
    the blend, and the arms fell to the locomotion's (the probe saw it)."""
    late = keep(_node(ed, FN_NOT))
    _connect(_before_end(ed, keep), _pin(late, "A"))
    posed = keep(_node(ed, FN_IS_PLAYING_SLOT))
    _connect(anim_out, _pin(posed, "self"))
    _connect(pose_pin, _pin(posed, "Asset"))
    _set(posed, "SlotNodeName", AIM_SLOT)
    not_posed = keep(_node(ed, FN_NOT))
    _connect(out(posed), _pin(not_posed, "A"))
    due = _both(ed, _in_slot(ed, anim_out, keep), out(late), keep)
    return _both(ed, due, out(not_posed), keep)


def reload_defaults():
    """{variable: default} for ReloadFor, ReloadClips and ReloadRates: a row
    for each gun of RELOAD_CLIP_GUNS whose clip the worn skin has, its rate
    the one that ends the clip with the gun's reload (its row's reload_s)."""
    skin = player_skin()
    poses, clips, rates = [], [], []
    for name, (display, field) in RELOAD_CLIP_GUNS.items():
        path = getattr(skin, field)
        if not path:
            continue
        clip = _must_load(path)
        poses.append(_must_load(clip_for(name)))
        clips.append(clip)
        rates.append(reload_rate(clip.get_play_length(), gun_row(display)["reload_s"]))
    return {WV.ReloadFor: poses, WV.ReloadClips: clips, WV.ReloadRates: rates}


def _row(ed, keep=lambda n: n):
    """Where the ready pose in hand is in ReloadFor (-1: no clip). An int pin."""
    at = keep(_node(ed, FN_ARR_FIND))
    _connect(_get(ed, WV.ReloadFor, keep), _pin(at, "TargetArray"))
    _connect(_get(ed, HandPose, keep), _pin(at, "ItemToFind"))
    return out(at)


def same_gun(ed, keep=lambda n: n):
    """Is the ready pose in hand the one the last reload's clip was played
    for? A bool pin."""
    same = keep(_node(ed, FN_EQ_OO))
    _connect(_get(ed, HandPose, keep), _pin(same, "A"))
    _connect(_get(ed, WV.ReloadPose, keep), _pin(same, "B"))
    return out(same)


def author_reload_clip(g, exec_in):
    """The gun's clip into the upper-body slot at its rate, and ReloadAnim,
    ReloadPose and ReloadClipEnds, behind a gun that reloads with one.
    Returns the exec pins after, played or not: the start of Fx_Reload's
    body."""
    ed = g.ed
    mine = g.call(FN_GE_II, A=_row(ed, g.keep))
    _set(mine, "B", 0)
    plays, silent = g.branch(out(mine), [exec_in])
    # Read behind the Branch only: Array_Get at -1 is a runtime error.
    clip = g.call(FN_ARR_GET, TargetArray=g.get(WV.ReloadClips), Index=_row(ed, g.keep))
    chosen = g.put(WV.ReloadAnim, out(clip, "Item"), [plays])
    posed = g.put(WV.ReloadPose, g.get(HandPose), [chosen])
    rate = g.call(FN_ARR_GET, TargetArray=g.get(WV.ReloadRates), Index=_row(ed, g.keep))
    anim = g.call(FN_ANIM_INSTANCE, self=g.get(WV.OwnerMesh))
    play = g.call(FN_PLAY_SLOT, [posed], self=out(anim), Asset=g.get(WV.ReloadAnim),
                  InPlayRate=out(rate, "Item"))
    _set(play, "SlotNodeName", AIM_SLOT)
    _set(play, "BlendInTime", RELOAD_BLEND_IN_S)
    _set(play, "BlendOutTime", RELOAD_BLEND_OUT_S)
    _set(play, "LoopCount", 1)
    length = out(g.call(FN_PLAY_LENGTH, self=g.get(WV.ReloadAnim)))
    lasts = op(g, FN_DIV_FF, length, out(rate, "Item"))
    left = g.call(FN_SUB_FF, A=lasts)
    _set(left, "B", RELOAD_HANDOVER_S)
    until = op(g, FN_ADD_FF, out(g.call(FN_TIME_SECONDS)), out(left))
    timed = g.put(WV.ReloadClipEnds, until, [then(play)])
    return [timed, silent]


def author_hand_weight(ed, sight_blend, exec_in, keep=lambda n: n):
    """ReloadHand eased towards holding(), and SightBlend x (1 - ReloadHand).
    Returns (the exec pin after, the weight's pin): support_hand.py's."""
    g = _G(ed)
    anim = g.call(FN_ANIM_INSTANCE, self=g.get(WV.OwnerMesh))
    target = g.call(FN_BOOL_TO_FLOAT, InBool=holding(ed, out(anim), g.keep))
    step = g.call(FN_INTERP_FF, Current=g.get(WV.ReloadHand), Target=out(target),
                  DeltaTime=out(g.call(FN_DELTA_SECONDS)))
    _set(step, "InterpSpeed", RELOAD_HAND_SPEED)
    eased = g.put(WV.ReloadHand, out(step), [exec_in])
    free = g.call(FN_SUB_FF, B=g.get(WV.ReloadHand))
    _set(free, "A", 1.0)
    weight = op(g, FN_MUL_FF, sight_blend, out(free))
    for n in g.made:
        keep(n)
    return eased, weight
