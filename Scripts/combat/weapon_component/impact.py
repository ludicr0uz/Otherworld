"""A pellet whose trace stopped on something: on a character, whether it
struck the body at all and where (the hit zone), then blood, damage, the zone's
multiplier and the debug-mode damage readout -- or, on anything without
health, the surface's chips and dust (surface_impact.py). firing.py traces the
pellets and calls in here on a hit.
"""

from combat.blood import (
    BLOOD_REFERENCE_DAMAGE, BLOOD_SCALE_MAX, BLOOD_SCALE_MIN,
)
from combat.game_state import (
    DAMAGED_BY_PLAYER_VAR, DAMAGE_TEXT_COLOR, DEBUG_MODE_VAR, LAST_DAMAGE_VAR,
    TRACE_DEBUG_SECONDS,
)
from uebp.graph import _connect, _loose_pin, _node, _palette, _pin, _set, _vec, out, then
from combat.hit_reaction import LAST_HIT_FROM_VAR
from combat.hit_zones import (
    HEAD_BONES_VAR, HEAD_MULT_VAR, HIT_BONE_VAR, HIT_POINT_VAR,
    LIMB_BONES_VAR, LIMB_MULT_VAR,
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


def _author_impact(ed, brk, held, exec_in):
    """A pellet that hit something: blood, then subtract the damage.

    Both are behind the health cast, so trees and terrain produce no blood
    -- only things carrying BP_HealthComponent bleed. What the cast refuses
    gets the bullet impact instead (_author_surface_impact). Both are also
    behind the hit zone (_author_hit_zone): a pellet stopped by a character's
    capsule that strikes none of its bodies passed the model by, and does
    nothing. The damage is the weapon's, scaled by where on the body it
    landed, using the target's own hit-box tables.
    """
    # Where the burst goes: the trace's hit, until the hit zone moves it onto
    # the body. Written before the cast so the scenery's chips read it too.
    mark = ed.add_set_member_variable_node(HIT_POINT_VAR)
    _connect(_loose_pin(brk, "Location", is_input=False), _pin(mark, HIT_POINT_VAR))
    _connect(exec_in, _pin(mark, "execute"))
    exec_in = then(mark)
    landed = ed.add_get_member_variable_node(HIT_POINT_VAR)
    comp = _node(ed, FN_GET_COMP)
    _connect(_loose_pin(brk, "HitActor", is_input=False), _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)

    cast = _palette(ed, NODE_CAST_HEALTH)
    _connect(out(comp), _pin(cast, "Object"))
    _connect(exec_in, _pin(cast, "execute"))
    as_health = _loose_pin(cast, "AsBPHealthComponent", is_input=False)

    blood_cls = ed.add_get_member_variable_node("BloodClass")
    where = _node(ed, FN_MAKE_TRANSFORM)
    _connect(out(landed, HIT_POINT_VAR), _pin(where, "Location"))
    # How big the spray is, as a clamped ratio of the round's damage to a
    # reference one. Spawn *scale* rather than a parameter on the splash,
    # because the droplet solver works in the actor's own space: scaling the
    # actor scales launch distance and droplet size together, which is the
    # single number that separates a 9 mm from a slug at contact range. A
    # shotgun pays eight of these at once, which is why one pellet is under 1x.
    spray_dmg_pin, spray_dmg = _prop(ed, "Damage", held)
    ratio = _node(ed, FN_DIV_FF)
    _connect(spray_dmg_pin, _pin(ratio, "A"))
    _set(ratio, "B", BLOOD_REFERENCE_DAMAGE)
    spray = _node(ed, FN_CLAMP)
    _connect(out(ratio), _pin(spray, "Value"))
    _set(spray, "Min", BLOOD_SCALE_MIN)
    _set(spray, "Max", BLOOD_SCALE_MAX)
    spray_v = _node(ed, FN_MUL_VF)
    _connect(_vec(ed, 1.0, 1.0, 1.0), _pin(spray_v, "A"))
    _connect(out(spray), _pin(spray_v, "B"))
    _connect(out(spray_v), _pin(where, "Scale"))
    # Point the splash's +X down the surface normal: BP_BloodSplash throws its
    # cone along its own forward, so this is what makes the spray come *out of*
    # the wound instead of along an arbitrary world axis.
    facing = _node(ed, FN_ROT_FROM_X)
    _connect(_loose_pin(brk, "ImpactNormal", is_input=False), _pin(facing, "X"))
    _connect(out(facing), _pin(where, "Rotation"))
    splash = _palette(ed, NODE_SPAWN)
    _connect(out(blood_cls, "BloodClass"), _pin(splash, "Class"))
    _connect(out(where), _pin(splash, "SpawnTransform"))
    _set(splash, "CollisionHandlingOverride", "AlwaysSpawn")
    chipped = _author_surface_impact(ed, where, out(cast, "CastFailed"))

    # The zone runs BEFORE the blood it is drawn to the right of: only a
    # pellet that struck a body (or a thing with health and no body) bleeds.
    zoned, zone_nodes = _author_hit_zone(ed, brk, then(cast))
    for tail in zoned:
        _connect(tail, _pin(splash, "execute"))

    get_h = ed.add_get_member_variable_node("Health", HEALTH_CLASS_PATH)
    _connect(as_health, _pin(get_h, "self"))
    dmg_pin, dmg_n = _prop(ed, "Damage", held)
    worth, worth_nodes = _zone_multiplier(ed, as_health)
    scaled = _node(ed, FN_MUL_FF)
    _connect(dmg_pin, _pin(scaled, "A"))
    _connect(worth, _pin(scaled, "B"))
    sub = _node(ed, FN_SUB_FF)
    _connect(out(get_h, "Health"), _pin(sub, "A"))
    _connect(out(scaled), _pin(sub, "B"))
    clamp = _node(ed, FN_CLAMP)
    _connect(out(sub), _pin(clamp, "Value"))
    _set(clamp, "Min", 0.0)
    _set(clamp, "Max", INF)
    set_h = ed.add_set_member_variable_node("Health", HEALTH_CLASS_PATH)
    _connect(as_health, _pin(set_h, "self"))
    _connect(out(clamp), _pin(set_h, "Health"))
    _connect(then(splash), _pin(set_h, "execute"))

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
    now = _node(ed, FN_TIME_SECONDS)
    stamp = ed.add_set_member_variable_node(LAST_DAMAGE_VAR, HEALTH_CLASS_PATH)
    _connect(as_health, _pin(stamp, "self"))
    _connect(out(now), _pin(stamp, LAST_DAMAGE_VAR))
    _connect(then(set_h), _pin(stamp, "execute"))

    blame = ed.add_set_member_variable_node(DAMAGED_BY_PLAYER_VAR, HEALTH_CLASS_PATH)
    _connect(as_health, _pin(blame, "self"))
    _set(blame, DAMAGED_BY_PLAYER_VAR, "true")
    _connect(then(stamp), _pin(blame, "execute"))

    # ...and which way it came from, for the flinch. The IMPACT NORMAL, not the
    # shot's own direction reversed: it is already in the hit result, it already
    # points back out of the surface toward the muzzle, and it is the one that
    # is right for a pellet that grazed a shoulder at an angle. A target shot in
    # the back therefore plays the Back reaction with nothing having measured an
    # angle. See _author_hit_reaction for what reads it.
    from_where = ed.add_set_member_variable_node(LAST_HIT_FROM_VAR, HEALTH_CLASS_PATH)
    _connect(as_health, _pin(from_where, "self"))
    _connect(_loose_pin(brk, "ImpactNormal", is_input=False),
             _pin(from_where, LAST_HIT_FROM_VAR))
    _connect(then(blame), _pin(from_where, "execute"))

    shown = _author_damage_readout(ed, brk, out(scaled), worth, then(from_where))

    ed.add_comment_to_nodes(
        "Clamped at zero so an overkill shot cannot drive Health negative -- "
        "the HUD bar divides by MaxHealth and the death check is Health <= 0, "
        "and both want a floor.",
        [mark, landed, comp, cast, blood_cls, where, facing, splash, spray_dmg, ratio, spray,
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
        f"1x. A pellet that clipped the capsule but strikes no body passed "
        f"the model by: no blood, no damage.",
        zone_nodes + worth_nodes + [dmg_n, scaled])
    ed.add_comment_to_nodes(
        "Debug mode only: the damage this pellet actually did, and the zone "
        "multiplier behind it, drawn where it landed for as long as the tracer.",
        shown)


def _author_damage_readout(ed, brk, damage, worth, exec_in):
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

    seen = keep(ed.add_get_member_variable_node(DEBUG_MODE_VAR))
    showing = keep(ed.add_branch_node())
    _connect(out(seen, DEBUG_MODE_VAR), _pin(showing, "Condition"))
    _connect(exec_in, _pin(showing, "execute"))

    dmg_str = keep(_node(ed, FN_FLOAT_TO_STR))
    _connect(damage, _pin(dmg_str, "InDouble"))
    mult_str = keep(_node(ed, FN_FLOAT_TO_STR))
    _connect(worth, _pin(mult_str, "InDouble"))
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
    _connect(_loose_pin(brk, "Location", is_input=False), _pin(draw, "TextLocation"))
    _connect(out(text), _pin(draw, "Text"))
    _set(draw, "TextColor", DAMAGE_TEXT_COLOR)
    _set(draw, "Duration", TRACE_DEBUG_SECONDS)
    _connect(then(showing), _pin(draw, "execute"))
    return made


def _author_hit_zone(ed, brk, exec_in):
    """Did this pellet strike the body, and which bone? Written into HitBone.

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

    The capsule is far wider than the model -- 34 cm of radius round an 18 cm
    head -- so a trace that finds no body is a pellet that flew past the model
    inside its capsule, and its exec ends here: it is a miss. It used to count
    as a body hit, which made every near miss round the head a hit. The bodies
    are fitted to the model for that reason (hit_bodies.py).

    A trace that struck writes HitBone and moves HitPoint from the capsule's
    surface onto the body's. HitBone is cleared first, for the one other way
    on: an actor with health that is not a Character has no mesh to trace, and
    takes the hit at 1x where the pellet's own trace landed.

    Returns (exec outs that continue to the blood, nodes made, next free x).
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    clear = keep(ed.add_set_member_variable_node(HIT_BONE_VAR))
    _set(clear, HIT_BONE_VAR, "None")
    _connect(exec_in, _pin(clear, "execute"))

    as_char = keep(_palette(ed, NODE_CAST_CHARACTER))
    _connect(_loose_pin(brk, "HitActor", is_input=False), _pin(as_char, "Object"))
    _connect(then(clear), _pin(as_char, "execute"))
    mesh = keep(ed.add_get_member_variable_node("Mesh", "/Script/Engine.Character"))
    _connect(_loose_pin(as_char, "AsCharacter", is_input=False), _pin(mesh, "self"))

    probe = keep(_node(ed, FN_TRACE_COMPONENT))
    _connect(out(mesh, "Mesh"), _pin(probe, "self"))
    _connect(_loose_pin(brk, "TraceStart", is_input=False), _pin(probe, "TraceStart"))
    _connect(_loose_pin(brk, "TraceEnd", is_input=False), _pin(probe, "TraceEnd"))
    # Simple collision is the physics asset's capsules and spheres, which is
    # the point: complex would be the render mesh, which has no bone to report.
    _set(probe, "bTraceComplex", "false")
    _set(probe, "bShowTrace", "false")
    _set(probe, "bPersistentShowTrace", "false")
    _connect(then(as_char), _pin(probe, "execute"))

    struck = keep(ed.add_branch_node())
    _connect(out(probe), _pin(struck, "Condition"))
    _connect(then(probe), _pin(struck, "execute"))
    note = keep(ed.add_set_member_variable_node(HIT_BONE_VAR))
    _connect(out(probe, "BoneName"), _pin(note, HIT_BONE_VAR))
    _connect(then(struck), _pin(note, "execute"))

    onto = keep(ed.add_set_member_variable_node(HIT_POINT_VAR))
    _connect(out(probe, "HitLocation"), _pin(onto, HIT_POINT_VAR))
    _connect(then(note), _pin(onto, "execute"))

    outs = [then(onto), out(as_char, "CastFailed")]
    return outs, made


def _zone_multiplier(ed, as_health):
    """What HitBone is worth on this target: a pure float, 1.0 unless zoned.

    Head is tested last so it wins, though the two tables never overlap -- a
    bone cannot be under both the head and a thigh.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    bone = keep(ed.add_get_member_variable_node(HIT_BONE_VAR))
    bone_out = out(bone, HIT_BONE_VAR)

    def member(table):
        pin, n = _prop(ed, table, as_health, HEALTH_CLASS_PATH)
        keep(n)
        test = keep(_node(ed, FN_ARR_CONTAINS))
        _connect(pin, _loose_pin(test, "TargetArray"))
        _connect(bone_out, _loose_pin(test, "ItemToFind"))
        return out(test)

    def worth(var):
        pin, n = _prop(ed, var, as_health, HEALTH_CLASS_PATH)
        keep(n)
        return pin

    is_limb = member(LIMB_BONES_VAR)
    limb_or_body = keep(_node(ed, FN_SELECT_FF))
    _connect(worth(LIMB_MULT_VAR), _pin(limb_or_body, "A"))
    _set(limb_or_body, "B", 1.0)
    _connect(is_limb, _pin(limb_or_body, "bPickA"))

    is_head = member(HEAD_BONES_VAR)
    pick = keep(_node(ed, FN_SELECT_FF))
    _connect(worth(HEAD_MULT_VAR), _pin(pick, "A"))
    _connect(out(limb_or_body), _pin(pick, "B"))
    _connect(is_head, _pin(pick, "bPickA"))
    return out(pick), made
