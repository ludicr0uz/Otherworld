"""verify.install -- Components installed on both characters, their hit-box tables and footsteps.
"""

import unreal

from combat.camera import CAMERA_ARM, CAMERA_SHOULDER
from combat.footsteps import FOOTSTEP_BP_PATH, FOOTSTEP_STRIDE_CM
from Sound.sound_monsters import MONSTER_FOOTSTEPS
from Sound.sound_world import FOOTSTEPS
from combat.game_state import TRACE_DEBUG_SECONDS
from combat.hit_zones import (
    HEAD_BONES_VAR, HEAD_MULT_VAR, LIMB_BONES_VAR, LIMB_MULT_VAR, hit_zones,
)
from combat.install import OLD_SHOTGUN_PARTS
from combat.tuning import COMBAT
from combat.verify.fixtures import char, h, hg, npc
from combat.verify.common import (
    BEL, _mesh_asset, cdo, check, component_template, components, graph, load,
)


# ─── Installation ────────────────────────────────────────────────────────────

def check_installation():
    def blocks_visibility(bp):
        """Would a Visibility line trace hit this character?

        The single most important check in this file. UE's stock Pawn profile
        ignores Visibility, which is the channel the pellets trace on, so a
        character left on the default is simply unhittable -- and the trace reports
        "no hit" exactly as it would for a real miss, so nothing anywhere says so.
        """
        capsule = component_template(bp, "CapsuleComponent")
        if capsule is None:
            return None
        return (capsule.get_collision_response_to_channel(
            unreal.CollisionChannel.ECC_VISIBILITY) == unreal.CollisionResponseType.ECR_BLOCK)


    cnames = set(components(char))
    # Found by type, not by name: the template's boom is "CameraBoom" in the
    # third-person template but that is a name somebody could reasonably change,
    # whereas there is only ever one spring arm on a third-person character.
    arm = next((c for c in (component_template(char, n) for n in components(char))
                if isinstance(c, unreal.SpringArmComponent)), None)
    check("the camera sits over the shoulder, so the reticle is not on the player",
          arm is not None
          and abs(arm.get_editor_property("socket_offset").y - CAMERA_SHOULDER[1]) < 1e-3
          and abs(arm.get_editor_property("target_arm_length") - CAMERA_ARM) < 1e-3,
          f"offset {arm.get_editor_property('socket_offset').to_tuple()}, "
          f"arm {arm.get_editor_property('target_arm_length')}" if arm else "no boom")

    move = next((c for c in (component_template(char, n) for n in components(char))
                 if isinstance(c, unreal.CharacterMovementComponent)), None)
    check("the body follows the camera, so the gun stays on the crosshair",
          cdo(char).get_editor_property("use_controller_rotation_yaw")
          and move is not None
          and not move.get_editor_property("orient_rotation_to_movement"),
          "orient-to-movement would turn the gun with the movement input instead")

    check("player carries HealthComponent + WeaponComponent",
          {"HealthComponent", "WeaponComponent"} <= cnames,
          str(sorted(cnames)))
    stale = cnames & OLD_SHOTGUN_PARTS
    check("the old welded shotgun is gone from the player", not stale, str(sorted(stale)))
    check("player's capsule blocks Visibility, so it can be shot too",
          blocks_visibility(char) is True, str(blocks_visibility(char)))

    check("pellet traces are drawn, so a miss is visible",
          TRACE_DEBUG_SECONDS > 0, f"{TRACE_DEBUG_SECONDS}s")

    if npc:
        check("NPC carries HealthComponent", "HealthComponent" in components(npc))
        n = cdo(npc)
        # A component added through the SCS is not a property on the CDO -- it is
        # constructed per instance -- so its authored defaults live on the subobject
        # template, which is also where the builder wrote them.
        comp = component_template(npc, "HealthComponent")
        check("NPC despawns at 0 HP",
              comp is not None and comp.get_editor_property("DespawnOnDeath") is True)
        rc = comp.get_editor_property("RespawnClass") if comp else None
        check("NPC respawns as another wanderer",
              rc is not None and "ForestWanderer" in rc.get_name(),
              rc.get_name() if rc else "None")
        # ...and as ITS OWN kind of wanderer. That template default names the
        # parent, and every variant inherits it, so on its own it means a dead
        # wendigo is replaced by a BP_ForestWanderer -- which wears the parent's
        # mesh, i.e. a zombie. Kill the two wendigos the level places and there are
        # never any more. The fix is that BeginPlay overwrites RespawnClass with
        # the owner's own class, and this is the check for it, because nothing a
        # headless run does will ever kill a wanderer.
        # GetObjectClass renders as "Get Class" in the graph.
        owner_class = [n for n in hg
                       if str(BEL.get_node_title(n)).replace("\n", " ") == "Get Class"]
        check("...and BeginPlay asks the owner what class it is",
              len(owner_class) == 1, str(len(owner_class)))
        # Loop variable deliberately not `n`: `n` is the NPC's CDO, read again two
        # checks below, and shadowing it here turned that read into a call on a
        # graph node.
        rewritten = []
        for getter in owner_class:
            for pin in BEL.list_output_pins(getter):
                for other in pin.list_connected_pins():
                    node = unreal.BlueprintGraphPinLibrary.get_owning_node(other)
                    if node and "RespawnClass" in str(BEL.get_node_title(node)):
                        rewritten.append(node)
        check("...and writes it into RespawnClass, so each creature respawns as "
              "itself", len(rewritten) == 1,
              str([str(BEL.get_node_title(x)) for x in rewritten]))
        check("NPC's capsule blocks Visibility, so pellets can actually hit it",
              blocks_visibility(npc) is True, str(blocks_visibility(npc)))
        check("a spawned wanderer still gets an AI controller",
              n.get_editor_property("auto_possess_ai")
              == unreal.AutoPossessAI.PLACED_IN_WORLD_OR_SPAWNED)


# ─── Hit boxes ───────────────────────────────────────────────────────────────

def check_hit_boxes():
    # The capsule says whether a pellet hit; the physics bodies say where. Every
    # half of that can be wrong while the gun still works -- a table that never
    # filled, a multiplier that declared as an int (1.5 -> 1), a second trace fed
    # from the wrong line -- and each looks exactly like "every hit is a body hit".

    for var, want in ((HEAD_MULT_VAR, COMBAT.head_multiplier),
                      (LIMB_MULT_VAR, COMBAT.limb_multiplier)):
        got = h.get_editor_property(var)
        check(f"{var} is {want}, and a float -- an int would truncate it",
              isinstance(got, float) and abs(got - want) < 1e-6, repr(got))




    for tag, bp in (("player", char), ("NPC", npc)):
        if not bp:
            continue
        comp = component_template(bp, "HealthComponent")
        heads = [str(b) for b in comp.get_editor_property(HEAD_BONES_VAR)] if comp else []
        limbs = [str(b) for b in comp.get_editor_property(LIMB_BONES_VAR)] if comp else []
        want_head, want_limbs, body = hit_zones(_mesh_asset(bp))
        # Rig-AGNOSTIC, deliberately. The first version of these asserted literal
        # mannequin bone names ("head" in heads, upperarm_l in limbs), which is the
        # very bug they were written to catch, one level up: the monsters are on a
        # Mixamo rig whose bodies are Head / LeftArm / LeftUpLeg, the tables were
        # perfectly correct, and the CHECK failed. What is actually worth asserting
        # is structural -- that the tables are what this mesh's own physics asset
        # resolves to, that both zones exist, that they do not overlap, and that
        # the torso is in neither.
        check(f"{tag}: the head table is its own skeleton's head bodies",
              heads == want_head and len(heads) > 0, str(heads))
        check(f"{tag}: the limb table is its own skeleton's arm and leg bodies",
              limbs == want_limbs and len(limbs) >= 4, str(limbs))
        # Four limbs means all four were found, not one root matched twice: a rig
        # whose arms resolved and whose legs did not would still list "several".
        roots = {b for b in limbs if not any(
            o != b and b.lower().startswith(o.lower()) for o in limbs)}
        check(f"{tag}: all four limbs are covered, not just the arms",
              len(limbs) >= 8 or len(roots) >= 4,
              f"{len(limbs)} limb bodies: {limbs}")
        check(f"{tag}: no bone is both head and limb", not set(heads) & set(limbs))
        check(f"{tag}: the torso is neither -- a chest shot is a 1x shot",
              len(body) > 0 and not set(body) & (set(heads) | set(limbs)),
              str(body))


# ─── Footsteps ───────────────────────────────────────────────────────────────

def check_footsteps():
    foot = load(FOOTSTEP_BP_PATH)
    check("there is a footstep component", foot is not None)
    if foot:
        f = cdo(foot)
        sounds = list(f.get_editor_property("Sounds"))
        check("...with more than one step, so it is not one buffer retriggered",
              len(sounds) >= 3, f"{len(sounds)} clips")
        check("...on a stride measured in centimetres, not seconds",
              abs(f.get_editor_property("StrideCm") - FOOTSTEP_STRIDE_CM) < 1e-6,
              repr(f.get_editor_property("StrideCm")))
        fg = graph(foot).list_all_nodes()
        # NOT `titles`: this file is a flat script and `titles` is the weapon
        # component's, read again hundreds of lines below.
        foot_titles = {str(BEL.get_node_title(x)).replace("\n", " ") for x in fg}
        # Distance, not time: the accumulator has to be driven by SPEED x dt. A
        # Delay or a plain timer here would be the bug this design exists to avoid.
        check("...accumulated from the owner's own speed",
              any("eloc" in t for t in foot_titles),
              str(sorted(t for t in foot_titles if "eloc" in t)))
        check("...and the remainder is carried, not zeroed, so the rate does not "
              "follow the framerate",
              any("-" in t or "Subtract" in t for t in foot_titles),
              str(len(foot_titles)))
        # The audibility probe that proved the attenuation boundaries at runtime
        # lived here, on a once-only Tick gate with a Probed flag. Both it and the
        # flag are asserted gone: a probe left in ships a PrintString on every
        # footstep component in the level.
        try:
            f.get_editor_property("Probed")
            _left_over = True
        except Exception:                                             # noqa: BLE001
            _left_over = False
        check("...and the temporary audibility probe is gone",
              not _left_over
              and not any("Print" in t or "Probed" in t for t in foot_titles),
              str(sorted(t for t in foot_titles if "Print" in t or "Probed" in t)))
    check("both the player and the wanderers wear it",
          "FootstepComponent" in components(char)
          and (npc is None or "FootstepComponent" in components(npc)))
    # One component, and whose feet they are is which takes its copy holds:
    # the class's own on the player, the monsters' on BP_ForestWanderer's.
    for who, bp, sound in (("the player", char, FOOTSTEPS), ("a wanderer", npc, MONSTER_FOOTSTEPS)):
        if bp is None or "FootstepComponent" not in components(bp):
            continue
        got = [s.get_name() for s in
               component_template(bp, "FootstepComponent").get_editor_property("Sounds") if s]
        check(f"{who}'s footsteps are the {len(sound.names)} takes of '{sound.key}'",
              got == list(sound.names), str(got))


def run():
    check_installation()
    check_hit_boxes()
    check_footsteps()
