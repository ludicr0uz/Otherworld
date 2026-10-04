"""Candidate sounds, cut from the downloaded packs for listening.

Run by `Scripts/Sound/prepare_sound_candidates.py`, outside the editor. Needs
ffmpeg and numpy. Reads `assets/cache/sounds/`, writes
`assets/generated/sound_candidates/`; nothing in the game reads that folder.

  manifest.py   the table: which candidate is cut from which file, how, and
                each pack's licence
  dsp.py        decode, trim, split, loop, repitch, write: the signal code
  build.py      runs the table and writes the files and SOURCES.md
  audition.py   the HTML page that plays every candidate and every sound the
                game has now (`Scripts/Sound/build_sound_audition.py`)
"""
