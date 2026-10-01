"""A pellet that connected: blood, damage, the hit zone's multiplier and the
debug-mode damage readout -- or, on anything without health, the surface's
chips and dust (surface_impact.py). firing.py traces the pellets and calls in
here on a hit.
"""

from combat.blood import (
    BLOOD_REFERENCE_DAMAGE, BLOOD_SCALE_MAX, BLOOD_SCALE_MIN,
)
from combat.game_state import (
    DAMAGED_BY_PLAYER_VAR, DAMAGE_TEXT_COLOR, DEBUG_MODE_VAR, LAST_DAMAGE_VAR,
    TRACE_DEBUG_SECONDS,
)
from combat.graph import (
    BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set, _vec,
)
from combat.hit_reaction import LAST_HIT_FROM_VAR
from combat.hit_zones import (
    HEAD_BONES_VAR, HEAD_MULT_VAR, HIT_BONE_VAR, LIMB_BONES_VAR,
    LIMB_MULT_VAR,
)
from combat.nodes import (
    FN_ARR_CONTAINS, FN_CLAMP, FN_CONCAT, FN_DIV_FF, FN_DRAW_STRING,
    FN_FLOAT_TO_STR, FN_GET_COMP, FN_MAKE_TRANSFORM, FN_MUL_FF, FN_MUL_VF,
    FN_ROT_FROM_X, FN_SELECT_FF, FN_SUB_FF, FN_TIME_SECONDS,
    FN_TRACE_COMPONENT, INF, NODE_CAST_CHARACTER, NODE_CAST_HEALTH,
    NODE_SPAWN,
)
from combat.paths import HEALTH_CLASS_PATH
from combat.tuning import COMBAT
from combat.weapon_component.common import _prop
from combat.weapon_component.surface_impact import _author_surface_impact


def _author_impact(ed, brk, held, exec_in, x0, y0):
    """A pellet that hit something: blood, then subtract the damage.

    Both are behind the health cast, so trees and terrain produce no blood
    -- only things carrying BP_HealthComponent bleed. What the cast refuses
    gets the bullet impact instead (_author_surface_impact). The damage is
    the weapon's, scaled by where on the body it landed (see
    _author_hit_zone), using the target's own hit-box tables.
    """
    comp = _at(_node(ed, FN_GET_COMP), x0, y0 + 260)
    _connect(_loose_pin(brk, "HitActor", is_input=False), _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)

    cast = _at(_palette(ed, NODE_CAST_HEALTH), x0 + 260, y0)
    _connect(_pin(comp, "ReturnValue", is_input=False), _pin(cast, "Object"))
    _connect(exec_in, _pin(cast, "execute"))
    as_health = _loose_pin(cast, "AsBPHealthComponent", is_input=False)

    blood_cls = _at(ed.add_get_member_variable_node("BloodClass"), x0 + 520, y0 + 520)
    where = _at(_node(ed, FN_MAKE_TRANSFORM), x0 + 520, y0 + 380)
    _connect(_loose_pin(brk, "Location", is_input=False), _pin(where, "Location"))
    # How big the spray is, as a clamped ratio of the round's damage to a
    # reference one. Spawn *scale* rather than a parameter on the splash,
    # because the droplet solver works in the actor's own space: scaling the
    # actor scales launch distance and droplet size together, which is the
    # single number that separates a 9 mm from a slug at contact range. A
    # shotgun pays eight of these at once, which is why one pellet is under 1x.
    spray_dmg_pin, spray_dmg = _prop(ed, "Damage", held, x0 - 40, y0 + 760)
    ratio = _at(_node(ed, FN_DIV_FF), x0 + 200, y0 + 760)
    _connect(spray_dmg_pin, _pin(ratio, "A"))
    _set(ratio, "B", BLOOD_REFERENCE_DAMAGE)
    spray = _at(_node(ed, FN_CLAMP), x0 + 440, y0 + 760)
    _connect(_pin(ratio, "ReturnValue", is_input=False), _pin(spray, "Value"))
    _set(spray, "Min", BLOOD_SCALE_MIN)
    _set(spray, "Max", BLOOD_SCALE_MAX)
    spray_v = _at(_node(ed, FN_MUL_VF), x0 + 680, y0 + 900)
    _connect(_vec(ed, 1.0, 1.0, 1.0, x0 + 440, y0 + 1040), _pin(spray_v, "A"))
    _connect(_pin(spray, "ReturnValue", is_input=False), _pin(spray_v, "B"))
    _connect(_pin(spray_v, "ReturnValue", is_input=False), _pin(where, "Scale"))
    # Point the splash's +X down the surface normal: BP_BloodSplash throws its
    # cone along its own forward, so this is what makes the spray come *out of*
    # the wound instead of along an arbitrary world axis.
    facing = _at(_node(ed, FN_ROT_FROM_X), x0 + 520, y0 + 660)
    _connect(_loose_pin(brk, "ImpactNormal", is_input=False), _pin(facing, "X"))
    _connect(_pin(facing, "ReturnValue", is_input=False), _pin(where, "Rotation"))
    splash = _at(_palette(ed, NODE_SPAWN), x0 + 800, y0)
    _connect(_pin(blood_cls, "BloodClass", is_input=False), _pin(splash, "Class"))
    _connect(_pin(where, "ReturnValue", is_input=False), _pin(splash, "SpawnTransform"))
    _set(splash, "CollisionHandlingOverride", "AlwaysSpawn")
    _connect(BEL.find_then_pin(cast), _pin(splash, "execute"))
    chipped = _author_surface_impact(
        ed, where, _pin(cast, "CastFailed", is_input=False), x0 + 800, y0 - 420)

    zoned, zone_nodes, x_zone = _author_hit_zone(
        ed, brk, BEL.find_then_pin(splash), x0 + 1080, y0)

    get_h = _at(ed.add_get_member_variable_node("Health", HEALTH_CLASS_PATH),
                x_zone, y0 + 300)
    _connect(as_health, _pin(get_h, "self"))
    dmg_pin, dmg_n = _prop(ed, "Damage", held, x_zone - 480, y0 + 1300)
    worth, worth_nodes = _zone_multiplier(ed, as_health, x_zone - 480, y0 + 1440)
    scaled = _at(_node(ed, FN_MUL_FF), x_zone, y0 + 1300)
    _connect(dmg_pin, _pin(scaled, "A"))
    _connect(worth, _pin(scaled, "B"))
    sub = _at(_node(ed, FN_SUB_FF), x_zone + 240, y0 + 300)
    _connect(_pin(get_h, "Health", is_input=False), _pin(sub, "A"))
    _connect(_pin(scaled, "ReturnValue", is_input=False), _pin(sub, "B"))
    clamp = _at(_node(ed, FN_CLAMP), x_zone + 480, y0 + 300)
    _connect(_pin(sub, "ReturnValue", is_input=False), _pin(clamp, "Value"))
    _set(clamp, "Min", 0.0)
    _set(clamp, "Max", INF)
    set_h = _at(ed.add_set_member_variable_node("Health", HEALTH_CLASS_PATH),
                x_zone + 740, y0)
    _connect(as_health, _pin(set_h, "self"))
    _connect(_pin(clamp, "ReturnValue", is_input=False), _pin(set_h, "Health"))
    for tail in zoned:
        _connect(tail, _pin(set_h, "execute"))
    # Everything after this sits right of the zone block, as it sat right of
    # the splash before there was one.
    x0 += x_zone - (x0 + 1080)

    # Stamp the hit. Two things read this and nothing else writes it:
    #
    #   LastDamageTime  the HUD floats a wanderer's health bar for a few seconds
    #                   after it, and hides it the rest of the time;
    #   DamagedByPlayer what separates a kill from a wanderer that fell through
    #                   the world -- the safety net writes Health to 0 too, and
    #                   the kill counter must not count that.
    #
    # Written on every pellet rather than only on the killing one: a wanderer
    # that takes a hit and lives has to show its bar as well.
    now = _at(_node(ed, FN_TIME_SECONDS), x0 + 1820, y0 + 300)
    stamp = _at(ed.add_set_member_variable_node(LAST_DAMAGE_VAR, HEALTH_CLASS_PATH),
                x0 + 2080, y0)
    _connect(as_health, _pin(stamp, "self"))
    _connect(_pin(now, "ReturnValue", is_input=False), _pin(stamp, LAST_DAMAGE_VAR))
    _connect(BEL.find_then_pin(set_h), _pin(stamp, "execute"))

    blame = _at(ed.add_set_member_variable_node(DAMAGED_BY_PLAYER_VAR,
                                                HEALTH_CLASS_PATH),
                x0 + 2340, y0)
    _connect(as_health, _pin(blame, "self"))
    _set(blame, DAMAGED_BY_PLAYER_VAR, "true")
    _connect(BEL.find_then_pin(stamp), _pin(blame, "execute"))

    # ...and which way it came from, for the flinch. The IMPACT NORMAL, not the
    # shot's own direction reversed: it is already in the hit result, it already
    # points back out of the surface toward the muzzle, and it is the one that
    # is right for a pellet that grazed a shoulder at an angle. A target shot in
    # the back therefore plays the Back reaction with nothing having measured an
    # angle. See _author_hit_reaction for what reads it.
    from_where = _at(ed.add_set_member_variable_node(LAST_HIT_FROM_VAR,
                                                     HEALTH_CLASS_PATH),
                     x0 + 2600, y0)
    _connect(as_health, _pin(from_where, "self"))
    _connect(_loose_pin(brk, "ImpactNormal", is_input=False),
             _pin(from_where, LAST_HIT_FROM_VAR))
    _connect(BEL.find_then_pin(blame), _pin(from_where, "execute"))

    shown = _author_damage_readout(ed, brk, _pin(scaled, "ReturnValue", is_input=False),
                                   worth, BEL.find_then_pin(from_where), x0 + 2860, y0)

    ed.add_comment_to_nodes(
        "Clamped at zero so an overkill shot cannot drive Health negative -- "
        "the HUD bar divides by MaxHealth and the death check is Health <= 0, "
        "and both want a floor.",
        [comp, cast, blood_cls, where, facing, splash, spray_dmg, ratio, spray,
         spray_v, get_h, sub, clamp, set_h, now, stamp, blame,
         from_where])
    ed.add_comment_to_nodes(
        "No health component: the pellet hit the scenery, which chips and "
        "dusts where a body would bleed. The blood's own transform -- impact "
        "point, surface normal, scale off the round's damage.",
        chipped)
    ed.add_comment_to_nodes(
        f"Hit boxes: the pellet's own line is traced again against the target's "
        f"physics-asset bodies alone, and the bone it strikes picks the "
        f"multiplier off the TARGET's health component -- head "
        f"{COMBAT.head_multiplier}x, arms and legs {COMBAT.limb_multiplier}x, anything else "
        f"1x. A pellet that clipped the capsule but threaded between the limbs "
        f"strikes no body and counts as a body hit, which is what every hit "
        f"was before.",
        zone_nodes + worth_nodes + [dmg_n, scaled])
    ed.add_comment_to_nodes(
        "Debug mode only: the damage this pellet actually did, and the zone "
        "multiplier behind it, drawn where it landed for as long as the tracer.",
        shown)


def _author_damage_readout(ed, brk, damage, worth, exec_in, x0, y0):
    """In debug mode, write "<damage> (x<multiplier>)" at the impact point.

    Behind the same cached DebugMode the tracer branches on, and for the same
    TRACE_DEBUG_SECONDS, so the number appears at the end of the line that
    explains it. DrawDebugString rather than anything on the HUD: it is world
    space, needs no projection, and is compiled out of shipping builds like
    DrawDebugLine is.

    Re-reading `damage` and `worth` here is safe, though both are pure: their
    inputs (Damage, HitBone, the target's tables) are not written between the
    health update and this node.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    seen = keep(_at(ed.add_get_member_variable_node(DEBUG_MODE_VAR), x0, y0 + 300))
    showing = keep(_at(ed.add_branch_node(), x0 + 240, y0))
    _connect(_pin(seen, DEBUG_MODE_VAR, is_input=False), _pin(showing, "Condition"))
    _connect(exec_in, _pin(showing, "execute"))

    dmg_str = keep(_at(_node(ed, FN_FLOAT_TO_STR), x0, y0 + 440))
    _connect(damage, _pin(dmg_str, "InDouble"))
    mult_str = keep(_at(_node(ed, FN_FLOAT_TO_STR), x0, y0 + 580))
    _connect(worth, _pin(mult_str, "InDouble"))
    lead = keep(_at(_node(ed, FN_CONCAT), x0 + 240, y0 + 440))
    _connect(_pin(dmg_str, "ReturnValue", is_input=False), _pin(lead, "A"))
    _set(lead, "B", " (x")
    body = keep(_at(_node(ed, FN_CONCAT), x0 + 480, y0 + 440))
    _connect(_pin(lead, "ReturnValue", is_input=False), _pin(body, "A"))
    _connect(_pin(mult_str, "ReturnValue", is_input=False), _pin(body, "B"))
    text = keep(_at(_node(ed, FN_CONCAT), x0 + 720, y0 + 440))
    _connect(_pin(body, "ReturnValue", is_input=False), _pin(text, "A"))
    _set(text, "B", ")")

    draw = keep(_at(_node(ed, FN_DRAW_STRING), x0 + 960, y0))
    _connect(_loose_pin(brk, "Location", is_input=False), _pin(draw, "TextLocation"))
    _connect(_pin(text, "ReturnValue", is_input=False), _pin(draw, "Text"))
    _set(draw, "TextColor", DAMAGE_TEXT_COLOR)
    _set(draw, "Duration", TRACE_DEBUG_SECONDS)
    _connect(BEL.find_then_pin(showing), _pin(draw, "execute"))
    return made


def _author_hit_zone(ed, brk, exec_in, x0, y0):
    """Which bone did this pellet strike? Written into HitBone, None for none.

    The pellet trace stops at the capsule -- make_shootable makes the capsule,
    not the mesh, block Visibility, and that is what keeps the aim trace and
    the reticle predictable. So the capsule answers *whether* a character was
    hit, and a second trace along the very same line (the hit result carries
    its TraceStart/TraceEnd) answers *where*: K2_LineTraceComponent tests one
    component only, and on a skeletal mesh that means its physics bodies, each
    of which reports its bone. It ignores collision channels altogether, so the
    mesh's own profile (CharacterMesh, which ignores Visibility) is irrelevant;
    what matters is that the mesh has query collision at all, or it has no
    bodies at runtime -- install_hit_zones asserts that.

    HitBone is cleared first, then written only by a trace that struck, which
    covers both misses with one node: an actor that is not a Character (no
    mesh to trace), and a pellet that clipped the capsule's edge and threaded
    between the arms and the body.

    Returns (exec outs that continue to the damage, nodes made, next free x).
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    clear = keep(_at(ed.add_set_member_variable_node(HIT_BONE_VAR), x0, y0))
    _set(clear, HIT_BONE_VAR, "None")
    _connect(exec_in, _pin(clear, "execute"))

    as_char = keep(_at(_palette(ed, NODE_CAST_CHARACTER), x0 + 260, y0))
    _connect(_loose_pin(brk, "HitActor", is_input=False), _pin(as_char, "Object"))
    _connect(BEL.find_then_pin(clear), _pin(as_char, "execute"))
    mesh = keep(_at(ed.add_get_member_variable_node("Mesh", "/Script/Engine.Character"),
                    x0 + 260, y0 + 300))
    _connect(_loose_pin(as_char, "AsCharacter", is_input=False), _pin(mesh, "self"))

    probe = keep(_at(_node(ed, FN_TRACE_COMPONENT), x0 + 560, y0))
    _connect(_pin(mesh, "Mesh", is_input=False), _pin(probe, "self"))
    _connect(_loose_pin(brk, "TraceStart", is_input=False), _pin(probe, "TraceStart"))
    _connect(_loose_pin(brk, "TraceEnd", is_input=False), _pin(probe, "TraceEnd"))
    # Simple collision is the physics asset's capsules and spheres, which is
    # the point: complex would be the render mesh, which has no bone to report.
    _set(probe, "bTraceComplex", "false")
    _set(probe, "bShowTrace", "false")
    _set(probe, "bPersistentShowTrace", "false")
    _connect(BEL.find_then_pin(as_char), _pin(probe, "execute"))

    struck = keep(_at(ed.add_branch_node(), x0 + 880, y0))
    _connect(_pin(probe, "ReturnValue", is_input=False), _pin(struck, "Condition"))
    _connect(BEL.find_then_pin(probe), _pin(struck, "execute"))
    note = keep(_at(ed.add_set_member_variable_node(HIT_BONE_VAR), x0 + 1120, y0))
    _connect(_pin(probe, "BoneName", is_input=False), _pin(note, HIT_BONE_VAR))
    _connect(BEL.find_then_pin(struck), _pin(note, "execute"))

    outs = [BEL.find_then_pin(note), BEL.find_else_pin(struck),
            _pin(as_char, "CastFailed", is_input=False)]
    return outs, made, x0 + 1400


def _zone_multiplier(ed, as_health, x0, y0):
    """What HitBone is worth on this target: a pure float, 1.0 unless zoned.

    Head is tested last so it wins, though the two tables never overlap -- a
    bone cannot be under both the head and a thigh.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    bone = keep(_at(ed.add_get_member_variable_node(HIT_BONE_VAR), x0, y0 + 280))
    bone_out = _pin(bone, HIT_BONE_VAR, is_input=False)

    def member(table, x, y):
        pin, n = _prop(ed, table, as_health, x, y, HEALTH_CLASS_PATH)
        keep(n)
        test = keep(_at(_node(ed, FN_ARR_CONTAINS), x + 240, y))
        _connect(pin, _loose_pin(test, "TargetArray"))
        _connect(bone_out, _loose_pin(test, "ItemToFind"))
        return _pin(test, "ReturnValue", is_input=False)

    def worth(var, x, y):
        pin, n = _prop(ed, var, as_health, x, y, HEALTH_CLASS_PATH)
        keep(n)
        return pin

    is_limb = member(LIMB_BONES_VAR, x0, y0)
    limb_or_body = keep(_at(_node(ed, FN_SELECT_FF), x0 + 480, y0))
    _connect(worth(LIMB_MULT_VAR, x0 + 240, y0 + 140), _pin(limb_or_body, "A"))
    _set(limb_or_body, "B", 1.0)
    _connect(is_limb, _pin(limb_or_body, "bPickA"))

    is_head = member(HEAD_BONES_VAR, x0, y0 + 420)
    pick = keep(_at(_node(ed, FN_SELECT_FF), x0 + 720, y0 + 420))
    _connect(worth(HEAD_MULT_VAR, x0 + 480, y0 + 560), _pin(pick, "A"))
    _connect(_pin(limb_or_body, "ReturnValue", is_input=False), _pin(pick, "B"))
    _connect(is_head, _pin(pick, "bPickA"))
    return _pin(pick, "ReturnValue", is_input=False), made
