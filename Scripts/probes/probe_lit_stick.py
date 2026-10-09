"""The stick: used at a campfire it lights, and a burning one is held out by
the use key, which is the FireWard a wendigo reads.

The player must start carrying BP_Stick, last of the six issued items. The
use key is the sights key with an item that has no sights in hand;
SightsForced stands in for it (no key can be injected into a headless game).

  - with no campfire anywhere, the key lights nothing; held, it is Using and
    does not aim;
  - the fire is lit the way the game lights it: wood cut with the axe, a
    strike of the matches (probe_campfire.py's steps);
  - out of the fire's reach the key still lights nothing; within it, a press
    lights the stick: Lit, BurnOutTime STICK_BURN_S on, the burning model and
    the glow shown in place of the bare one;
  - held on, the key raises it: FireWard, the stick's ready pose its UsePose,
    playing; let go, FireWard falls and the carry pose is back;
  - switched to the pistol with the key still down, FireWard falls, the stick
    gets its carry pose back, and the key is the pistol's sights again;
  - its time run out (BurnOutTime written into the past: a headless game's
    clock would not reach two minutes), the stick goes out by itself, while
    held out: FireWard falls with it.

Any profile on disk is set aside first, so the game starts on the issued
loadout, and put back at the end.
"""

LEVEL = "/Game/Maps/Lvl_Forest_200m"  # passes here, fails on the 50 m probe level (T11)
SYSTEMS = ('throw', 'survival')

import os
import shutil

import unreal

from combat.anim_blueprint import AIM_SLOT
from combat.paths import (
    FIRE_WARD_VAR, HOLD_TORCH_ANIM_PATH, ITEM_BP_PATH, WARD_TORCH_ANIM_PATH,
    WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH,
)
from combat.seat_tuning import SIGHTS_FORCED_VAR
from combat.stick import FLAME, GLOW, MODEL
from combat.torch_tuning import (
    BURN_OUT_VAR, BURNS_VAR, LIT_VAR, STICK_BURN_S, STICK_LIGHT_RADIUS_CM,
    USE_POSE_VAR, WARD_ITEM_VAR,
)
from combat.use_tuning import USING_VAR
from combat.weapon_component.interact import INTERACT_FORCED_VAR
from combat.weapon_component.knife import KNIFE_QUEUED_VAR
from combat.weapon_component.tick import FIRE_FORCED_VAR
from probes.probe_campfire import ISSUED, MATCHES, _bag, _cut_wood, _fires, _strike
from probes.probe_chop_tree import _equip
from probes.probe_knife import _file, _held_name
from combat.weapon_component import vars as WV

WRITABLE = ([(WEAPON_COMP_BP_PATH, v) for v in
             (WV.EquippedIndex, WV.NeedsRefresh, WV.Inventory, KNIFE_QUEUED_VAR,
              INTERACT_FORCED_VAR, FIRE_FORCED_VAR, SIGHTS_FORCED_VAR)]
            + [(ITEM_BP_PATH, BURN_OUT_VAR)])

STICK = "BP_Stick_C"
PISTOL = "BP_Pistol_C"
FAR_CM = 2.0 * STICK_LIGHT_RADIUS_CM
HELD_S = 0.3
BLEND_S = 0.4             # the equip's blend, and a little


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _shown(stick):
    """{component: visible} for the bare model, the burning one and the glow."""
    out = {}
    for cls in (unreal.StaticMeshComponent, unreal.PointLightComponent):
        for c in stick.get_components_by_class(cls):
            if c.get_name() in (MODEL, FLAME, GLOW):
                out[c.get_name()] = bool(c.is_visible())
    return out


def _key(p, wc, down, wait=HELD_S):
    p.set(wc, SIGHTS_FORCED_VAR, down)
    yield wait


def _pose(stick):
    pose = stick.get_editor_property("AimPose")
    return pose.get_name() if pose else None


def _run(p):
    yield lambda: p.pawn() is not None
    yield 0.5
    player = p.pawn()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    p.check("the player has a weapon component", wc is not None)
    if wc is None:
        return
    anim = player.get_editor_property("mesh").get_anim_instance()
    carry, ward = (unreal.load_asset(a) for a in (HOLD_TORCH_ANIM_PATH, WARD_TORCH_ANIM_PATH))

    bag = _bag(p, wc)
    p.check("a stick is issued, last, after the matches", bag == ISSUED, str(bag))
    if STICK not in bag:
        return
    stick = list(p.get(wc, "Inventory"))[bag.index(STICK)]
    p.check("...carried, named for the HUD, with its icon, the one item that Burns, not lit",
            not p.get(stick, "Dropped") and str(p.get(stick, "DisplayName")) == "Stick"
            and p.get(stick, "Icon") is not None and not p.get(stick, LIT_VAR)
            and [n for n, i in zip(bag, p.get(wc, "Inventory")) if p.get(i, BURNS_VAR)]
            == [STICK], f"{p.get(stick, 'DisplayName')} {p.get(stick, 'Icon')}")

    yield from _equip(p, wc, STICK)
    yield BLEND_S
    p.check("in hand it is a bare stick, carried in A_HoldTorch",
            p.get(wc, "Held") == stick and _shown(stick) == {MODEL: True, FLAME: False,
                                                             GLOW: False}
            and stick.get_editor_property("AimPose") == carry
            and anim.is_playing_slot_animation(carry, AIM_SLOT),
            f"{_held_name(p, wc)} {_shown(stick)} {_pose(stick)}")

    yield from _key(p, wc, True)
    p.check("the use key with no campfire anywhere lights nothing",
            not p.get(stick, LIT_VAR) and not p.get(wc, FIRE_WARD_VAR) and not _fires(p),
            f"Lit {p.get(stick, LIT_VAR)}")
    p.check("...held, it is Using, and it does not aim: the key is not the sights' here",
            p.get(wc, USING_VAR) and not p.get(wc, "Aiming") and not p.get(wc, "SightAiming"),
            f"Using {p.get(wc, USING_VAR)} Aiming {p.get(wc, 'Aiming')}")
    yield from _key(p, wc, False)
    p.check("...let go, it is not Using", not p.get(wc, USING_VAR))

    got = yield from _cut_wood(p, player, wc)
    p.check("the axe cuts a piece of wood and E takes it into the bag", got, str(_bag(p, wc)))
    if not got:
        return
    yield from _equip(p, wc, MATCHES)
    yield from _strike(p, wc)
    fires = _fires(p)
    p.check("a strike of the matches lights a campfire", len(fires) == 1, str(len(fires)))
    if len(fires) != 1:
        return
    at = fires[0].get_actor_location()
    near = player.get_actor_location()
    yield from _equip(p, wc, STICK)

    far = near - player.get_actor_forward_vector() * FAR_CM
    player.set_actor_location(far + unreal.Vector(0.0, 0.0, 30.0), False, True)
    yield 0.1
    gap = (player.get_actor_location() - at).length()
    yield from _key(p, wc, True)
    p.check(f"out of the fire's reach ({STICK_LIGHT_RADIUS_CM:g} cm) the key lights nothing",
            gap > STICK_LIGHT_RADIUS_CM and not p.get(stick, LIT_VAR)
            and not p.get(wc, FIRE_WARD_VAR), f"{gap:.0f} cm away, Lit {p.get(stick, LIT_VAR)}")
    yield from _key(p, wc, False)

    player.set_actor_location(near, False, True)
    yield 0.1
    gap = (player.get_actor_location() - at).length()
    t0 = unreal.GameplayStatics.get_time_seconds(p.world())
    p.set(wc, SIGHTS_FORCED_VAR, True)
    yield lambda: p.get(stick, LIT_VAR)
    t1 = unreal.GameplayStatics.get_time_seconds(p.world())
    out = p.get(stick, BURN_OUT_VAR)
    p.check("within it, a press of the use key lights the stick",
            gap < STICK_LIGHT_RADIUS_CM and p.get(stick, LIT_VAR), f"{gap:.0f} cm away")
    p.check(f"...to burn {STICK_BURN_S:g} s from the press",
            t0 + STICK_BURN_S - 0.01 <= out <= t1 + STICK_BURN_S + 0.01,
            f"{BURN_OUT_VAR} {out:.3f}, pressed between {t0:.3f} and {t1:.3f}")
    yield BLEND_S
    p.check("...the burning model and its glow shown in place of the bare stick",
            _shown(stick) == {MODEL: False, FLAME: True, GLOW: True}, str(_shown(stick)))
    p.check("the key held on, the burning stick is held out: FireWard",
            p.get(wc, FIRE_WARD_VAR) and p.get(wc, USING_VAR) and not p.get(wc, "Aiming"),
            f"FireWard {p.get(wc, FIRE_WARD_VAR)}")
    p.check(f"...raised in its {USE_POSE_VAR}, A_WardTorch, which plays",
            stick.get_editor_property("AimPose") == ward
            and p.get(wc, WARD_ITEM_VAR) == stick
            and anim.is_playing_slot_animation(ward, AIM_SLOT)
            and not anim.is_playing_slot_animation(carry, AIM_SLOT), str(_pose(stick)))
    p.check("...still in hand, in the fist", p.get(wc, "Held") == stick
            and stick.get_attach_parent_actor() == player
            and not stick.get_editor_property("hidden"), _held_name(p, wc))

    yield from _key(p, wc, False, BLEND_S)
    p.check("the key let go, the fire is lowered: FireWard falls, the stick burns on",
            not p.get(wc, FIRE_WARD_VAR) and p.get(stick, LIT_VAR)
            and _shown(stick) == {MODEL: False, FLAME: True, GLOW: True},
            f"FireWard {p.get(wc, FIRE_WARD_VAR)} Lit {p.get(stick, LIT_VAR)}")
    p.check("...and it is carried in A_HoldTorch again",
            stick.get_editor_property("AimPose") == carry
            and p.get(wc, WARD_ITEM_VAR) is None
            and anim.is_playing_slot_animation(carry, AIM_SLOT), str(_pose(stick)))

    yield from _key(p, wc, True, BLEND_S)
    up = p.get(wc, FIRE_WARD_VAR)
    p.set(wc, "EquippedIndex", _bag(p, wc).index(PISTOL))
    p.set(wc, "NeedsRefresh", True)
    yield lambda: _held_name(p, wc) == PISTOL
    yield lambda: p.get(wc, "SightAiming")
    p.check("held out, then switched to the pistol with the key still down: FireWard "
            "falls and the stick has its carry pose back",
            up and not p.get(wc, FIRE_WARD_VAR) and stick.get_editor_property("AimPose") == carry
            and p.get(wc, WARD_ITEM_VAR) is None,
            f"was up {up}, FireWard {p.get(wc, FIRE_WARD_VAR)}, {_pose(stick)}")
    p.check("...and with a gun the same key is the sights': SightAiming, not Using",
            p.get(wc, "SightAiming") and not p.get(wc, USING_VAR))
    p.check("...the stick burning on in the bag, hidden",
            p.get(stick, LIT_VAR) and stick.get_editor_property("hidden"))
    yield from _key(p, wc, False)

    yield from _equip(p, wc, STICK)
    yield from _key(p, wc, True, BLEND_S)
    up = p.get(wc, FIRE_WARD_VAR)
    p.set(stick, BURN_OUT_VAR, unreal.GameplayStatics.get_time_seconds(p.world()) - 1.0)
    yield lambda: not p.get(stick, LIT_VAR)
    yield BLEND_S
    p.check("its time run out while it is held out, the stick goes out by itself",
            up and not p.get(stick, LIT_VAR)
            and _shown(stick) == {MODEL: True, FLAME: False, GLOW: False},
            f"was up {up}, {_shown(stick)}")
    p.check("...FireWard falls with it, the key still down, and the carry pose is back",
            not p.get(wc, FIRE_WARD_VAR) and p.get(wc, USING_VAR)
            and stick.get_editor_property("AimPose") == carry
            and anim.is_playing_slot_animation(carry, AIM_SLOT),
            f"FireWard {p.get(wc, FIRE_WARD_VAR)}, {_pose(stick)}")
    p.check("...and it is a stick again, still in the bag: it can be lit again",
            _bag(p, wc).count(STICK) == 1 and p.get(wc, "Held") == stick)
    yield from _key(p, wc, False)
    yield from _key(p, wc, True)
    p.check("...which a fresh press at the fire does",
            p.get(stick, LIT_VAR) and len(_fires(p)) == 1, f"Lit {p.get(stick, LIT_VAR)}")
    yield from _key(p, wc, False)
