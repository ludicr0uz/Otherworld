"""verify.settings_and_tuning -- BP_Settings (what survives a restart) and the CombatConfig being the
only home of the global numbers.
"""

import dataclasses

import unreal

from combat.difficulty import DEFAULT_DIFFICULTY, DIFFICULTY_LABELS, DIFFICULTY_VAR, EASY
from combat.paths import (
    GAME_MODE_BP_PATH, SETTINGS_BP_PATH, SETTINGS_SLOT, SETTINGS_USER_INDEX)
from combat.tuning import BIND_VARS, COMBAT, CombatConfig
from combat.verify.fixtures import w, wc_cdo, wg
from combat.verify.common import BEL, PIN, builder_modules, cdo, check, load, titled


def _upstream_titles(nodes, title):
    """How many nodes titled `title` feed data, at any depth, into `nodes`."""
    seen, todo, hits = set(), list(nodes), 0
    while todo:
        node = todo.pop()
        for pin in BEL.list_input_pins(node):
            if str(PIN.get_pin_name(pin)) == "execute":
                continue
            for link in PIN.list_connected_pins(pin):
                up = PIN.get_owning_node(link)
                if up.get_name() in seen or any(
                        str(PIN.get_pin_name(q)) == "execute"
                        for q in BEL.list_input_pins(up)):
                    continue        # an exec node's output is a stored value
                seen.add(up.get_name())
                hits += str(BEL.get_node_title(up)).replace("\n", " ") == title
                todo.append(up)
    return hits


# ─── BP_Settings: what survives a restart ────────────────────────────────────

def check_settings_savegame():
    # Built here rather than in build_graphics_menu.py so that both consumers -- the
    # weapon component's defaults and the HUD's settings screen -- can name the
    # class without a build-order cycle. Nothing in this file reads it at runtime;
    # the HUD pushes its values onto the component every DrawHUD frame.
    sg = load(SETTINGS_BP_PATH)
    check("BP_Settings exists", sg is not None, SETTINGS_BP_PATH)
    if sg:
        check("...and is a USaveGame, so it can be written to a slot",
              BEL.get_blueprint_parent_class(sg) == unreal.SaveGame.static_class(),
              str(BEL.get_blueprint_parent_class(sg)))
        sg_cdo = cdo(sg)
        check("...carrying a mouse sensitivity that is a float, not an int",
              isinstance(sg_cdo.get_editor_property("MouseSensitivity"), float),
              type(sg_cdo.get_editor_property("MouseSensitivity")).__name__)
        check(f"...defaulting to {COMBAT.mouse_sensitivity_default}",
              abs(sg_cdo.get_editor_property("MouseSensitivity")
                  - COMBAT.mouse_sensitivity_default) < 1e-6,
              repr(sg_cdo.get_editor_property("MouseSensitivity")))
        # The sniper scope's own multiplier: the settings screen's second row,
        # and the Lerp target the weapon component eases toward past the irons.
        for owner, obj in (("BP_Settings", sg_cdo), ("BP_WeaponComponent", wc_cdo)):
            got = obj.get_editor_property("ScopeSensitivity")
            check(f"{owner} carries a scope sensitivity defaulting to "
                  f"{COMBAT.ads_scope_sens_scale}",
                  isinstance(got, float)
                  and abs(got - COMBAT.ads_scope_sens_scale) < 1e-6, repr(got))
        check("...inside its own settings range, whose floor is not zero",
              0.0 < COMBAT.scope_sensitivity_min <= COMBAT.ads_scope_sens_scale
              <= COMBAT.scope_sensitivity_max,
              f"{COMBAT.scope_sensitivity_min}..{COMBAT.scope_sensitivity_max}")
        stored = list(sg_cdo.get_editor_property("Binds"))
        check(f"...and {len(BIND_VARS)} binds, one per rebindable action",
              len(stored) == len(BIND_VARS), str(len(stored)))
        # Index-for-index against BIND_VARS, because Binds is indexed and not
        # keyed: the settings screen writes Binds[row - 1] and the HUD pushes
        # Binds[i] into BIND_VARS[i], so a reordering here silently rebinds every
        # save already on disk.
        check("...in the same order BIND_VARS names them",
              [k.export_text() for k in stored] == [d for _v, d in BIND_VARS],
              str([k.export_text() for k in stored]))
        check("...and debug mode, on unless the player turned it off",
              sg_cdo.get_editor_property("DebugMode") is True,
              repr(sg_cdo.get_editor_property("DebugMode")))
        check("the slot it is written to is named and single",
              bool(SETTINGS_SLOT) and SETTINGS_USER_INDEX == 0,
              f"{SETTINGS_SLOT!r} / user {SETTINGS_USER_INDEX}")
        # The requirement, exercised rather than inspected: a BP_Settings written
        # to a slot has to come back off the disk with its FKey array intact. An
        # FKey is a struct with no Python-visible fields, so "it compiles" says
        # nothing about whether it serialises -- this is the only check here that
        # writes a file and reads it back.
        probe_slot = f"{SETTINGS_SLOT}Probe"
        made = unreal.GameplayStatics.create_save_game_object(
            BEL.generated_class(sg))
        wrote = unreal.GameplayStatics.save_game_to_slot(made, probe_slot, 0)
        read = unreal.GameplayStatics.load_game_from_slot(probe_slot, 0)
        check("a BP_Settings survives a write to a slot and a read back",
              wrote and read is not None
              and [k.export_text() for k in read.get_editor_property("Binds")]
              == [d for _v, d in BIND_VARS]
              and abs(read.get_editor_property("MouseSensitivity")
                      - COMBAT.mouse_sensitivity_default) < 1e-6,
              f"wrote={wrote}")
        unreal.GameplayStatics.delete_game_in_slot(probe_slot, 0)

    for var, _default in BIND_VARS:
        check(f"{var} is an FKey on the component, not a string",
              isinstance(w.get_editor_property(var), unreal.Key),
              type(w.get_editor_property(var)).__name__)

    check("the engine's pitch scale is negative, so it MUST be cached not written",
          wc_cdo.get_editor_property("BasePitchScale") < 0.0,
          repr(wc_cdo.get_editor_property("BasePitchScale")))
    check("...and the yaw scale positive",
          wc_cdo.get_editor_property("BaseYawScale") > 0.0,
          repr(wc_cdo.get_editor_property("BaseYawScale")))
    scale_reads = {str(BEL.get_node_title(x)).replace("\n", " ") for x in wg}
    for label, want in (("yaw", "Set Deprecated Input Yaw Scale"),
                        ("pitch", "Set Deprecated Input Pitch Scale")):
        hits = [t for t in scale_reads if t.replace(" ", "")
                == want.replace(" ", "")]
        check(f"the {label} look scale is written every frame", bool(hits), want)
    for label, want in (("yaw", "Get Deprecated Input Yaw Scale"),
                        ("pitch", "Get Deprecated Input Pitch Scale")):
        hits = [t for t in scale_reads if t.replace(" ", "")
                == want.replace(" ", "")]
        check(f"...from a {label} base READ off the controller, not a literal",
              bool(hits), want)
    check("the scope's slowdown is driven off the zoom, not off a flag -- so it "
          "eases in, and only past the irons",
          len(titled(wg, "Lerp")) >= 1 and 0.0 < COMBAT.ads_sens_compensation <= 1.0,
          f"Lerp(1, {COMBAT.scope_sens_base():g} x ScopeSensitivity, past the irons)")
    # The numbers the player actually feels, spelled out so a change to either
    # constant has to be argued for rather than noticed later. The shoulder
    # and the irons are 1x: the mouse is the same standing, walking (which is
    # aiming) and running.
    for name, zoom, want in (("shoulder", COMBAT.shoulder_zoom, 1.0),
                             ("irons", COMBAT.ads_zoom_irons, 1.0),
                             ("scope", COMBAT.ads_zoom_scope, 0.21875)):
        past = min(max((zoom - COMBAT.ads_zoom_irons)
                       / (COMBAT.ads_zoom_scope - COMBAT.ads_zoom_irons), 0.0), 1.0)
        got = 1.0 + past * (COMBAT.scope_sens_base() * COMBAT.ads_scope_sens_scale - 1.0)
        check(f"...which works out at {want:.2f}x sensitivity "
              f"{'on the' if name == 'shoulder' else 'down the'} {name}",
              abs(got - want) < 5e-3, f"{got:.4f}")
    # The graph itself: nothing but the scope's Lerp, the sensitivity and the
    # cached base may reach a look scale. A CurrentFOV/BaseFOV ratio feeding it
    # is the old slowdown, which slowed the mouse on every aim.
    for label, want in (("yaw", "SetDeprecatedInputYawScale"),
                        ("pitch", "SetDeprecatedInputPitchScale")):
        puts = [n for n in wg
                if str(BEL.get_node_title(n)).replace("\n", " ").replace(" ", "") == want]
        lerps = _upstream_titles(puts, "Lerp") if puts else -1
        check(f"...and the {label} scale has one Lerp behind it (the scope's): the "
              f"shoulder and the irons do not slow the mouse", lerps == 1, str(lerps))
    check("the scope's extra slowdown is the component's ScopeSensitivity, "
          "read rather than a literal, so the settings screen can move it",
          bool(titled(wg, "Get ScopeSensitivity")),
          str(len(titled(wg, "Get ScopeSensitivity"))))


# ─── The combat config ───────────────────────────────────────────────────────

def check_combat_config():
    # The ask was for a named, tunable home for the global combat parameters, with
    # more to follow. What can go wrong quietly is that it becomes a SECOND home --
    # the structure exists, a builder still reads a leftover module constant, and
    # the two disagree until somebody tunes the one that is not wired up.

    check("the global combat tuning lives in one named structure",
          dataclasses.is_dataclass(CombatConfig)
          and isinstance(COMBAT, CombatConfig),
          type(COMBAT).__name__)
    check("...frozen, so no builder can rewrite a value the verifier then asserts",
          CombatConfig.__dataclass_params__.frozen)
    knobs = {f.name for f in dataclasses.fields(COMBAT)}
    check("...holding every global knob: lethality, sprint, ADS, look, recoil",
          knobs >= {"start_health", "head_multiplier", "limb_multiplier",
                    "sprint_speed_cms", "max_stamina", "stamina_drain_per_s",
                    "stamina_regen_per_s", "ads_zoom_irons", "ads_zoom_scope",
                    "ads_interp_speed",
                    "mouse_sensitivity_default", "mouse_sensitivity_min",
                    "mouse_sensitivity_max", "mouse_sensitivity_step",
                    "ads_sens_compensation", "ads_scope_sens_scale",
                    "scope_sensitivity_min", "scope_sensitivity_max",
                    "scope_sensitivity_step",
                    "ads_move_speed_scale",
                    "recoil_recovery_speed",
                    "recoil_recovery_fraction"},
          str(sorted(knobs)))
    stale = [n for n in ("START_HEALTH", "HEAD_MULTIPLIER", "LIMB_MULTIPLIER",
                         "SPRINT_SPEED_CMS", "MAX_STAMINA", "STAMINA_DRAIN_PER_S",
                         "STAMINA_REGEN_PER_S", "ADS_ZOOM_IRONS", "ADS_ZOOM_SCOPE",
                         "ADS_INTERP_SPEED", "ADS_SPREAD_SCALE",
                         "ADS_SENS_COMPENSATION", "MOUSE_SENSITIVITY_DEFAULT",
                         "MOUSE_SENSITIVITY_MIN", "MOUSE_SENSITIVITY_MAX",
                         "MOUSE_SENSITIVITY_STEP")
             if any(hasattr(m, n) for m in builder_modules())]
    check("...and it is the ONLY home -- every loose constant it replaced is gone, "
          "so nothing can read a stale second copy", not stale, str(stale))
    # Per-weapon numbers must NOT have been swept into it: that would undo the
    # "a sixth weapon is a row in a table" property the whole file is built on.
    check("per-weapon numbers stayed on the weapon table",
          not (knobs & {"damage", "spread", "recoil", "interval", "magazine",
                        "ads_spread_scale", "recoil_ads_scale",
                        "recoil_horizontal_ratio"}),
          str(sorted(knobs)))


def check_difficulty():
    # Saved in BP_Settings, copied onto the GameMode by the HUD each frame;
    # both default to EASY so a first run, an old save and a HUD-less pawn all
    # play on easy.
    check("the difficulties are EASY, MEDIUM, SURVIVOR in that order",
          DIFFICULTY_LABELS == ("EASY", "MEDIUM", "SURVIVOR"), str(DIFFICULTY_LABELS))
    check("the default difficulty is EASY",
          DEFAULT_DIFFICULTY == EASY == DIFFICULTY_LABELS.index("EASY"))
    for owner, path in (("BP_Settings", SETTINGS_BP_PATH),
                        ("the GameMode", GAME_MODE_BP_PATH)):
        bp = load(path)
        got = cdo(bp).get_editor_property(DIFFICULTY_VAR) if bp else None
        check(f"{owner} carries {DIFFICULTY_VAR}, an int defaulting to EASY",
              isinstance(got, int) and not isinstance(got, bool)
              and got == DEFAULT_DIFFICULTY, repr(got))


def run():
    check_settings_savegame()
    check_difficulty()
    check_combat_config()
