"""verify.blood_sprite -- the splat at a wound (combat/blood_sprite.py): the
flipbook texture, the material that plays it off the spawn time, the card
that faces the camera, and the size the pellet's zone picks (head largest,
then the chest, a limb least). The splat in a running game is
probes/probe_blood_sprite.py.
"""

import unreal

from combat import fx_vars as FX
from combat.blood_sprite_consts import (
    SPLAT_CELL, SPLAT_COMPONENT, SPLAT_GRID, SPLAT_LIFETIME, SPLAT_SPAWN_PARAM, SPLAT_SPAWN_SLOT, splat_scale,
)
from combat.paths import BLOOD_SPRITE_BP_PATH, MAT_BLOOD_SPRITE, PLANE, TEX_BLOOD_SPRITE
from combat.verify import fx as fxv
from combat.verify.common import (
    BEL, PIN, by_pins, check, component_template, graph, load, num_pin,
)
from combat.verify.fixtures import w, wg
from combat.verify.record import _feeders, _title


def _squash(node):
    """A node's title without spaces or case: the editor that authored a call
    titles it one way, one that loaded it from disk may another."""
    return _title(node).replace(" ", "").lower()


def _walk(mat, node):
    """Every expression ``node`` reads, itself included."""
    mel = unreal.MaterialEditingLibrary
    seen, stack = [], [node]
    while stack:
        n = stack.pop()
        if n is None or n in seen:
            continue
        seen.append(n)
        stack.extend(mel.get_inputs_for_material_expression(mat, n))
    return seen


def check_splat_texture():
    tex = load(TEX_BLOOD_SPRITE)
    size = SPLAT_CELL * SPLAT_GRID
    got = (tex.blueprint_get_size_x(), tex.blueprint_get_size_y()) if tex else None
    check(f"T_BloodSprite is the {SPLAT_GRID}x{SPLAT_GRID} flipbook atlas, {size} px square",
          got == (size, size), str(got))
    check("...linear and clamped, so no frame bleeds into the next",
          tex is not None and not tex.get_editor_property("srgb")
          and tex.get_editor_property("address_x") == unreal.TextureAddress.TA_CLAMP)


def check_splat_material():
    mel = unreal.MaterialEditingLibrary
    mat = load(MAT_BLOOD_SPRITE)
    check("M_BloodSprite is masked and two-sided",
          mat.get_editor_property("blend_mode") == unreal.BlendMode.BLEND_MASKED
          and mat.get_editor_property("two_sided"))
    mask = mel.get_material_property_input_node(mat, unreal.MaterialProperty.MP_OPACITY_MASK)
    base = mel.get_material_property_input_node(mat, unreal.MaterialProperty.MP_BASE_COLOR)
    lit = mel.get_material_property_input_node(
        mat, unreal.MaterialProperty.MP_EMISSIVE_COLOR) is None
    check("...lit, its mask the atlas's alpha and its colour fed",
          lit and isinstance(mask, unreal.MaterialExpressionTextureSample) and base is not None
          and mask.get_editor_property("texture") == load(TEX_BLOOD_SPRITE))
    if mask is None:
        return
    read = _walk(mat, mask)
    born = [n for n in read if isinstance(n, unreal.MaterialExpressionScalarParameter)]
    check(f"...the frame picked by the age since {SPLAT_SPAWN_PARAM}, read off the card's "
          f"custom primitive data slot {SPLAT_SPAWN_SLOT}, against the Time node",
          len(born) == 1
          and str(born[0].get_editor_property("parameter_name")) == SPLAT_SPAWN_PARAM
          and born[0].get_editor_property("use_custom_primitive_data")
          and born[0].get_editor_property("primitive_data_index") == SPLAT_SPAWN_SLOT
          and any(isinstance(n, unreal.MaterialExpressionTime) for n in read),
          f"{len(born)} parameter(s)")
    rates = [n.get_editor_property("const_b") for n in read
             if isinstance(n, unreal.MaterialExpressionMultiply)]
    check(f"...over {SPLAT_LIFETIME}s", any(abs(r - 1.0 / SPLAT_LIFETIME) < 1e-4 for r in rates),
          str(rates))


def check_splat_actor():
    bp = load(BLOOD_SPRITE_BP_PATH)
    card = component_template(bp, SPLAT_COMPONENT)
    check(f"BP_BloodSprite's {SPLAT_COMPONENT} is the engine plane in M_BloodSprite, "
          "turned a quarter in pitch to face down the actor's X",
          card is not None and card.get_editor_property("static_mesh") == load(PLANE)
          and list(card.get_editor_property("override_materials")) == [load(MAT_BLOOD_SPRITE)]
          and abs(card.get_editor_property("relative_rotation").pitch - 90.0) < 1e-3)
    check("...casting no shadow and colliding with nothing",
          card is not None and not card.get_editor_property("cast_shadow")
          and str(card.get_collision_profile_name()) == "NoCollision")
    nodes = graph(bp).list_all_nodes()
    life = by_pins(nodes, "InLifespan")
    check(f"...lives {SPLAT_LIFETIME}s", len(life) == 1
          and abs((num_pin(life[0], "InLifespan") or 0.0) - SPLAT_LIFETIME) < 1e-4)
    stamp = by_pins(nodes, "DataIndex", "Value")
    check(f"...stamps the world's time into slot {SPLAT_SPAWN_SLOT} at BeginPlay",
          len(stamp) == 1 and int(num_pin(stamp[0], "DataIndex") or 0) == SPLAT_SPAWN_SLOT
          and [_squash(n) for n in _feeders(stamp[0], "Value")] == ["gettimeseconds"],
          str([_title(n) for n in _feeders(stamp[0], "Value")]) if stamp else "none")
    check("...and turns to the local camera",
          any(_squash(n) == "findlookatrotation" for n in nodes)
          and bool(by_pins(nodes, "NewRotation")))


def _from(node, pin):
    """The names of the pins linked into ``node``'s ``pin``."""
    return [str(PIN.get_pin_name(q))
            for q in PIN.list_connected_pins(BEL.find_input_pin(node, pin))]


def _sizes():
    """(head, limb, chest) as the pellet graph picks them, or None."""
    adds = [n for n in by_pins(wg, "TargetArray", "NewItem")
            if {_title(f) for f in _feeders(n, "TargetArray")} == {f"Get {FX.ShotHitSplats}"}]
    outer = [f for n in adds for f in _feeders(n, "NewItem") if "Select" in _title(f)]
    if len(outer) != 1:
        return None
    inner = [f for f in _feeders(outer[0], "B") if "Select" in _title(f)]
    if len(inner) != 1:
        return None
    if _from(outer[0], "bPickA") != ["bHead"]:
        return None
    if [p for f in _feeders(inner[0], "bPickA") for p in _from(f, "A")] != ["Worth"]:
        return None
    return (num_pin(outer[0], "A"), num_pin(inner[0], "A"), num_pin(inner[0], "B"))


def check_splat_sizes():
    got = _sizes()
    want = (splat_scale(True, 1.0), splat_scale(False, 0.75), splat_scale(False, 1.0))
    check("a pellet's splat is sized by its zone: the head's, else a limb's (Worth under "
          "1), else the chest's, as blood_sprite_consts.splat_scale says",
          got is not None and all(g is not None and abs(g - s) < 1e-4
                                  for g, s in zip(got, want)), f"{got} != {want}")
    check("...the head largest, the chest medium, a limb smallest",
          want[0] > want[2] > want[1])


def check_splat_spawn():
    got = w.get_editor_property("BloodSpriteClass")
    check("BloodSpriteClass points at BP_BloodSprite_C",
          got is not None and got.get_name() == "BP_BloodSprite_C",
          got.get_name() if got else "None")
    spawns = [n for n in by_pins(wg, "Class", "SpawnTransform")
              if [_title(f) for f in _feeders(n, "Class")] == ["Get BloodSpriteClass"]]
    mine = fxv.in_fx(FX.PELLET_HIT, spawns)
    check("Fx_PelletHit spawns the splat once, after the blood", len(mine) == 1
          and [_title(f) for f in _feeders(mine[0], "execute")]
          and any(by_pins([f], "Class") for f in _feeders(mine[0], "execute")),
          f"{len(mine)} splat spawn(s)")
    if len(mine) != 1:
        return
    at = _feeders(mine[0], "SpawnTransform")
    scale = [p for t in at for p in _feeders(t, "Scale")]
    sized = [p for s in scale for p in _from(s, "B")]
    check(f"...sized by the event's {FX.SPLAT_PARAM}", sized == [FX.SPLAT_PARAM], str(sized))


def run():
    check_splat_texture()
    check_splat_material()
    check_splat_actor()
    check_splat_sizes()
    check_splat_spawn()
