"""verify_graphics_menu.py's checks for the HUD's stat bars: where they sit
(HP and stamina under the grid, the survival bars vertical in the bottom-left
corner), the icon beside each, and the blink while one is low (hud_flash.py).
"""

import unreal

from graphics_menu import umg_consts as C
from graphics_menu.umg_author import colour as linear
from graphics_menu.umg_checks import _pins, _source_titles, _sources, _title, _tree, _value
from ui_art.stat_icons import stat_icon_name

# bar -> (its icon widget, the stat its texture is drawn for, the icon's tint)
ICONS = {C.HP_BAR: (C.HP_ICON, "Health", C.COL_HP_FILL),
         C.STAMINA_BAR: (C.ST_ICON, "Stamina", C.COL_ST_FILL)}
ICONS.update({C.stat_bar(s): (C.stat_icon(s), s, fill) for s, fill in C.SURVIVAL_BARS})


def _children(tree, name):
    w = tree.get(name, (None, False))[0]
    return [str(c.get_name()) for c in w.get_all_children()] if w else None


def _close(a, b):
    return abs(float(a) - float(b)) < 1e-6


def check_bar_layout(check):
    hud = _tree(C.WBP_HUD)
    vitals = (_children(hud, C.VITALS), _children(hud, C.HP_GROUP),
              _children(hud, C.ST_GROUP))
    check("under the grid: HP (icon, bar, number) then stamina (icon, bar)",
          vitals == ([C.HP_GROUP, C.ST_GROUP],
                     [C.HP_ICON, f"{C.HP_BAR}Box", C.HP_NUM],
                     [C.ST_ICON, f"{C.STAMINA_BAR}Box"]), str(vitals))

    columns = _children(hud, "SurvivalBars")
    want = [C.stat_group(s) for s, _c in C.SURVIVAL_BARS]
    shapes = {g: _children(hud, g) for g in want}
    check("bottom left: one column per survival stat, its bar over its icon, "
          "and no caption",
          columns == want and all(shapes[C.stat_group(s)]
                                  == [f"{C.stat_bar(s)}Box", C.stat_icon(s)]
                                  for s, _c in C.SURVIVAL_BARS),
          f"{columns}: {shapes}")
    stack = _children(hud, C.SURVIVAL)
    check("...with the debuff names stacked above them",
          stack == [C.debuff_text(s) for _t, _l, s in C.DEBUFF_LABELS] + ["SurvivalBars"],
          str(stack))

    up = unreal.ProgressBarFillType.BOTTOM_TO_TOP
    fills = {}
    for s, _c in C.SURVIVAL_BARS:
        bar = hud.get(C.stat_bar(s), (None, False))[0]
        box = hud.get(f"{C.stat_bar(s)}Box", (None, False))[0]
        style = bar.get_editor_property("widget_style") if bar else None
        fills[s] = (str(bar.get_editor_property("bar_fill_type")) if bar else None,
                    (box.get_editor_property("width_override"),
                     box.get_editor_property("height_override")) if box else None,
                    tuple(style.get_editor_property(k).get_editor_property(
                        "resource_object").get_name()
                          for k in ("fill_image", "background_image")) if style else None)
    check("the survival bars stand vertical, fill from the bottom, on the upright art",
          all(f == (str(up), C.SV_BAR_SIZE, ("T_UI_BarV", "T_UI_BarTrackV"))
              for f in fills.values()), str(fills))
    across = [n for n in (C.HP_BAR, C.STAMINA_BAR)
              if hud.get(n, (None, False))[0] is None
              or hud[n][0].get_editor_property("bar_fill_type")
              != unreal.ProgressBarFillType.LEFT_TO_RIGHT]
    check("...and HP and stamina fill across", not across, str(across))

    wrong = []
    for bar, (name, stat, tint) in ICONS.items():
        icon = hud.get(name, (None, False))[0]
        tex = (icon.get_editor_property("brush").get_editor_property("resource_object")
               if isinstance(icon, unreal.Image) else None)
        colour = icon.get_editor_property("color_and_opacity") if tex else None
        w = linear(tint)
        want_tint = (w.r, w.g, w.b, w.a)
        if (not tex or tex.get_name() != stat_icon_name(stat)
                or not all(_close(a, b) for a, b in zip(
                    (colour.r, colour.g, colour.b, colour.a), want_tint))):
            wrong.append(f"{bar}: {name} {tex.get_name() if tex else None}")
    check("every bar has its stat's icon beside it, tinted the bar's colour",
          not wrong, "; ".join(wrong))


def check_bar_flash(check, nodes):
    """Each group blinks off its own bar's fraction, below LOW_FRACTION, on
    real time."""
    groups = C.flash_groups()
    percents = {t[4:]: n for n in nodes if "InPercent" in _pins(n)
                for t in _source_titles(n, "self") if t.startswith("Get ")}
    fades = {}
    for n in nodes:
        if "InOpacity" not in _pins(n):
            continue
        for t in _source_titles(n, "self"):
            if t[4:] in groups:
                fades.setdefault(t[4:], []).append(n)
    check("every stat group has one opacity write, and nothing else blinks it",
          sorted(fades) == sorted(groups) and all(len(v) == 1 for v in fades.values()),
          str({g: len(v) for g, v in fades.items()}))

    bad = []
    for group, bar in groups.items():
        why = _flash_fault(fades.get(group, [None])[0], percents.get(bar))
        if why:
            bad.append(f"{group}: {why}")
    check(f"...dimmed to {C.FLASH_DIM} every other half-beat at {C.FLASH_HZ} Hz of "
          f"real time, while its own bar's fraction is under {C.LOW_FRACTION}",
          not bad, str(bad))


def _flash_fault(fade, fill):
    """Why ``fade`` is not the blink of the bar ``fill`` writes, or None."""
    def one(n, pin):
        found = _sources(n, pin) if n else []
        if len(found) != 1:
            raise LookupError(f"{_title(n) if n else None}.{pin} has {len(found)} feeds")
        return found[0]
    try:
        pick = one(fade, "InOpacity")
        both = one(pick, "bPickA")
        low, off = one(both, "A"), one(both, "B")
        beats = one(one(off, "A"), "A")
        clock = one(beats, "A")
    except LookupError as e:
        return str(e)
    got = (_value(pick, "A"), _value(pick, "B"), _value(low, "B"), _value(off, "B"),
           _value(beats, "B"), _title(clock))
    if not (_close(got[0], C.FLASH_DIM) and _close(got[1], 1.0)
            and _close(got[2], C.LOW_FRACTION) and _close(got[3], 0.5)
            and _close(got[4], C.FLASH_HZ) and "RealTime" in got[5].replace(" ", "")):
        return str(got)
    src, want = _sources(low, "A"), (_sources(fill, "InPercent") if fill else [])
    if len(src) != 1 or len(want) != 1 or src[0].get_path_name() != want[0].get_path_name():
        return "not its own bar's fraction"
    return None
