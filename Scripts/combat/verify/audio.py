"""verify.audio -- Sound assets, their attenuation profiles, and every place a sound is played.
"""

import os
import wave as _wave

import unreal

from combat.audio import (
    ATTENUATIONS, ATT_DB_AT_MAX, ATT_FOLEY, ATT_GUNFIRE, AUDIBLE_LIMIT_CM,
    CREATURE_AUDIO_DIR, CREATURE_SOUND_NAMES, RETIRED_SOUNDS,
    SOUND_ATTENUATION, SOUND_NAMES, SOUND_SRC_DIR,
)
from combat.paths import AUDIO_DIR
from combat.tuning import AUTO_DISPLAYS
from combat.weapon_specs import _weapon_specs
from combat.verify.fixtures import _eas
from combat.verify.common import BEL, PIN, by_pins, check, graph, in_pins, load


# ─── The sounds themselves ───────────────────────────────────────────────────

def check_sound_assets():
    # Nine assets cut from CC0 recordings of real firearms by
    # Scripts/fetch_weapon_sounds.py, which replaced a synthesiser. The checks are
    # on the WAVs on disk rather than on the SoundWave assets, because the two
    # properties worth asserting are properties of the audio and not of the import.



    for name in SOUND_NAMES:
        check(f"{name} imported", _eas.does_asset_exist(f"{AUDIO_DIR}/{name}"))
    # A_Reload was the one synthesised clack every weapon shared. A builder that
    # simply stops referencing an asset leaves it on disk forever, so its removal
    # is deliberate and worth asserting -- an orphan in the audio folder reads as
    # something still in use.
    for path in RETIRED_SOUNDS:
        check(f"the superseded {path.rsplit('/', 1)[-1]} is gone",
              not _eas.does_asset_exist(path), path)

    for name in SOUND_NAMES:
        src = os.path.join(SOUND_SRC_DIR, f"{name}.wav")
        if not os.path.isfile(src):
            check(f"{name}.wav is on disk", False, src)
            continue
        with _wave.open(src, "rb") as fh:
            channels, rate, frames = (fh.getnchannels(), fh.getframerate(),
                                      fh.getnframes())
        # MONO IS LOAD-BEARING, not a size choice. PlaySoundAtLocation spatialises
        # by panning and attenuating around the listener and can only do that to a
        # one-channel source; hand it the stereo original and every shot plays flat
        # and full volume with no sense of where the muzzle was.
        check(f"{name} is mono, so PlaySoundAtLocation can place it",
              channels == 1, f"{channels} channels")
        check(f"{name} is 44.1 kHz", rate == 44100, str(rate))
        seconds = frames / float(rate)
        check(f"{name} is between 0.2 s and 2.5 s long", 0.2 <= seconds <= 2.5,
              f"{seconds:.2f}s")

    # A shot has to finish inside its own fire interval or an automatic stacks an
    # unbounded number of copies of itself. Only the automatics are checked: the
    # sniper's 1.6 s report deliberately runs into its 1.6 s cadence.
    for name in AUTO_DISPLAYS:
        sp = next(x for x in _weapon_specs() if x["display"] == name)
        src = os.path.join(SOUND_SRC_DIR, f"{sp['sound'].rsplit('/', 1)[-1]}.wav")
        if not os.path.isfile(src):
            continue
        with _wave.open(src, "rb") as fh:
            seconds = fh.getnframes() / float(fh.getframerate())
        overlap = seconds / sp["interval"]
        check(f"{name}: a held trigger stacks at most 12 copies of the shot",
              overlap <= 12.0, f"{seconds:.2f}s sample / {sp['interval']:.2f}s "
                               f"interval = {overlap:.1f} overlapping")
        # ...and the ones that do stack are mixed down for it, or the burst clips.
        with _wave.open(src, "rb") as fh:
            raw = fh.readframes(fh.getnframes())
        peak = max(abs(int.from_bytes(raw[i:i + 2], "little", signed=True))
                   for i in range(0, len(raw), 2)) / 32767.0
        check(f"{name}: its sample is mixed below full scale, so a burst does not "
              f"clip", peak < 0.80, f"peak {peak:.2f}")


# ─── Distance and direction ──────────────────────────────────────────────────

def check_distance_and_direction():
    # Every sound in this game is made by something standing somewhere, so every
    # one of them is spatialised and every one of them fades with distance. The
    # machinery is the engine's: a USoundAttenuation asset per profile, named on
    # the SoundWave rather than wired into each PlaySoundAtLocation node.
    #
    # The failure this section exists to catch is the quiet one. A SoundBase whose
    # AttenuationSettings is None does not fall back to some default falloff -- it
    # is parsed with no spatialisation and no attenuation at all, and plays at full
    # volume, centred, from anywhere on the map. That is indistinguishable from
    # working until you walk away from the thing making the noise.

    _ATT_OK = {p.name: p for p in ATTENUATIONS}
    check("there is a small named set of attenuation profiles, not one per sound",
          1 <= len(ATTENUATIONS) <= 4, str(sorted(_ATT_OK)))

    for profile in ATTENUATIONS:
        att = load(profile.path)
        check(f"{profile.name} exists", att is not None, profile.path)
        if att is None:
            continue
        check(f"{profile.name} is a SoundAttenuation asset",
              isinstance(att, unreal.SoundAttenuation), str(type(att)))
        st = att.get_editor_property("attenuation")
        check(f"{profile.name}: volume falls off with distance",
              bool(st.get_editor_property("attenuate")))
        # Without this the sound has a position and no direction: it attenuates as
        # you walk away but never moves in the stereo field as you turn.
        check(f"{profile.name}: spatialised, so it comes from where it happened",
              bool(st.get_editor_property("spatialize")))
        check(f"{profile.name}: on the engine's own panner",
              st.get_editor_property("spatialization_algorithm")
              == unreal.SoundSpatializationAlgorithm.SPATIALIZATION_DEFAULT,
              str(st.get_editor_property("spatialization_algorithm")))
        check(f"{profile.name}: a natural (dB) falloff curve, not a mixing one",
              st.get_editor_property("distance_algorithm")
              == unreal.AttenuationDistanceModel.NATURAL_SOUND,
              str(st.get_editor_property("distance_algorithm")))
        check(f"{profile.name}: a sphere, so it fades the same in every direction",
              st.get_editor_property("attenuation_shape")
              == unreal.AttenuationShape.SPHERE,
              str(st.get_editor_property("attenuation_shape")))
        radius = float(st.get_editor_property("attenuation_shape_extents").x)
        falloff = float(st.get_editor_property("falloff_distance"))
        check(f"{profile.name}: full volume out to {profile.radius_cm:.0f} cm",
              abs(radius - profile.radius_cm) < 1e-3, f"{radius:.1f} cm")
        check(f"{profile.name}: fades over {profile.falloff_cm:.0f} cm beyond that",
              abs(falloff - profile.falloff_cm) < 1e-3, f"{falloff:.1f} cm")
        # THE NUMBER THE BRIEF ASKED FOR. The falloff is measured from the edge of
        # the full-volume sphere, so the audible radius is the sum of the two --
        # reading falloff_distance alone would under-report it by the radius.
        check(f"{profile.name}: inaudible past 100 m",
              radius + falloff <= AUDIBLE_LIMIT_CM + 1e-3,
              f"{(radius + falloff) / 100.0:.1f} m")
        check(f"{profile.name}: reaches {ATT_DB_AT_MAX:.0f} dB at the edge",
              abs(float(st.get_editor_property("d_b_attenuation_at_max"))
                  - ATT_DB_AT_MAX) < 1e-3,
              str(st.get_editor_property("d_b_attenuation_at_max")))
        check(f"{profile.name}: air absorption "
              f"{'on' if profile.air_absorption else 'off'}",
              bool(st.get_editor_property("attenuate_with_lpf"))
              is bool(profile.air_absorption))

    # One profile has to spend the whole 100 m allowance, or "at most 100 m" has
    # been satisfied by making everything quiet instead of by placing it.
    check("a gunshot is the thing that carries the full 100 m",
          abs(ATT_GUNFIRE.audible_cm - AUDIBLE_LIMIT_CM) < 1e-3,
          f"{ATT_GUNFIRE.audible_cm / 100.0:.0f} m")
    check("a footstep carries far less than a gunshot",
          ATT_FOLEY.audible_cm * 4 < ATT_GUNFIRE.audible_cm,
          f"{ATT_FOLEY.audible_cm / 100.0:.0f} m vs "
          f"{ATT_GUNFIRE.audible_cm / 100.0:.0f} m")

    # THE SWEEP THAT MAKES "NOTHING WAS MISSED" TRUE. It walks the two audio
    # folders on disk rather than SOUND_NAMES + CREATURE_SOUND_NAMES, so a
    # sound the builder imports under a name nobody remembered to profile is a
    # failure here rather than one unattenuated noise nobody notices.
    _waves, _flat = [], []
    for _folder in (AUDIO_DIR, CREATURE_AUDIO_DIR):
        for _ref in _eas.list_assets(_folder, recursive=False):
            _asset = load(_ref)
            if not isinstance(_asset, unreal.SoundWave):
                continue
            _waves.append(_asset.get_name())
            _att = _asset.get_editor_property("attenuation_settings")
            if _att is None or _att.get_name() not in _ATT_OK:
                _flat.append(f"{_asset.get_name()} -> {_att}")
    check("every sound in the game carries one of the attenuation profiles",
          not _flat and len(_waves) == len(SOUND_NAMES) + len(CREATURE_SOUND_NAMES),
          f"{len(_waves)} sounds, unattenuated: {sorted(_flat)}")
    for _name, _profile in sorted(SOUND_ATTENUATION.items()):
        # Named folder, not "try one then the other": a failed load is an Error
        # line in the log, and 13 of them on every clean run is how a real one
        # stops being read.
        _asset = load(f"{AUDIO_DIR if _name in SOUND_NAMES else CREATURE_AUDIO_DIR}"
                      f"/{_name}")
        _att = _asset.get_editor_property("attenuation_settings") if _asset else None
        check(f"{_name} -> {_profile.name}",
              _att is not None and _att.get_name() == _profile.name, str(_att))
        # AND THE ENGINE AGREES. MaxDistance is not a field this builder writes --
        # USoundBase caches it off whatever attenuation it ends up resolving, and
        # it is the number the audio device culls against at play time. Reading it
        # back is the end-to-end proof that the asset link actually reached the
        # sound, rather than a re-read of the struct the builder just wrote; an
        # unattenuated wave reports the whole world here, not 100 m.
        _reach = float(_asset.get_editor_property("max_distance")) if _asset else -1.0
        check(f"...and the engine will cull {_name} past "
              f"{_profile.audible_cm / 100.0:.0f} m",
              abs(_reach - _profile.audible_cm) < 1e-3, f"{_reach:.0f} cm")


# ─── Every call site is a placed one ─────────────────────────────────────────

def check_sound_call_sites():
    # Attenuation on the asset only works if the sound is played AT somewhere.
    # PlaySound2D / SpawnSound2D are non-spatial by construction -- they bypass
    # attenuation entirely, whatever the SoundBase says -- so one of them anywhere
    # in the game would be a sound that stayed flat while every check above passed.
    #
    # The sweep is over every Blueprint in the two folders that make noise, found
    # by listing them, so a sixth sound-playing graph added later is covered
    # without anybody remembering to add it here.

    _placed, _flat_calls, _unwired, _overridden, _graphs = [], [], [], [], 0
    for _dir in ("/Game/Weapons", "/Game/Forest/NPC"):
        for _ref in _eas.list_assets(_dir, recursive=True):
            _bp = load(_ref)
            if not isinstance(_bp, unreal.Blueprint):
                continue
            _g = graph(_bp)
            if _g is None:
                continue
            _graphs += 1
            # Nodes carrying a Sound INPUT pin: that is every play and spawn
            # overload and nothing else. Matching on the title instead would sweep
            # up every `Get FireSound` in the graph.
            for _n in by_pins(_g.list_all_nodes(), "Sound"):
                _t = str(BEL.get_node_title(_n)).replace("\n", " ")
                _where = f"{_bp.get_name()}: {_t}"
                _placed.append(_where)
                if "2D" in _t or "Location" not in in_pins(_n):
                    _flat_calls.append(_where)
                if not PIN.list_connected_pins(BEL.find_input_pin(_n, "Sound")):
                    _unwired.append(_where)
                _ap = BEL.find_input_pin(_n, "AttenuationSettings")
                if _ap and _ap.is_valid() and (PIN.list_connected_pins(_ap)
                                               or str(PIN.get_pin_value(_ap))
                                               not in ("", "None")):
                    _overridden.append(_where)

    check("every sound is played at a world location, never in 2D",
          not _flat_calls, str(sorted(_flat_calls)))
    check("...and every one of them was handed a sound to play",
          not _unwired, str(sorted(_unwired)))
    # Not a functional failure -- the pin overrides the asset and would still
    # attenuate -- but it would be a second place the answer lives, and the whole
    # point of setting it on the SoundBase was that there is only one.
    check("...with no per-call attenuation override, so the asset is the one "
          "place it is said", not _overridden, str(sorted(_overridden)))
    check("all five known call sites are still there: fire, dry fire, reload, "
          "footstep, and the wanderers' voice and melee thud",
          len(_placed) >= 5, f"{len(_placed)} across {_graphs} graphs")


def run():
    check_sound_assets()
    check_distance_and_direction()
    check_sound_call_sites()
