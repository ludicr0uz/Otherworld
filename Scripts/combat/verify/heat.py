"""verify.heat -- the heated blade (combat/heat.py, weapon_component/heat.py,
cauterize.py, hot_blow.py): who Heats, the glow's material and each item's
instance of it, the cooling and the glow on the item's own Tick, the interact
key's campfire kind, the use key's cauterising, and the doubled blow on a
creature afraid of fire.
"""

import unreal

from combat.axe import AXE_SCALE
from combat.axe import HOT_AXIS as AXE_AXIS
from combat.axe import HOT_FADE_CM as AXE_FADE_CM
from combat.axe import HOT_START_CM as AXE_START_CM
from combat.heat_tuning import (
    BLOW_DAMAGE_VAR, COOL_VAR, FIRE_FEAR_TAG, HEAT_GLOW, HEAT_MATERIAL_VAR,
    HEAT_S, HEATS_VAR, HOT_AXIS_PARAM, HOT_BLOW_SCALE, HOT_FADE_PARAM,
    HOT_START_PARAM, HOT_VAR, MODEL,
)
from combat.knife import HOT_AXIS as KNIFE_AXIS
from combat.knife import HOT_FADE as KNIFE_FADE
from combat.knife import HOT_START as KNIFE_START
from combat.light_tuning import CAMPFIRE_CLASS_VAR
from combat.paths import (
    AXE_BP_PATH, ITEM_BP_PATH, KNIFE_BP_PATH, MAT_HOT_AXE, MAT_HOT_KNIFE,
    MAT_HOT_METAL, WEAPON_DIR,
)
from combat.tuning import BLEEDING_TAG, COMBAT
from combat.use_tuning import USE_PRESSED_VAR
from combat.verify.chop import _pure_feeds, _ran_by
from combat.verify.common import (
    take_hits,
    BEL, by_pins, cdo, check, component_template, graph, load, num_pin, pin_value,
)
from combat.verify.fixtures import w, wg
from combat.verify.glimmer import is_glimmer_node
from combat.verify.interact import _then
from combat.fire_vars import (
    FIRE_PARAM, HEAT_REACH_CM, SERVER_CAUTERIZE, SERVER_HEAT)
from combat.verify.punch import _feeders, _feeds, _title
from combat.verify.record import _upstream
from combat.verify.shot import _asked_above, _calls_of, _event
from combat.weapon_component.interact import INTERACT_TARGET_VAR
from combat.weapon_specs import _weapon_specs
from survival.paths import SURVIVAL_DIR

MEL = unreal.MaterialEditingLibrary

# (name, Blueprint, its instance of the glow, axis, start, fade): the last
# three in the model component's own units.
HEATED = (
    ("knife", KNIFE_BP_PATH, MAT_HOT_KNIFE, KNIFE_AXIS, KNIFE_START, KNIFE_FADE),
    ("axe", AXE_BP_PATH, MAT_HOT_AXE, AXE_AXIS, AXE_START_CM / AXE_SCALE,
     AXE_FADE_CM / AXE_SCALE),
)
# Every other item: none of them Heats.
OTHERS = ([ITEM_BP_PATH] + [s["path"] for s in _weapon_specs()]
          + [f"{WEAPON_DIR}/{n}" for n in ("BP_Wood", "BP_Matches", "BP_Stick")]
          + [f"{SURVIVAL_DIR}/{n}" for n in ("BP_Mushroom", "BP_WaterCanteen")])


def _false(node, pin):
    # A literal equal to its pin's default reads "" once loaded from disk.
    return pin_value(node, pin) in ("false", "") and not _feeders(node, pin)


def _sets(nodes, var):
    return [n for n in nodes if _title(n) == f"Set {var}"]


def _names(nodes):
    return {_title(n) for n in nodes}


def _squash(node):
    return _title(node).replace(" ", "").lower()


def _gates(node, limit=6):
    """The Branches a node sits behind: up its exec chain, ``limit`` steps."""
    found, todo = [], [(node, 0)]
    while todo:
        n, depth = todo.pop()
        for up in _ran_by(n):
            if _title(up) == "Branch":
                found.append(up)
            if depth + 1 < limit:
                todo.append((up, depth + 1))
    return found


def check_hot_material():
    mat = load(MAT_HOT_METAL)
    check("M_HotMetal exists", mat is not None)
    if mat is None:
        return
    check("...an unlit additive overlay, so it only adds light and adds none "
          "where its mask is zero; usable on a skeletal mesh (the knife's)",
          mat.get_editor_property("blend_mode") == unreal.BlendMode.BLEND_ADDITIVE
          and mat.get_editor_property("shading_model") == unreal.MaterialShadingModel.MSM_UNLIT
          and mat.get_editor_property("used_with_skeletal_mesh") is True,
          f"{mat.get_editor_property('blend_mode')} {mat.get_editor_property('shading_model')}")
    scalars = {str(n) for n in MEL.get_scalar_parameter_names(mat)}
    vectors = {str(n) for n in MEL.get_vector_parameter_names(mat)}
    check(f"...masked by {HOT_AXIS_PARAM}, {HOT_START_PARAM} and {HOT_FADE_PARAM}",
          {HOT_START_PARAM, HOT_FADE_PARAM} <= scalars and HOT_AXIS_PARAM in vectors,
          f"{sorted(scalars)} {sorted(vectors)}")


def check_heated_items():
    for name, path, mi_path, axis, start, fade in HEATED:
        bp = load(path)
        if bp is None:
            check(f"the {name} exists", False)
            continue
        d = cdo(bp)
        cool = d.get_editor_property(COOL_VAR)
        check(f"the {name} {HEATS_VAR} and starts cold",
              d.get_editor_property(HEATS_VAR) is True
              and d.get_editor_property(HOT_VAR) is False
              and isinstance(cool, float) and cool == 0.0, f"{COOL_VAR}={cool!r}")
        mi = d.get_editor_property(HEAT_MATERIAL_VAR)
        got_axis = MEL.get_material_instance_vector_parameter_value(mi, HOT_AXIS_PARAM) if mi else None
        got = ((round(got_axis.r, 3), round(got_axis.g, 3), round(got_axis.b, 3)),
               round(MEL.get_material_instance_scalar_parameter_value(mi, HOT_START_PARAM), 2),
               round(MEL.get_material_instance_scalar_parameter_value(mi, HOT_FADE_PARAM), 2)
               ) if mi else None
        check(f"...its {HEAT_MATERIAL_VAR} an instance of M_HotMetal that says "
              "where its metal is",
              mi is not None and mi == load(mi_path)
              and mi.get_editor_property("parent") == load(MAT_HOT_METAL)
              and got == (tuple(round(a, 3) for a in axis), round(start, 2), round(fade, 2)),
              f"{mi.get_name() if mi else None} {got}")
        model, glow = component_template(bp, MODEL), component_template(bp, HEAT_GLOW)
        check(f"...its model wearing no overlay until it is hot, and {HEAT_GLOW} "
              "a point light hidden until then, casting no shadow",
              model is not None and model.get_editor_property("overlay_material") is None
              and isinstance(glow, unreal.PointLightComponent)
              and glow.get_editor_property("visible") is False
              and glow.get_editor_property("cast_shadows") is False)
        _check_cooling(name, graph(bp).list_all_nodes())
    heaters = [p.rsplit("/", 1)[-1] for p in OTHERS
               if load(p) is None or cdo(load(p)).get_editor_property(HEATS_VAR) is not False]
    check(f"nothing else {HEATS_VAR}", not heaters, str(heaters))


def _check_cooling(name, nodes):
    colds = _sets(nodes, HOT_VAR)
    check(f"the {name} cools itself, in one place",
          len(colds) == 1 and _false(colds[0], HOT_VAR), str(len(colds)))
    if len(colds) == 1:
        gates = _ran_by(colds[0])
        src = _pure_feeds(gates[0]) if len(gates) == 1 else []
        check(f"...on its Tick, once it is {HOT_VAR} and the clock has reached "
              f"{COOL_VAR}, on the server's copy alone (IsServer: a client's is told)",
              {f"Get {HOT_VAR}", f"Get {COOL_VAR}"} <= _names(src)
              and any("isserver" in _squash(n) for n in src)
              and any("gettimeseconds" in _squash(n) for n in src)
              and any("ReceiveTick" in str(n.get_name()) or "Tick" in _title(n)
                      for g in gates for n in _ran_by(g)),
              str(sorted(_names(src))))
    wears = by_pins(nodes, "NewOverlayMaterial")
    on = [n for n in wears
          if [_title(f) for f in _feeders(n, "NewOverlayMaterial")] == [f"Get {HEAT_MATERIAL_VAR}"]]
    off = [n for n in wears if not _feeders(n, "NewOverlayMaterial")]
    arms = {}
    for label, group in (("on", on), ("off", off)):
        for n in group:
            for up in _ran_by(n):
                if _title(up) == "Branch" and [_title(f) for f in _feeders(up, "Condition")] == [f"Get {HOT_VAR}"]:
                    arms[label] = n in _then(up)
    check(f"...its {MODEL} wears {HEAT_MATERIAL_VAR} as its overlay while {HOT_VAR}, "
          "and none while not",
          len(on) == 1 and len(off) == 1 and len(wears) == 2
          and all([_title(f) for f in _feeders(n, "self")] == [f"Get {MODEL}"] for n in wears)
          and arms == {"on": True, "off": False}, f"{len(on)} on, {len(off)} off, {arms}")
    shows = [n for n in by_pins(nodes, "bNewVisibility") if not is_glimmer_node(n)]
    check(f"...and {HEAT_GLOW} shows while it is {HOT_VAR}",
          len(shows) == 1
          and [_title(f) for f in _feeders(shows[0], "self")] == [f"Get {HEAT_GLOW}"]
          and [_title(f) for f in _feeders(shows[0], "bNewVisibility")] == [f"Get {HOT_VAR}"],
          str(len(shows)))


def check_heat_at_fire():
    # The Branch that keeps a candidate, asking Heats of the held item...
    # (Server_Heat's own Branch on Heats keeps nothing: it is checked below.)
    offers = [n for n in wg if _title(n) == "Branch"
              and f"Get {HEATS_VAR}" in _names(_pure_feeds(n))
              and _event(SERVER_HEAT) not in _upstream(n)]
    # ...run by a Branch on IsValid(Held), itself the body of a loop...
    held_first = [g for o in offers for g in _ran_by(o) if _title(g) == "Branch"
                  and any("isvalid" in _squash(f) for f in _feeders(g, "Condition"))]
    loops = [l for g in held_first for l in _ran_by(g)]
    # ...over the campfires.
    walks = [n for l in loops for n in _feeders(l, "Array")
             if [_title(f) for f in _feeders(n, "ActorClass")] == [f"Get {CAMPFIRE_CLASS_VAR}"]]
    keeps = [n for o in offers for n in _then(o) if _title(n) == f"Set {INTERACT_TARGET_VAR}"]
    check(f"the interact key offers every {CAMPFIRE_CLASS_VAR} actor while the "
          f"held item {HEATS_VAR}, asked only once Held is known valid",
          len(offers) == 1 and len(held_first) == 1 and len(walks) == 1
          and len(keeps) == 1,
          f"{len(walks)} walk(s), {len(offers)} offer(s), "
          f"{len(held_first)} IsValid gate(s), {len(keeps)} keep(s)")

    # A client's picture is told its row's Hot (view.py): that Set is fed.
    writes = [n for n in _sets(wg, HOT_VAR) if not _feeders(n, HOT_VAR)]
    hots = [n for n in writes if pin_value(n, HOT_VAR) == "true"]
    cools = _sets(wg, COOL_VAR)
    check(f"one place makes the held item {HOT_VAR}, and the component never "
          "cools it (the item does)",
          len(hots) == 1 and len(writes) == 1 and len(cools) == 1,
          f"{len(hots)} heat(s), {len(writes)} write(s), {len(cools)} {COOL_VAR}")
    if len(hots) != 1 or len(cools) != 1:
        return
    src = _pure_feeds(cools[0])
    check(f"...until {COOL_VAR}, {HEAT_S:g} s on from the press",
          _ran_by(hots[0]) == cools
          and any(num_pin(n, "B") == HEAT_S for n in src)
          and any("gettimeseconds" in _squash(n) for n in src),
          str(sorted(_names(src))))
    event = _event(SERVER_HEAT)
    gates = [g for g in _upstream(cools[0]) if _title(g) == "Branch"]
    is_fire = [g for g in gates if "classischildof" in {_squash(n) for n in _pure_feeds(g)}]
    fire_src = _pure_feeds(is_fire[0]) if len(is_fire) == 1 else []
    asked = _asked_above(cools[0])
    check(f"...in {SERVER_HEAT}(Fire): only when Fire is there, a {CAMPFIRE_CLASS_VAR} "
          f"within {HEAT_REACH_CM:g} cm of this machine's copy of the owner, the owner "
          f"alive and this machine's Held there and one that {HEATS_VAR}",
          bool(event) and event in _upstream(cools[0]) and len(is_fire) == 1
          and f"Get {CAMPFIRE_CLASS_VAR}" in _names(fire_src)
          and any(num_pin(n, "B") == HEAT_REACH_CM for n in fire_src)
          and any("getowner" in _squash(n) for n in fire_src)
          and {"Dead", "Health", "Held", HEATS_VAR} <= asked,
          f"{len(is_fire)} class test(s), {sorted(_names(fire_src))}, {sorted(asked)}")
    calls = _calls_of(SERVER_HEAT)
    above = _gates(calls[0], limit=2) if len(calls) == 1 else []
    reads = {t for g in above for t in _names(_pure_feeds(g))}
    check(f"...asked for with the kept target when its class is a {CAMPFIRE_CLASS_VAR} "
          "and Held is valid: the key's arm heats nothing itself",
          len(calls) == 1
          and [_title(f) for f in _feeders(calls[0], FIRE_PARAM)] == [f"Get {INTERACT_TARGET_VAR}"]
          and {f"Get {CAMPFIRE_CLASS_VAR}", f"Get {INTERACT_TARGET_VAR}", "Get Held"} <= reads,
          f"{len(calls)} call(s), {sorted(reads)}")


def check_cauterize():
    seals = [n for n in by_pins(wg, "Tags")
             if "removeactiveeffectswithgrantedtags" in _squash(n)]
    check("one node takes effects off the player by the tag they grant",
          len(seals) == 1, str(len(seals)))
    if len(seals) != 1:
        return
    check(f"...the ones granting {BLEEDING_TAG}: the bleed",
          f'TagName="{BLEEDING_TAG}"' in pin_value(seals[0], "Tags"),
          pin_value(seals[0], "Tags"))
    event = _event(SERVER_CAUTERIZE)
    asked = _asked_above(seals[0])
    check(f"...in {SERVER_CAUTERIZE}: the owner alive, this machine's Held there and "
          f"{HOT_VAR}, off an ability system known valid",
          bool(event) and event in _upstream(seals[0])
          and {"Dead", "Health", "Held", HOT_VAR} <= asked
          and any("getabilitysystemcomponent" in _squash(f)
                  for f in _feeders(seals[0], "self")), str(sorted(asked)))
    calls = _calls_of(SERVER_CAUTERIZE)
    reads = ({t for g in _gates(calls[0], limit=2) for t in _names(_pure_feeds(g))}
             if len(calls) == 1 else set())
    check(f"...asked for by a press of the use key ({USE_PRESSED_VAR}) with a {HOT_VAR} "
          "item in hand: the key's arm seals nothing itself",
          {f"Get {USE_PRESSED_VAR}", f"Get {HOT_VAR}"} <= reads, str(sorted(reads)))


def check_hot_blow():
    start = w.get_editor_property(BLOW_DAMAGE_VAR)
    check(f"{BLOW_DAMAGE_VAR} is a real", isinstance(start, float), repr(start))
    marks = _sets(wg, BLOW_DAMAGE_VAR)
    hot = COMBAT.knife_damage * HOT_BLOW_SCALE
    seared = [n for n in marks if num_pin(n, BLOW_DAMAGE_VAR) == hot]
    check(f"a hot blade's blow takes {HOT_BLOW_SCALE:g} times the knife's "
          f"{COMBAT.knife_damage:.0f} HP: {hot:.0f}",
          len(marks) == 2 and len(seared) == 1 and HOT_BLOW_SCALE == 2.0,
          f"{[num_pin(n, BLOW_DAMAGE_VAR) for n in marks]}")
    if len(seared) != 1:
        return
    gates = _gates(seared[0], limit=3)
    tagged = [g for g in gates
              if any("actorhastag" in _squash(f) and pin_value(f, "Tag") == FIRE_FEAR_TAG
                     for f in _feeders(g, "Condition"))]
    body = [f for g in tagged for t in _feeders(g, "Condition") for f in _feeders(t, "self")]
    check(f"...only off a body tagged {FIRE_FEAR_TAG} (a creature afraid of "
          "fire), the one the sweep met",
          len(tagged) == 1 and len(body) == 1
          and "HitActor" in {str(unreal.BlueprintGraphPinLibrary.get_pin_name(p)).replace(" ", "")
                             for p in BEL.list_output_pins(body[0])},
          f"{len(tagged)} tag test(s)")
    reads = [[_title(f) for f in _feeders(g, "Condition")] for g in gates]
    check(f"...with a {HOT_VAR} item in hand, {HOT_VAR} read on a Branch of its "
          "own behind IsValid(Held)",
          [f"Get {HOT_VAR}"] in reads
          and any(len(r) == 1 and "isvalid" in r[0].replace(" ", "").lower() for r in reads),
          str(reads))
    writes = [n for n in take_hits(wg)
              if any(_title(f) == f"Get {BLOW_DAMAGE_VAR}"
                     for f in _feeds(BEL.find_input_pin(n, "Amount")))]
    check("...and the health is taken (TakeHit) after it, on every way out of the test",
          len(writes) == 1 and seared[0] in _ran_by(writes[0])
          and len(_ran_by(writes[0])) == 4, f"{len(writes)} write(s)")


def run():
    check_hot_material()
    check_heated_items()
    check_heat_at_fire()
    check_cauterize()
    check_hot_blow()
