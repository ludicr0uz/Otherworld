"""The skin under a worn garment is cut out of the body, so it never shows
through the jeans or the hoodie as the body moves (asset_pipeline/
body_cover.py: the body's material is Masked by T_BodyCoverMask, a scalar
parameter per part; combat/weapon_component/wear_draw.py sets it).

    python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_clothing_cut.py

1. As the game starts, each part's parameter on the body's materials is 1
   exactly when that part draws a garment (the issued pants among them).
2. The jacket and the pants, each worn (probes/dressed.py) if it is not:
   its part's parameter is 1 on every material of the body, the rest as
   drawn.
3. Each taken off (TakeOff, as the I panel raises it): its part's parameter
   is 0 again, and the skin there is whole.

A parameter never set reads 0 (the material's default): a material that is
not yet a dynamic instance has had none set. Whether the pixels are cut is
the material's (verify/wear_draw.check_body_cut); a headless game draws
none. Any profile on disk is set aside first, and put back at the end.
"""

LEVEL = "/Game/Maps/Lvl_Forest_200m"  # the test garments lie here; the MetaHuman player
SYSTEMS = ('clothing',)

import os
import shutil

import unreal

from asset_pipeline.metahuman_paths import CLOTHING, COVER_PARTS
from clothing.specs import GARMENTS
from combat.metahuman_body import BODY
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.wear_tuning import NOT_CLOTHING, TAKE_OFF_VAR, WORN_VAR
from graphics_menu.profile_consts import PROFILE_CHECKED_VAR, PROFILE_SLOT
from probes import dressed
from probes.dressed import drawn, part, put_on, still

WRITABLE = dressed.WRITABLE + [(WEAPON_COMP_BP_PATH, TAKE_OFF_VAR)]
GARMENTS_CUT = ("Jacket", "Pants")


def _file():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames", f"{PROFILE_SLOT}.sav")


def _live_hud(p):
    try:
        hud = p.hud()
    except Exception:
        return None
    return hud if hud is not None and p.get(hud, PROFILE_CHECKED_VAR) else None


def _body(player):
    return next(c for c in player.get_components_by_class(unreal.SkeletalMeshComponent)
                if c.get_name() == BODY)


def _cuts(body, name):
    """The parameter on each of the body's materials (0 where none is set)."""
    got = []
    for i in range(body.get_num_materials()):
        m = body.get_material(i)
        got.append(round(m.get_scalar_parameter_value(name), 3)
                   if isinstance(m, unreal.MaterialInstanceDynamic) else 0.0)
    return got


def _drawn_parts(player):
    shown = {}
    for g in GARMENTS:
        if g.worn and g.worn[0] in CLOTHING:
            shown[g.worn[0]] = drawn(part(player, g.display), g.display)
    return shown


def _matches(player):
    """{part: (drawn, cuts)}, and whether every part is cut exactly when drawn."""
    body, shown = _body(player), _drawn_parts(player)
    seen = {n: (shown[n], _cuts(body, n)) for n in COVER_PARTS}
    ok = all(all(c == (1.0 if d else 0.0) for c in cuts) for d, cuts in seen.values())
    return ok, seen


def _spec(display):
    return next(g for g in GARMENTS if g.display == display)


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    held = []
    try:
        yield from _run(p, held)
    finally:
        still(p, held, False)
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _run(p, held):
    yield lambda: _live_hud(p) is not None
    player = p.pawn()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    still(p, held, True)
    yield 0.3
    body = _body(player)
    p.check(f"the body ({BODY}) has materials to cut", body.get_num_materials() > 0,
            str(body.get_num_materials()))
    ok, seen = _matches(player)
    p.check("as the game starts, each part's skin is cut exactly when a garment is drawn "
            "there", ok, str(seen))
    for display in GARMENTS_CUT:
        spec = _spec(display)
        name = spec.worn[0]
        worn = list(p.get(wc, WORN_VAR))
        item = worn[spec.slot_index] if spec.slot_index < len(worn) else None
        if item is None or not drawn(part(player, display), display):
            item = yield from put_on(p, player, wc, display)
        p.check(f"{display} worn: drawn on {name}",
                item is not None and drawn(part(player, display), display))
        if item is None:
            continue
        yield 0.2
        ok, seen = _matches(player)
        p.check(f"...and the skin under it is cut: {name} is 1 on every material of the "
                f"body, the other parts as drawn",
                ok and seen[name][1] and all(c == 1.0 for c in seen[name][1]), str(seen))
        p.set(wc, TAKE_OFF_VAR, spec.slot_index)
        yield lambda: p.get(wc, TAKE_OFF_VAR) == NOT_CLOTHING
        yield 0.2
        ok, seen = _matches(player)
        p.check(f"taken off, {name} is bare and its skin whole again (0)",
                ok and not seen[name][0] and all(c == 0.0 for c in seen[name][1]), str(seen))
