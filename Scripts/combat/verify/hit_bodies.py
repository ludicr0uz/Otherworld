"""verify.hit_bodies -- The physics bodies sit on the models (hit_bodies.py),
and a pellet that strikes none of them does nothing.
"""

import unreal

from combat.hit_bodies import (
    COVERAGE_MAX_HEAD_OVERHANG, COVERAGE_MAX_OVERHANG, COVERAGE_MAX_UNCOVERED,
    body_coverage, body_fit_plan, saved_capsules,
)
from combat.fx_vars import ShotHitScale
from combat.hit_zones import HIT_BONE_VAR, HIT_POINT_VAR
from combat.ragdoll import RAGDOLL_MESH_ROOT
from combat.shot_vars import PELLET_FLEW
from combat.verify.anchor import event
from combat.verify.common import BEL, PIN, check, in_pins, titled
from combat.verify.fixtures import wg


def _near(a, b, tol=0.05):
    return abs(a - b) <= tol


# ─── The bodies are the size of the model ────────────────────────────────────

def check_bodies_fit_the_model():
    # The importer's capsules stood 4-8 cm proud of the skin all round: the
    # zombie's head body was 26 cm across on an 18 cm head. Read back off the
    # saved assets, then measured the way a pellet meets them.
    eas = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    for path in sorted(eas.list_assets(RAGDOLL_MESH_ROOT, recursive=True)):
        mesh = eas.load_asset(path.split(".")[0])
        if not isinstance(mesh, unreal.SkeletalMesh):
            continue
        name = mesh.get_name()
        plan = body_fit_plan(mesh)
        check(f"{name}: every physics body has a fit planned", len(plan) >= 8,
              f"{len(plan)} bodies")
        off = []
        for b in plan:
            saved = saved_capsules(b["setup"])
            want = [(c["center"], c["radius"], c["length"]) for c in b["capsules"]]
            same = len(saved) == len(want) and all(
                all(_near(x, y) for x, y in zip(sc, wc)) and _near(sr, wr)
                and _near(sl, wl)
                for (sc, sr, sl), (wc, wr, wl) in zip(saved, want))
            if not same:
                off.append((b["bone"], saved, want))
        check("...and the saved capsules are the fitted ones", not off, str(off[:3]))

        cover = body_coverage(mesh)
        detail = (f"overhang {cover['overhang']:.3f}, uncovered "
                  f"{cover['uncovered']:.3f}, head overhang "
                  f"{cover['head_overhang']:.3f} {cover['counts']}")
        check(f"...and no more than {COVERAGE_MAX_UNCOVERED:.0%} of the rays "
              f"that strike the model strike no body",
              cover["uncovered"] <= COVERAGE_MAX_UNCOVERED, detail)
        if not cover["counts"]["head"]:
            # The wendigo: its head, antlers and neck are one body, and one
            # capsule round a pair of antlers is mostly air. Not held to the
            # overhang bounds until it has bodies of its own up there.
            continue
        check(f"...and the bodies overhang the model by no more than "
              f"{COVERAGE_MAX_OVERHANG:.0%} of its rays",
              cover["overhang"] <= COVERAGE_MAX_OVERHANG, detail)
        check(f"...the head's by no more than {COVERAGE_MAX_HEAD_OVERHANG:.0%} "
              f"of the head's", cover["head_overhang"] <= COVERAGE_MAX_HEAD_OVERHANG,
              detail)


# ─── A pellet that strikes no body is a miss ─────────────────────────────────

def _then(node):
    return [PIN.get_owning_node(q)
            for q in PIN.list_connected_pins(BEL.find_then_pin(node))]


def _title(node):
    return str(BEL.get_node_title(node)).replace("\n", " ")


def _fed_by(node, pin):
    return {_title(PIN.get_owning_node(q))
            for q in PIN.list_connected_pins(BEL.find_input_pin(node, pin))}


def _fed_pins(node, pin):
    """{(output pin name, its node)} feeding ``node``'s input ``pin``."""
    return {(str(PIN.get_pin_name(q)), PIN.get_owning_node(q))
            for q in PIN.list_connected_pins(BEL.find_input_pin(node, pin))}


def check_body_miss_is_a_miss():
    # The capsule stops the pellet and is twice the model's width. The body
    # trace used to pick the multiplier only, so a round through the air
    # beside the head still bled and still did its damage at 1x.
    # (A thrown blade's stage has a body trace of its own: verify/throw_strike.)
    # Since W1 the pellet is flown in C++ (FirePellets: one ShotTrace, the
    # capsule and the bodies on the one line), which hurts only a body it
    # struck and says what the pellet did as PelletFlew: bHurt, bScenery, or
    # neither for one that crossed a capsule and passed the body by.
    flew = event(PELLET_FLEW)
    if not check_one("one PelletFlew event in the fire graph: the native base's word "
                     "of each pellet it flew", [flew] if flew is not None else []):
        return
    branches = [n for n in wg if "Condition" in in_pins(n)
                and ("bHurt", flew) in _fed_pins(n, "Condition")]
    if not check_one("one Branch asks it whether a body was hurt (bHurt)", branches):
        return
    struck = branches[0]
    spared = [PIN.get_owning_node(q) for q in PIN.list_connected_pins(BEL.find_else_pin(struck))]
    scenery = [n for n in spared if ("bScenery", flew) in _fed_pins(n, "Condition")]
    missed = [q for n in scenery for q in PIN.list_connected_pins(BEL.find_else_pin(n))]
    check("a pellet that strikes no body and no scenery ends there: no blood, no chips",
          len(spared) == 1 and len(scenery) == 1 and len(missed) == 0,
          f"{len(spared)} node(s) on bHurt's False, {len(missed)} link(s) on bScenery's False")

    marks = titled(wg, f"Set {HIT_POINT_VAR}")
    bones = titled(wg, f"Set {HIT_BONE_VAR}")
    check("HitPoint and HitBone are written once a pellet, from PelletFlew's Point and "
          "Bone: the body's where a body was struck, the trace's own otherwise",
          len(marks) == 1 and len(bones) == 1
          and _fed_pins(marks[0], HIT_POINT_VAR) == {("Point", flew)}
          and _fed_pins(bones[0], HIT_BONE_VAR) == {("Bone", flew)},
          f"{len(marks)} point write(s), {len(bones)} bone write(s)")
    noted = _then(struck)
    check("...and the blood is noted off bHurt, for the shot's one Multicast "
          "(verify/shot_hits.py)",
          [_title(n) for n in noted] == [f"Set {ShotHitScale}"],
          str([_title(n) for n in noted]))


def check_one(label, nodes):
    check(label, len(nodes) == 1, f"{len(nodes)} node(s)")
    return len(nodes) == 1


def run():
    check_bodies_fit_the_model()
    check_body_miss_is_a_miss()
