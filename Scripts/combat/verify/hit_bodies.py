"""verify.hit_bodies -- The physics bodies sit on the models (hit_bodies.py),
and a pellet that strikes none of them does nothing.
"""

import unreal

from combat.hit_bodies import (
    COVERAGE_MAX_HEAD_OVERHANG, COVERAGE_MAX_OVERHANG, COVERAGE_MAX_UNCOVERED,
    body_coverage, body_fit_plan, saved_capsules,
)
from combat.hit_zones import HIT_BONE_VAR, HIT_POINT_VAR
from combat.ragdoll import RAGDOLL_MESH_ROOT
from combat.verify.common import BEL, PIN, check, in_pins, titled
from combat.verify.fixtures import wg
from combat.verify.throw_strike import is_strike_node


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


def check_body_miss_is_a_miss():
    # The capsule stops the pellet and is twice the model's width. The body
    # trace used to pick the multiplier only, so a round through the air
    # beside the head still bled and still did its damage at 1x.
    # (A thrown blade's stage has a body trace of its own: verify/throw_strike.)
    traces = [n for n in wg if {"TraceStart", "TraceEnd", "bTraceComplex"} <= in_pins(n)
              and not is_strike_node(n)]
    if not check_one("one body trace in the fire graph", traces):
        return
    branches = _then(traces[0])
    if not check_one("the body trace is followed by one Branch", branches):
        return
    struck = branches[0]
    check("...on whether it struck a body",
          any("LineTraceComponent" in t or "Line Trace Component" in t
              for t in _fed_by(struck, "Condition")), str(_fed_by(struck, "Condition")))
    missed = PIN.list_connected_pins(BEL.find_else_pin(struck))
    check("a pellet that strikes no body ends there: no blood, no damage",
          len(missed) == 0, f"{len(missed)} link(s) on the Branch's False")

    hit = _then(struck)
    check("a pellet that strikes one records the bone",
          [_title(n) for n in hit] == [f"Set {HIT_BONE_VAR}"],
          str([_title(n) for n in hit]))
    marks = titled(wg, f"Set {HIT_POINT_VAR}")
    fed = sorted(str(sorted(_fed_by(n, HIT_POINT_VAR))) for n in marks)
    check("HitPoint is written twice: the pellet's own hit, then the body's",
          len(marks) == 2 and any("Break Hit Result" in f or "BreakHitResult" in f
                                  for f in fed)
          and any("Trace" in f for f in fed), str(fed))
    onto = [n for n in marks if hit and n in _then(hit[0])]
    if not check_one("...the body's straight after the bone", onto):
        return
    told = _then(onto[0])
    reads = {t for n in told for t in _fed_by(n, "Location")}
    check("...and the blood is told after it (Multicast_PelletHit), where HitPoint says",
          len(told) == 1 and _title(told[0]).replace(" ", "").replace("_", "") == "MulticastPelletHit"
          and reads == {f"Get {HIT_POINT_VAR}"},
          f"{[_title(n) for n in told]} at {reads}")


def check_one(label, nodes):
    check(label, len(nodes) == 1, f"{len(nodes)} node(s)")
    return len(nodes) == 1


def run():
    check_bodies_fit_the_model()
    check_body_miss_is_a_miss()
