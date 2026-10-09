"""What a pellet shows: PelletFlew, the native base's word of each pellet it
flew (OtherworldWeaponComponentBase::FirePellets, which traced it, read the
hit zone and handed a body its damage). On a body: blood, the headshot's
stamp and the debug-mode damage readout. On anything without health: the
surface's chips and dust (surface_impact.py). And Fx_PelletHit, the burst
itself, on every machine with a screen.
"""

from combat.blood import (
    BLOOD_REFERENCE_DAMAGE, BLOOD_SCALE_MAX, BLOOD_SCALE_MIN,
)
from combat.game_state import DAMAGE_TEXT_COLOR, DEBUG_MODE_VAR, TRACE_DEBUG_SECONDS
from uebp.graph import _connect, _node, _palette, _pin, _set, out, then
from combat.hit_zones import HIT_BONE_VAR, HIT_POINT_VAR
from combat.paths import ITEM_CLASS_PATH
from combat.tuning import COMBAT
from combat.fx_vars import BLOOD_PARAM, PELLET_HIT, PELLET_HIT_PARAMS, SCALE_PARAM, fx_event
from combat.weapon_component import fx, shot_hits
from combat.weapon_component import vars as WV
from combat.weapon_component.headshot import _author_headshot
from combat.weapon_component.surface_impact import _author_surface_impact
from combat.weapon_component.tracer import _author_tracer
from uebp import net
from uebp.g import _G
from uebp.nodes.math import FN_CLAMP, FN_DIV_FF
from uebp.nodes.system import FN_CONCAT, FN_DRAW_STRING, FN_FLOAT_TO_STR
from uebp.nodes.weapon import NODE_EVENT_PELLET_FLEW
from combat import item_vars as IV


def _author_pellet_hit(g, exec_in, event):
    """The body of Fx_PelletHit: at the event's point and normal, sized by
    its Scale, the blood (Blood) or the surface's chips. The one transform
    serves both bursts."""
    where = fx.point_transform(g, event, out(event, SCALE_PARAM))
    bleeds, chips = g.branch(out(event, BLOOD_PARAM), [exec_in])
    fx.spawn_blood(g, where, [bleeds])
    for n in _author_surface_impact(g.ed, where, chips):
        g.keep(n)


def author_pellet_fx(ed):
    """Fx_PelletHit, the cosmetic itself, and the batch that tells a shot's
    (shot_hits.py). Before PelletFlew, which notes into it."""
    g = _G(ed)
    event = g.keep(net.custom_event(ed, fx_event(PELLET_HIT), PELLET_HIT_PARAMS))
    _author_pellet_hit(g, then(event), event)
    ed.add_comment_to_nodes(
        f"{fx_event(PELLET_HIT)} (impact.py): the cosmetic itself, once. Called once per "
        "impact by Multicast_ShotHits, where this copy has a screen (shot_hits.py).",
        g.made)
    shot_hits.author_shot_hits(ed)


def author_pellet_flew(ed):
    """PelletFlew, the native base's word of one pellet (FirePellets, C++),
    and what this graph shows of it. On the server, which traced it.

    The capsule says whether a character was struck and its physics bodies
    where (ShotTrace); the base read the zone off the TARGET's own tables
    and handed the body its damage (TakeHit) before it raised this. So the
    event says which of three things the pellet did:

        bHurt      a body took Damage: blood out of the wound, the headshot's
                   stamp if bHead, the debug readout
        bScenery   a thing without health: chips and dust
        neither    it crossed a character's capsule and struck none of its
                   bodies. It passed the model by: nothing

    The blood and the chips are told to every machine with a screen: noted
    here, pellet by pellet, and told once after the last (Multicast_ShotHits,
    shot_hits.py). The server has no screen, and the shooter predicted no hit.
    HitPoint and HitBone keep the last pellet's, as they did when the zone
    was traced here: where a burst goes, and the bone a probe reads.
    """
    g = _G(ed, ITEM_CLASS_PATH)
    flew = g.keep(_palette(ed, NODE_EVENT_PELLET_FLEW))
    # The tracer, in debug mode only (tracer.py): drawn for a miss too.
    drawn, after_tracer = _author_tracer(ed, flew)
    stopped, _flew_on = g.branch(out(flew, "bStopped"), after_tracer)
    flow = g.put(HIT_POINT_VAR, out(flew, "Point"), [stopped])
    flow = g.put(HIT_BONE_VAR, out(flew, "Bone"), [flow])
    hurt, spared = g.branch(out(flew, "bHurt"), [flow])
    scenery, _passed = g.branch(out(flew, "bScenery"), [spared])

    # How big the spray is, as a clamped ratio of the round's damage to a
    # reference one. Spawn *scale* rather than a parameter on the splash,
    # because the droplet solver works in the actor's own space: scaling the
    # actor scales launch distance and droplet size together, which is the
    # single number that separates a 9 mm from a slug at contact range. A
    # shotgun pays eight of these at once, which is why one pellet is under 1x.
    ratio = g.call(FN_DIV_FF, A=g.iget(g.get(WV.Held), IV.Damage))
    _set(ratio, "B", BLOOD_REFERENCE_DAMAGE)
    spray = g.call(FN_CLAMP, Value=out(ratio))
    _set(spray, "Min", BLOOD_SCALE_MIN)
    _set(spray, "Max", BLOOD_SCALE_MAX)
    # The splash's +X goes down the surface normal (BP_BloodSplash throws its
    # cone along its own forward, so the spray comes *out of* the wound), and
    # so do the chips: Fx_PelletHit makes the one transform from these.
    normal = out(flew, "Normal")
    bled = shot_hits.note(g, [hurt], g.get(HIT_POINT_VAR), normal, out(spray), blood=True)
    shot_hits.note(g, [scenery], g.get(HIT_POINT_VAR), normal, out(spray), blood=False)

    # A pellet in the head says so to the HUD: the X round the reticle.
    headed, head_nodes = _author_headshot(ed, out(flew, "bHead"), [bled])
    shown = _author_damage_readout(ed, flew, headed)

    ed.add_comment_to_nodes(
        "PelletFlew (impact.py): one pellet of a shot, flown by the native base "
        "(FirePellets). On a body it already took the round's damage times its zone "
        "(TakeHit, on the server): blood out of the wound, noted for the shot's one "
        "Multicast_ShotHits (Blood). On a thing without health: chips and dust where a "
        "body would bleed (the same event, Blood false), at the impact point, along the "
        "surface normal, sized by the round's damage. Through a capsule and past the "
        "body: nothing.",
        g.made + drawn)
    ed.add_comment_to_nodes(
        f"Hit boxes: the bone the pellet struck picked the multiplier off the TARGET's "
        f"health component -- head {COMBAT.head_multiplier}x, arms and legs "
        f"{COMBAT.limb_multiplier}x, anything else 1x; one in the head stamps "
        f"HeadshotTime, the HUD's X round the reticle.", head_nodes)
    ed.add_comment_to_nodes(
        "Debug mode only: the damage this pellet actually did, and the zone "
        "multiplier behind it, drawn where it landed for as long as the tracer.",
        shown)


def _author_damage_readout(ed, flew, exec_in):
    """In debug mode, write "<damage> (x<multiplier>)" where the pellet
    stopped. ``flew`` is the PelletFlew event node, whose Damage already
    holds the zone's Worth.

    Behind the same cached DebugMode the tracer branches on, and for the same
    TRACE_DEBUG_SECONDS, so the number appears at the end of the line that
    explains it. DrawDebugString rather than anything on the HUD: it is world
    space, needs no projection, and is compiled out of shipping builds like
    DrawDebugLine is.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    seen = keep(ed.add_get_member_variable_node(DEBUG_MODE_VAR))
    showing = keep(ed.add_branch_node())
    _connect(out(seen, DEBUG_MODE_VAR), _pin(showing, "Condition"))
    _connect(exec_in, _pin(showing, "execute"))

    dmg_str = keep(_node(ed, FN_FLOAT_TO_STR))
    _connect(out(flew, "Damage"), _pin(dmg_str, "InDouble"))
    mult_str = keep(_node(ed, FN_FLOAT_TO_STR))
    _connect(out(flew, "Worth"), _pin(mult_str, "InDouble"))
    lead = keep(_node(ed, FN_CONCAT))
    _connect(out(dmg_str), _pin(lead, "A"))
    _set(lead, "B", " (x")
    body = keep(_node(ed, FN_CONCAT))
    _connect(out(lead), _pin(body, "A"))
    _connect(out(mult_str), _pin(body, "B"))
    text = keep(_node(ed, FN_CONCAT))
    _connect(out(body), _pin(text, "A"))
    _set(text, "B", ")")

    draw = keep(_node(ed, FN_DRAW_STRING))
    _connect(out(flew, "Stop"), _pin(draw, "TextLocation"))
    _connect(out(text), _pin(draw, "Text"))
    _set(draw, "TextColor", DAMAGE_TEXT_COLOR)
    _set(draw, "Duration", TRACE_DEBUG_SECONDS)
    _connect(then(showing), _pin(draw, "execute"))
    return made
