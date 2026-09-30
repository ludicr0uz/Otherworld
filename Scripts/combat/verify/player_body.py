"""verify.player_body -- The player's worn body: skin, grip socket, physics asset, and hit zones
probed by real traces.
"""

import unreal

from combat.game_state import DEBUG_MODE_VAR, TRACE_DEBUG_SECONDS
from combat.graph import _component_object, _handles
from combat.grip import _mesh_bone_names
from combat.hit_zones import (
    HEAD_BONES_VAR, HEAD_MULT_VAR, LIMB_BONES_VAR, hit_zones,
)
from combat.skin import SKIN_QUINN, player_skin
from combat.tuning import COMBAT
from combat.verify.fixtures import char, npc, wg
from combat.verify.common import (
    BEL, PIN, _mesh_asset, check, in_pins, load, num_pin, pin_value, titled,
    zone_tables,
)


# ─── The player's body ───────────────────────────────────────────────────────

def check_player_body():
    # The player is no longer necessarily SKM_Quinn_Simple. Which body is worn is
    # decided by whether the asset pipeline has produced the adventurer, so what is
    # asserted here is that WHICHEVER skin resolved is internally consistent --
    # and, above all, that the mesh and the anim BP agree about the skeleton. That
    # mismatch is the silent one: the component falls back to the reference pose
    # and the player slides around the map in a bind pose with nothing in the log.

    skin = player_skin()
    unreal.log_warning(f"[VERIFY] player skin: {skin.mesh.rsplit('/', 1)[1]}")
    worn = _mesh_asset(char) if char else None
    check("the player wears the skin the builder resolved",
          worn is not None and worn.get_path_name().split(".")[0] == skin.mesh,
          worn.get_path_name() if worn else "None")

    _anim_class = unreal.load_class(
        None, f"{skin.anim_bp}.{skin.anim_bp.rsplit('/', 1)[1]}_C")
    _mesh_comp = None
    for _h, _n in (_handles(char) if char else []):
        _o = _component_object(_h)
        if isinstance(_o, unreal.SkeletalMeshComponent):
            _mesh_comp = _o
            break
    check("...animated by that skin's anim blueprint",
          _mesh_comp is not None and _anim_class is not None
          and _mesh_comp.get_editor_property("anim_class") == _anim_class,
          str(_mesh_comp.get_editor_property("anim_class")) if _mesh_comp else "no mesh")
    _abp = load(skin.anim_bp)
    check("...and the two agree about the skeleton, so the pose is not the bind pose",
          worn is not None and _abp is not None
          and _abp.get_editor_property("target_skeleton")
          == worn.get_editor_property("skeleton"),
          f"mesh {worn.get_editor_property('skeleton').get_name() if worn else None} vs "
          f"anim {_abp.get_editor_property('target_skeleton').get_name() if _abp else None}")

    if _mesh_comp:
        check("the body stands in its capsule, not on top of it",
              abs(_mesh_comp.get_editor_property("relative_location").z - skin.mesh_z) < 0.01,
              str(_mesh_comp.get_editor_property("relative_location").z))
        check("...facing the actor's forward",
              abs(_mesh_comp.get_editor_property("relative_rotation").yaw
                  - skin.mesh_yaw) < 0.01,
              str(_mesh_comp.get_editor_property("relative_rotation").yaw))

    # The grip has to resolve to something on the worn mesh. A name that is neither
    # a socket nor a bone does not error at attach time: the weapon silently binds
    # to the component root and rides in the middle of the player's chest.
    if worn:
        _sock = worn.find_socket(skin.grip)
        _bones = [str(b) for b in _mesh_bone_names(worn)]
        check(f"the weapon's attach point {skin.grip!r} exists on the worn body",
              _sock is not None or skin.grip in _bones,
              "neither a socket nor a bone")
        check("...and the rig it belongs to has a hand at the end of each arm",
              len([b for b in _bones if "hand" in b.lower()]) >= 2
              or len([b for b in _bones if b.lower().endswith("_r")
                      or b.lower().endswith("_l")]) >= 2,
              str([b for b in _bones if "hand" in b.lower()]))
        # Ragdoll and hit zones are the same precondition asked twice: both are
        # reading the bodies of the worn mesh's physics asset, and a skin swapped
        # in without one would pass every graph check in this file and then stand
        # bolt upright at 0 HP.
        check("the worn body has a physics asset, so it can ragdoll and be zoned",
              worn.get_editor_property("physics_asset") is not None,
              str(worn.get_editor_property("physics_asset")))

    # The fallback is load-bearing and is never the thing being exercised, so it is
    # checked directly: a clone that has not run the asset pipeline gets SKIN_QUINN
    # and must get every asset it names.
    _fallback = [a for a in (SKIN_QUINN.mesh, SKIN_QUINN.anim_bp,
                             SKIN_QUINN.aim_rifle, SKIN_QUINN.aim_pistol,
                             SKIN_QUINN.punch)
                 if not load(a)]
    check("the mannequin fallback skin is complete, for a clone with no /Game/Sourced",
          not _fallback, str(_fallback))
    # Every ready pose the weapons name has to live on the skeleton being worn, or
    # PlaySlotAnimationAsDynamicMontage plays nothing and the gun hangs at the hip.
    for _label, _pose in (("rifle", skin.aim_rifle), ("pistol", skin.aim_pistol)):
        _p = load(_pose)
        check(f"the {_label} ready pose is authored for the worn skeleton",
              _p is not None and worn is not None
              and _p.get_editor_property("skeleton") == worn.get_editor_property("skeleton"),
              str(_p.get_editor_property("skeleton").get_name()) if _p else "missing")


    wt = wg
    zone_traces = [n for n in wt if {"TraceStart", "TraceEnd", "bTraceComplex"} <= in_pins(n)]
    check("one trace against the struck character's body, per pellet",
          len(zone_traces) == 1, f"{len(zone_traces)} K2_LineTraceComponent node(s)")
    if zone_traces:
        zt = zone_traces[0]
        fed = {pin: {str(BEL.get_node_title(PIN.get_owning_node(q))).replace("\n", " ")
                     for q in PIN.list_connected_pins(BEL.find_input_pin(zt, pin))}
               for pin in ("TraceStart", "TraceEnd", "self")}
        # The pellet's own line, from the pellet's own hit result -- not the aim
        # point, not the muzzle recomputed: a second line would land somewhere the
        # first one did not.
        check("it retraces the pellet's own line (TraceStart/TraceEnd of its hit)",
              all(any("BreakHitResult" in t for t in fed[p])
                  for p in ("TraceStart", "TraceEnd")), str(fed))
        check("it traces the character's mesh, whose bodies carry bone names",
              any("Mesh" in t for t in fed["self"]), str(fed["self"]))
        check("it traces the simple (physics body) shapes, not the render mesh",
              pin_value(zt, "bTraceComplex").lower() == "false")
    contains = [n for n in wt if {"TargetArray", "ItemToFind"} <= in_pins(n)]
    tables = {str(BEL.get_node_title(PIN.get_owning_node(q)))
              for n in contains
              for q in PIN.list_connected_pins(BEL.find_input_pin(n, "TargetArray"))}
    check("the struck bone is looked up in both of the TARGET's tables",
          {f"Get {HEAD_BONES_VAR}", f"Get {LIMB_BONES_VAR}"} <= tables, str(tables))
    # The damage subtraction's B must be Damage x multiplier, not raw Damage.
    scaled = False
    for n in titled(wt, "float - float"):
        for q in PIN.list_connected_pins(BEL.find_input_pin(n, "B")):
            mul = PIN.get_owning_node(q)
            if "*" not in str(BEL.get_node_title(mul)):
                continue
            srcs = {str(BEL.get_node_title(PIN.get_owning_node(r)))
                    for pin in ("A", "B")
                    for r in PIN.list_connected_pins(BEL.find_input_pin(mul, pin))}
            scaled |= "Get Damage" in srcs and any("Select" in s for s in srcs)
    check("health loses Damage x the zone's multiplier, not raw Damage", scaled)


    def upstream(node, depth=8):
        """Titles of every node feeding `node`'s inputs, transitively."""
        # Data pins only: following "execute" would walk back up the whole shot.
        # Nodes are tracked by name, not title -- two SelectFloats share a title.
        out, seen, frontier = set(), set(), [node]
        for _ in range(depth):
            nxt = []
            for n in frontier:
                for p in BEL.list_input_pins(n):
                    if str(PIN.get_pin_name(p)) == "execute":
                        continue
                    for q in PIN.list_connected_pins(p):
                        src = PIN.get_owning_node(q)
                        if src.get_name() in seen:
                            continue
                        seen.add(src.get_name())
                        out.add(str(BEL.get_node_title(src)).replace("\n", " "))
                        nxt.append(src)
            frontier = nxt
        return out


    # Debug mode's damage readout: the number the target actually lost, at the
    # point it was hit, only when the tracers are on.
    readouts = [n for n in wt if {"TextLocation", "Text", "Duration"} <= in_pins(n)]
    check("one damage readout per impact (DrawDebugString)", len(readouts) == 1,
          f"{len(readouts)} DrawDebugString node(s)")
    if readouts:
        ro = readouts[0]
        gates = [PIN.get_owning_node(q) for q in
                 PIN.list_connected_pins(BEL.find_input_pin(ro, "execute"))]
        check("...drawn only in debug mode",
              any("Branch" in str(BEL.get_node_title(g))
                  and any(DEBUG_MODE_VAR in str(BEL.get_node_title(PIN.get_owning_node(q)))
                          for q in PIN.list_connected_pins(BEL.find_input_pin(g, "Condition")))
                  for g in gates))
        check("...at the impact point",
              any("BreakHitResult" in str(BEL.get_node_title(PIN.get_owning_node(q)))
                  for q in PIN.list_connected_pins(BEL.find_input_pin(ro, "TextLocation"))))
        check("...for as long as the tracer",
              abs((num_pin(ro, "Duration") or 0.0) - TRACE_DEBUG_SECONDS) < 1e-6,
              pin_value(ro, "Duration"))
        fed = upstream(ro)
        check("...showing the damage dealt (Damage x zone), not the weapon's raw Damage",
              "Get Damage" in fed and any("*" in t for t in fed)
              and f"Get {HEAD_MULT_VAR}" in fed, str(sorted(fed)))

    # And the geometry: put a wanderer in the editor world and fire the same
    # component trace through each part of it. This is what proves the physics
    # asset actually covers the body where the tables say it does, and that the
    # bone a trace reports is one the tables know.
    if npc:
        # The NPC's own tables, and the torso bodies hit_zones() leaves out of
        # both -- what the probes below may aim at.
        heads, limbs = zone_tables(npc)
        body = hit_zones(_mesh_asset(npc))[2]
        eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        dummy = eas.spawn_actor_from_class(BEL.generated_class(npc),
                                           unreal.Vector(0.0, 0.0, 60000.0))
        try:
            body_mesh = dummy.get_component_by_class(unreal.SkeletalMeshComponent)

            def between(a, b):
                pa, pb = body_mesh.get_socket_location(a), body_mesh.get_socket_location(b)
                return (pa + pb) * 0.5

            # (point, direction the shot comes from, what it should be worth). The
            # arms are shot from the side they hang on: in the reference pose they
            # lie along the flanks, and a line through the upper arm from the
            # front meets the chest first -- which is the correct answer for that
            # line, and not the part under test.
            front = unreal.Vector(300.0, 0.0, 0.0)

            # Probe bones resolved from the rig, not written down. Same reason as
            # the tables above -- and here the stakes are higher, because
            # get_socket_location on a bone that does not exist returns the
            # component origin rather than failing, so a stale name does not make
            # the check fail, it makes it trace through the middle of the actor and
            # PASS for the wrong reason. Three of these were doing exactly that.
            def bone(*candidates):
                have = {b.lower(): b for b in (heads + limbs + body)}
                for c in candidates:
                    if c.lower() in have:
                        return have[c.lower()]
                return None

            head_b = bone("head", "Head")
            arm_u = bone("upperarm_r", "RightArm")
            arm_l = bone("lowerarm_r", "RightForeArm")
            leg_u = bone("thigh_l", "LeftUpLeg")
            leg_l = bone("calf_l", "LeftLeg")
            chest = bone("spine_03", "Spine2", "Spine1", "Spine")

            aims = {}
            if head_b:
                aims["head"] = (body_mesh.get_socket_location(head_b)
                                + unreal.Vector(0.0, 0.0, 10.0), front,
                                COMBAT.head_multiplier)
            # Across the bone, not along a world axis. A fixed sideways shot works
            # on the mannequin, whose arms hang at the flanks, and fails on the
            # Meshy A-pose, whose arms are held out -- there the line reaches the
            # spine first and reports a 1x chest hit, which is the correct answer
            # for that line and not the part under test. 30 cm is short enough that
            # it cannot reach the torso from any limb.
            def across(a, b, reach=30.0):
                pa, pb = (body_mesh.get_socket_location(a),
                          body_mesh.get_socket_location(b))
                axis = pb - pa
                length = axis.length()
                if length < 1e-3:
                    return unreal.Vector(0.0, reach, 0.0)
                axis = axis / length
                # Any vector not parallel to the bone, made perpendicular to it.
                seed = (unreal.Vector(0.0, 0.0, 1.0) if abs(axis.z) < 0.9
                        else unreal.Vector(1.0, 0.0, 0.0))
                perp = seed - axis * (seed.x * axis.x + seed.y * axis.y
                                      + seed.z * axis.z)
                n2 = perp.length()
                return (perp / n2) * reach if n2 > 1e-3 else unreal.Vector(0.0, reach, 0.0)

            # Centred on the JOINT at the far end of the limb -- the elbow, the
            # knee -- rather than on the midpoint of the two. The midpoint is fine
            # on the mannequin and lands near the shoulder on the Meshy rig, where
            # a 30 cm line across it still reaches Spine01 and reports a chest hit.
            # An elbow is unambiguously in an arm on any rig.
            if arm_u and arm_l:
                aims["upper arm"] = (body_mesh.get_socket_location(arm_l),
                                     across(arm_u, arm_l, 18.0),
                                     COMBAT.limb_multiplier)
            if leg_u and leg_l:
                aims["thigh"] = (body_mesh.get_socket_location(leg_l),
                                 across(leg_u, leg_l, 18.0), COMBAT.limb_multiplier)
            if chest:
                aims["chest"] = (body_mesh.get_socket_location(chest), front, 1.0)
            check("the zone probe found bones to shoot at on this rig",
                  len(aims) == 4,
                  f"{sorted(aims)} (head={head_b} arm={arm_u}/{arm_l} "
                  f"leg={leg_u}/{leg_l} chest={chest})")
            for part, (at, side, want) in aims.items():
                hit = body_mesh.line_trace_component(at + side, at - side,
                                                     False, False, False)
                bone = str(hit[2]) if hit and hit[2] else "None"
                worth = (COMBAT.head_multiplier if bone in heads
                         else COMBAT.limb_multiplier if bone in limbs else 1.0)
                check(f"a shot through the {part} strikes a body worth {want}x",
                      bone != "None" and abs(worth - want) < 1e-6,
                      f"bone {bone} -> {worth}x")
        finally:
            dummy.destroy_actor()


def run():
    check_player_body()
