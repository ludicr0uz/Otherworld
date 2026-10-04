"""Sound -- every sound of the game: what it is, where it is played from, how
far it carries and how loud it is, as Unreal Python; and, beside it, the
tools that source the recordings (run outside the editor).

Entry point: Scripts/build_sound.py (assets, then bindings, then volumes).
After changing a mapping, a take, a profile or a volume it is the only build
to run. Design rules and traps: Scripts/Sound/CLAUDE.md.

THE AREAS (one module each: its SOUNDS, its BINDINGS, and its sound logic)
  sound_weapons   each gun's shot and reload, the dry click; a swing, a fist's
                  and a blade's blow, a thrown blade (GUN_SOUNDS: which gun
                  plays which)
  sound_monsters  the zombie's growls (patrol, aggro, attack: which take is
                  which), the wendigo's roar and its own attenuation curve,
                  a wanderer's blow and its footsteps (VOICES, AGGRO_VOICES,
                  ATTACK_VOICES: which creature has which voice)
  sound_items     a throw, the axe on a trunk, a match, the campfire's crackle
                  (its AudioComponent: add_crackle)
  sound_world     the player's footsteps; the player's voice (the health component's grunt
                  and cry); the forest's beds on BP_DayNightCycle and their
                  fade by DayAmount; the listener at the character

SHARED
  sound_def       Sound (a row of the table) and Binding (a Blueprint variable
                  or component that holds a sound's takes); the folders; the
                  attenuation profiles the areas share. Constants only
  catalog         the four areas put together: SOUNDS, BINDINGS,
                  SOUND_ATTENUATION, the names by folder, and the SOUND
                  SETTINGS tab's rows in order (TAB_ORDER, SOUND_STATS)
  play            the graph fragment that plays one of an array of takes
  bind            a binding's value; defaults_for() for a Blueprint's own
                  builder; apply_bindings() onto the Blueprints as they stand
  waves           import_sounds(): the WAVs of assets/generated/sounds as
                  SoundWaves, looping and virtualisation flags
  attenuation     the USoundAttenuation assets, and each wave's link to its own
  mix             a SoundClass per sound on its waves, and A_Mix_Game, the
                  mix the HUD overrides their volumes in
  tuning          sound_tuning.csv: each sound's volume; what the menu's SOUND
                  SETTINGS tab saves and the HUD's table is built from
  build           the build's three steps: build_sound_assets(),
                  apply_sound_bindings(), apply_sound_volumes()

Checks: combat/verify/audio.py and sound_mix.py (verify_weapons_and_combat),
world/verify/ambience.py (verify_day_night), npc/verify_voice.py
(verify_npc_blueprints), graphics_menu/sound_tune_checks.py
(verify_graphics_menu); probes/probe_sound_tuning.py, probe_ambience.py,
probe_monster_sounds.py.

SOURCING (outside the editor; sound_candidates/__init__.py maps it)
  sound_candidates/         the candidates, the audition page, THE CHOICE
                            (selection.py) and the install
  fetch_*.py, prepare_sound_candidates.py, build_sound_audition.py,
  read_sound_ratings.py, install_selected_sounds.py, make_creature_sounds.py
"""
