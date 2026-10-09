"""The SOUND SETTINGS tab's HUD Tick fragment: the tab's keys, nudge and save
(tune_tick.author_tab_flow, shared with the other tabs), then the table onto
the game's sound mix.

    its menu row taken      SoundTuneOpen = NOT SoundTuneOpen; the other tabs shut
    SoundTuneTouched OR NOT SoundTuneApplied:
      SetBaseSoundMix(A_Mix_Game)
      for each row s        SetSoundMixClassOverride(A_Mix_Game, the row's
                            SoundClass, Volume = SoundTuneValues[s], no fade)
      SoundTuneApplied = true, SoundTuneTouched = false

Every sound's waves are in a class of their own (Sound/mix.py), so a
class's volume in the mix is that sound's, wherever it is played from. The
assets hold no volume: the HUD's table (sound_tuning.csv, baked at build
time) is the one place it is, and the HUD's first Tick tells the mix. The
title's HUD ticks too, so the mix is told before a game starts. After that
only a nudge tells it again: the mix is the audio device's and outlives a
respawn, unlike what the other tabs write.
"""

from uebp.vars import declare, defaults
from graphics_menu.sound_tune_consts import SOUND_TUNE_TABLE
from uebp.graph import _connect, _must_load, _pin, out, then
from Sound.catalog import SOUND_STATS
from Sound.mix import SOUND_MIX_PATH, class_path
from Sound.tuning import VOLUME_MAX, VOLUME_MIN, VOLUME_STEP, table
from graphics_menu.dev_guns import _branch, _call, _get, _setter
from graphics_menu.sound_tune_consts import (
    SOUND_SUBJECT, SOUND_TAB, SOUND_TUNE_APPLIED_VAR,
)
from graphics_menu.tune_tabs import other_open_vars
from graphics_menu.tune_tick import author_tab_flow, declare_tab_vars, tab_defaults
from uebp.nodes.array import FN_ARR_GET
from uebp.nodes.math import FN_NOT, FN_OR
from uebp.nodes.system import FN_SET_BASE_MIX, FN_SET_MIX_CLASS

MIX_PIN, CLASS_PIN = "InSoundMixModifier", "InSoundClass"


def declare_sound_tune_vars(ed):
    declare_tab_vars(ed, SOUND_TAB)
    declare(ed, SOUND_TUNE_TABLE)


def sound_tune_defaults():
    """sound_tuning.csv's volumes (else the defaults), as the build bakes them."""
    built = table()
    count = len(SOUND_STATS)
    return {**tab_defaults(SOUND_TAB, [SOUND_SUBJECT],
                           [float(built[s[0]]) for s in SOUND_STATS],
                           [VOLUME_STEP] * count, [VOLUME_MIN] * count),
            SOUND_TAB.maxs_var: [VOLUME_MAX] * count,
            **defaults(SOUND_TUNE_TABLE)}


def _asset_pin(node, name, path):
    """An object pin's default: an asset, which must exist."""
    _must_load(path)
    pin = _pin(node, name)
    pin.set_pin_value(path)
    if path not in str(pin.get_pin_value()):
        raise RuntimeError(f"pin {name!r} would not take {path}: {pin.get_pin_value()!r}")


def _author_apply(ed, in_execs, made):
    """The table onto the mix (module docstring). Returns the exec tails."""
    told = _call(ed, FN_NOT, made, A=_get(ed, SOUND_TUNE_APPLIED_VAR, made))
    stale = _call(ed, FN_OR, made, A=_get(ed, SOUND_TAB.touched_var, made), B=out(told))
    go, idle = _branch(ed, out(stale), in_execs, made)
    base = _call(ed, FN_SET_BASE_MIX, made)
    _asset_pin(base, "InSoundMix", SOUND_MIX_PATH)
    _connect(go, _pin(base, "execute"))
    flow = then(base)
    for s, (sound, *_rest) in enumerate(SOUND_STATS):
        cell = _call(ed, FN_ARR_GET, made,
                     TargetArray=_get(ed, SOUND_TAB.values_var, made), Index=s)
        n = _call(ed, FN_SET_MIX_CLASS, made, Volume=out(cell, "Item"), FadeInTime=0.0)
        _asset_pin(n, MIX_PIN, SOUND_MIX_PATH)
        _asset_pin(n, CLASS_PIN, class_path(sound))
        _connect(flow, _pin(n, "execute"))
        flow = then(n)
    flow = _setter(ed, SOUND_TUNE_APPLIED_VAR, "true", [flow], made)
    done = _setter(ed, SOUND_TAB.touched_var, "false", [flow], made)
    return [done, idle]


def author_sound_tune_tick(ed, pc_out, in_execs):
    """The whole fragment (see the module docstring). Returns the exec tails."""
    made = []
    flow = author_tab_flow(ed, pc_out, in_execs, made, SOUND_TAB, 1, other_open_vars(SOUND_TAB))
    tails = _author_apply(ed, flow, made)
    ed.add_comment_to_nodes(
        "Sound tuning (its row in the menu): Up/Down pick a sound, Left/Right "
        "change its volume, Enter saves sound_tuning.csv. On the first Tick, "
        "and after a nudge, each sound's class takes its volume in the game's "
        "sound mix.", made[:1])
    return tails
