"""Corpse loot: a killed wanderer carries its roll, every body can be searched,
and the loot window shows the roll as icons and takes it; searching kneels.

The table's 50% is forced per wanderer by writing its LootChances (1.0, then
0.0), so each case is decided rather than a coin toss; the default table is
read first. Kills are Health = 0 with DamagedByPlayer set, as a shot leaves
them. The window is opened and the take asked for by writing the HUD's
LootOpen / LootTakeRequested (a probe has no keyboard; the verifier checks the
Tab / Enter polls).

Cases, each at a fresh spot (the player is moved to the next wanderer, so the
body in reach is the one just made):
  an unlucky kill carries nothing and is found all the same; its window says
    NOTHING and a take does nothing; while the window is open the player
    kneels (Searching, PoseKneel, the hips down, move input ignored) and
    stands again when it shuts;
  a lucky kill carries a canteen, shown as its icon in its tint and not as a
    name; taking puts a carried canteen in the bag and empties the body, which
    stays the target with the window open on NOTHING;
  a death nobody caused (no DamagedByPlayer, as the world-floor net) carries
    nothing even at 100%, and can be searched too.

Any profile on disk is set aside first, so the game starts on the issued
loadout, and put back at the end.
"""

import os
import shutil

import unreal

from combat.paths import (
    HEALTH_BP_PATH, HEALTH_CLASS_PATH, WEAPON_COMP_CLASS_PATH,
)
from graphics_menu import umg_consts as C
from combat.body_pose import KNEEL_FROM_S, KNEEL_TIME, KNEEL_TO_S, POSE_KNEEL
from combat.skin import skin_of_mesh
from combat.weapon_component.pose_weights import SEARCHING_VAR
from graphics_menu.loot_consts import (
    LOOT_EMPTY, LOOT_KNEELING_VAR, LOOT_OPEN_VAR, LOOT_PANEL, LOOT_PROMPT, LOOT_ROWS_BOX,
    LOOT_TAKE_VAR, LOOT_TARGET_VAR,
)
from graphics_menu.profile_consts import PROFILE_CHECKED_VAR, PROFILE_SLOT
from loot.consts import (
    LOOT_CHANCES_VAR, LOOT_ICONS_VAR, LOOT_NAMES_VAR, LOOT_TABLE_VAR, LOOT_TINTS_VAR,
    LOOT_VAR,
)
from combat import health_vars as HV
from combat.game_state import DAMAGED_BY_PLAYER_VAR

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = [(HEALTH_BP_PATH, HV.Health), (HEALTH_BP_PATH, DAMAGED_BY_PLAYER_VAR),
            (HEALTH_BP_PATH, LOOT_CHANCES_VAR),
            (HUD_BP_PATH, LOOT_OPEN_VAR), (HUD_BP_PATH, LOOT_TAKE_VAR)]
CANTEEN = "BP_WaterCanteen_C"
IN_FRONT_CM = 150.0
BESIDE_CM = 90.0          # where the player stands to search: beside the body
SETTLE = 0.3
SHOWN = unreal.SlateVisibility.HIT_TEST_INVISIBLE
HIDDEN = unreal.SlateVisibility.COLLAPSED


def _file():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames",
                        f"{PROFILE_SLOT}.sav")


def _live_hud(p):
    try:
        hud = p.hud()
    except Exception:
        return None
    return hud if hud is not None and p.get(hud, PROFILE_CHECKED_VAR) else None


def _wanderers(p):
    ctrls = unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.AIController)
    pawns = [c.get_controlled_pawn() for c in ctrls
             if "ForestWandererAI" in c.get_class().get_name()]
    return [x for x in pawns if x is not None
            and not p.get(p.component(x, HEALTH_CLASS_PATH), "Dead")]


def _kill(p, npc, chance, by_player=True):
    """Stand the player where ``npc`` is and ``npc`` in front of it, force its
    roll, kill it, and step up to where the ragdoll came to rest (it can
    slide a couple of metres down a slope, out of reach); returns its health
    component."""
    player = p.pawn()
    player.set_actor_location(npc.get_actor_location() + unreal.Vector(0, 0, 10),
                              False, True)
    spot = player.get_actor_location() + player.get_actor_forward_vector() * IN_FRONT_CM
    npc.set_actor_location(spot, False, True)
    health = p.component(npc, HEALTH_CLASS_PATH)
    p.set(health, LOOT_CHANCES_VAR, [chance])
    p.set(health, "DamagedByPlayer", by_player)
    p.set(health, "Health", 0.0)
    yield lambda: p.get(health, "Dead")
    mesh = npc.get_component_by_class(unreal.SkeletalMeshComponent)
    yield 1.0
    rest = mesh.get_world_location()
    player.set_actor_location(rest + unreal.Vector(-BESIDE_CM, 0.0, 100.0), False, True)
    yield SETTLE
    return health


def _names(p, health):
    return [str(n) for n in p.get(health, LOOT_NAMES_VAR)]


def _widgets(p, hud):
    ui = p.get(hud, "UiHud")
    return {n: ui.get_editor_property(n)
            for n in (LOOT_PROMPT, LOOT_PANEL, LOOT_ROWS_BOX, LOOT_EMPTY)}


def _draw(hud):
    """DrawHUD by hand (a -nullrhi run never draws, see probe_umg_screens)."""
    hud.call_method("ReceiveDrawHUD", (1920, 1080))


def _check_empty_window(p, hud, wc):
    """A body with nothing on it: shut, the prompt; open, NOTHING and no row;
    a take leaves the bag alone."""
    w = _widgets(p, hud)
    _draw(hud)
    p.check("an empty body, shut: the prompt to search it",
            w[LOOT_PROMPT].get_visibility() == SHOWN
            and w[LOOT_PANEL].get_visibility() == HIDDEN,
            f"{w[LOOT_PROMPT].get_visibility()} {w[LOOT_PANEL].get_visibility()}")
    p.set(hud, LOOT_OPEN_VAR, True)
    _draw(hud)
    first = w[LOOT_ROWS_BOX].get_child_at(0)
    p.check("...open: the window says NOTHING and shows no row",
            w[LOOT_PANEL].get_visibility() == SHOWN
            and w[LOOT_EMPTY].get_visibility() == SHOWN
            and first.get_visibility() == HIDDEN,
            f"{w[LOOT_PANEL].get_visibility()} {w[LOOT_EMPTY].get_visibility()} "
            f"{first.get_visibility()}")
    before = _bag(p, wc)
    p.set(hud, LOOT_TAKE_VAR, True)
    yield lambda: not p.get(hud, LOOT_TAKE_VAR)
    yield SETTLE
    p.check("...and a take from it does nothing", _bag(p, wc) == before
            and p.get(hud, LOOT_OPEN_VAR), f"{before} -> {_bag(p, wc)}")


def _hips(player):
    mesh = player.get_editor_property("mesh")
    capsule = player.get_component_by_class(unreal.CapsuleComponent)
    ground = player.get_actor_location().z - capsule.get_scaled_capsule_half_height()
    hips = skin_of_mesh(mesh.get_skeletal_mesh_asset().get_path_name()).pose_bones["hips"]
    return mesh.get_socket_location(hips).z - ground


def _check_kneel(p, hud, wc, stand_hips):
    """The window is open: the player is down on a knee and held there; shut,
    it stands and walks again."""
    player = p.pawn()
    pc = player.get_controller()
    mesh = player.get_editor_property("mesh")
    anim = mesh.get_anim_instance()
    yield lambda: p.get(wc, SEARCHING_VAR)
    p.check("the open window is Searching, and the controller ignores move input",
            p.get(wc, SEARCHING_VAR) and p.get(hud, LOOT_KNEELING_VAR)
            and pc.is_move_input_ignored(),
            f"searching={p.get(wc, SEARCHING_VAR)} ignored={pc.is_move_input_ignored()}")
    worn = mesh.get_skeletal_mesh_asset().get_path_name().split(".")[0]
    kneels = getattr(skin_of_mesh(worn), "search_kneel", None) is not None
    if kneels:
        yield lambda: p.get(anim, POSE_KNEEL) > 0.98
        yield SETTLE
        low, at = _hips(player), p.get(anim, KNEEL_TIME)
        p.check("...the body kneels: PoseKneel arrives, the hips come down at "
                "least 35 cm, the clip held inside its working stretch",
                stand_hips - low >= 35.0 and KNEEL_FROM_S <= at <= KNEEL_TO_S,
                f"hips {stand_hips:.0f} -> {low:.0f}, clip at {at:.2f} s")
    else:
        p.note(f"wearing {worn}: no kneel clip on this rig, the search is made standing")
    yield 1.0
    p.check("...and stays ignored once, however long the window is open (one "
            "SetIgnoreMoveInput per change)", pc.is_move_input_ignored())
    p.set(hud, LOOT_OPEN_VAR, False)
    yield lambda: not p.get(wc, SEARCHING_VAR)
    yield SETTLE
    p.check("shut: no longer Searching, and the walk is given back",
            not p.get(hud, LOOT_KNEELING_VAR) and not pc.is_move_input_ignored(),
            f"ignored={pc.is_move_input_ignored()}")
    if kneels:
        yield lambda: p.get(anim, POSE_KNEEL) < 0.02
        yield SETTLE
        up = _hips(player)
        p.check("...and the body stands again", abs(up - stand_hips) < 8.0,
                f"hips {up:.0f} (stood at {stand_hips:.0f})")


def _check_window(p, hud, body):
    """Shut, the prompt; open, the panel showing the canteen as its icon, in
    its tint, on the caret's row, and no name."""
    w = _widgets(p, hud)
    _draw(hud)
    p.check("shut, the window shows only its prompt",
            w[LOOT_PROMPT].get_visibility() == SHOWN
            and w[LOOT_PANEL].get_visibility() == HIDDEN,
            f"{w[LOOT_PROMPT].get_visibility()} {w[LOOT_PANEL].get_visibility()}")
    p.set(hud, LOOT_OPEN_VAR, True)
    _draw(hud)
    rows = w[LOOT_ROWS_BOX]
    first, second = rows.get_child_at(0), rows.get_child_at(1)
    icon = first.get_editor_property(C.ROW_ICON)
    drawn = icon.get_editor_property("brush").get_editor_property("resource_object")
    want = list(p.get(body, LOOT_ICONS_VAR))[0]
    tint = list(p.get(body, LOOT_TINTS_VAR))[0]
    p.check("open, the panel shows the canteen's icon in its colour, caret on it, "
            "and no other row",
            w[LOOT_PANEL].get_visibility() == SHOWN
            and w[LOOT_PROMPT].get_visibility() == HIDDEN
            and w[LOOT_EMPTY].get_visibility() == HIDDEN
            and first.get_visibility() == SHOWN and icon.get_visibility() == SHOWN
            and drawn is not None and drawn == want and "Canteen" in drawn.get_name()
            and icon.get_editor_property("color_and_opacity").to_tuple() == tint.to_tuple()
            and first.get_editor_property(C.ROW_CARET).get_render_opacity() == 1.0
            and second.get_visibility() == HIDDEN,
            f"{drawn.get_name() if drawn else None} {icon.get_visibility()} "
            f"{second.get_visibility()}")
    value = str(first.get_editor_property(C.ROW_VALUE).get_text())
    p.check("...an icon rather than text: the row writes no name", value == "",
            repr(value))


def _bag(p, wc):
    return [i.get_class().get_name() for i in p.get(wc, "Inventory")]


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _run(p):
    yield lambda: _live_hud(p) is not None and len(_wanderers(p)) >= 3
    hud = _live_hud(p)
    player = p.pawn()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    first, second, third = _wanderers(p)[:3]
    # A headless game renders nothing, and by default an unrendered mesh
    # never refreshes its bones (the kneel is measured off them).
    player.get_editor_property("mesh").set_editor_property(
        "visibility_based_anim_tick_option",
        unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES,
        unreal.PropertyAccessChangeNotifyMode.NEVER)

    table = p.component(first, HEALTH_CLASS_PATH)
    items = [c.get_name() for c in p.get(table, LOOT_TABLE_VAR)]
    chances = [round(float(c), 3) for c in p.get(table, LOOT_CHANCES_VAR)]
    p.check("a live wanderer's loot table is water at 50%",
            items == [CANTEEN] and chances == [0.5], f"{items} {chances}")
    p.check("no body in reach: nothing to search, standing",
            p.get(hud, LOOT_TARGET_VAR) is None and not p.get(wc, SEARCHING_VAR))

    # --- an unlucky kill: nothing on it, searched all the same ------------------
    body = yield from _kill(p, first, 0.0)
    stand_hips = _hips(player)
    p.check("an unlucky kill carries nothing", len(p.get(body, LOOT_VAR)) == 0,
            str(_names(p, body)))
    yield lambda: p.get(hud, LOOT_TARGET_VAR) == body
    p.check("...and the HUD finds its body all the same",
            p.get(hud, LOOT_TARGET_VAR) == body)
    yield from _check_empty_window(p, hud, wc)
    yield from _check_kneel(p, hud, wc, stand_hips)

    # --- a lucky kill ---------------------------------------------------------
    body = yield from _kill(p, second, 1.0)
    p.check("a lucky counted kill carries a canteen",
            [c.get_name() for c in p.get(body, LOOT_VAR)] == [CANTEEN]
            and _names(p, body) == ["Canteen"], str(_names(p, body)))
    yield lambda: p.get(hud, LOOT_TARGET_VAR) == body
    p.check("the HUD finds the body in reach", p.get(hud, LOOT_TARGET_VAR) == body)

    _check_window(p, hud, body)

    before = _bag(p, wc)
    held = p.get(wc, "Held")
    p.set(hud, LOOT_TAKE_VAR, True)
    yield lambda: not p.get(hud, LOOT_TAKE_VAR)
    yield SETTLE
    after = _bag(p, wc)
    p.check("taking puts the canteen in the bag",
            after.count(CANTEEN) == before.count(CANTEEN) + 1
            and len(after) == len(before) + 1, f"{before} -> {after}")
    taken = [i for i in p.get(wc, "Inventory") if i.get_class().get_name() == CANTEEN]
    p.check("...carried, not lying in the world",
            bool(taken) and all(not p.get(i, "Dropped") for i in taken))
    p.check("...the held item stays held", p.get(wc, "Held") == held)
    p.check("...and the body is emptied, icons and tints with it",
            all(len(p.get(body, v)) == 0
                for v in (LOOT_VAR, LOOT_NAMES_VAR, LOOT_ICONS_VAR, LOOT_TINTS_VAR)),
            str(_names(p, body)))
    _draw(hud)
    w = _widgets(p, hud)
    p.check("the emptied body is still the one being searched: the window stays "
            "open, on NOTHING",
            p.get(hud, LOOT_TARGET_VAR) == body and p.get(hud, LOOT_OPEN_VAR)
            and w[LOOT_EMPTY].get_visibility() == SHOWN
            and w[LOOT_ROWS_BOX].get_child_at(0).get_visibility() == HIDDEN,
            f"{p.get(hud, LOOT_TARGET_VAR)} open={p.get(hud, LOOT_OPEN_VAR)}")
    p.set(hud, LOOT_OPEN_VAR, False)
    yield SETTLE

    # --- a death nobody caused ---------------------------------------------------
    body = yield from _kill(p, third, 1.0, by_player=False)
    p.check("a death nobody caused carries nothing, even at 100%",
            len(p.get(body, LOOT_VAR)) == 0, str(_names(p, body)))
    yield lambda: p.get(hud, LOOT_TARGET_VAR) == body
    p.check("...and can be searched too", p.get(hud, LOOT_TARGET_VAR) == body)
    p.check("the player still walks when the probe ends",
            not player.get_controller().is_move_input_ignored())
