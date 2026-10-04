"""Candidate sounds, cut from the downloaded packs for listening.

Run by `Scripts/Sound/prepare_sound_candidates.py`, outside the editor. Needs
ffmpeg and numpy. Reads `assets/cache/sounds/`, writes
`assets/generated/sound_candidates/`; nothing in the game reads that folder.

  manifest.py   the table: which candidate is cut from which file, how, and
                each pack's licence
  manifest_archive.py   the second table: the Sonniss 2016-2019 files and the
                Freesound previews
  manifest_guns.py      the third table: gunshots for the five guns, near and far
  sonniss_archive.py    which files of the 2016-2019 Sonniss bundles are
                wanted, and the fetch (`Scripts/Sound/fetch_sonniss_archive.py`)
  remote_zip.py         one member of a zip on a web server, by HTTP range
  freesound_previews.py CC0 Freesound previews for what the packs lack
                (`Scripts/Sound/fetch_freesound_previews.py`)
  dsp.py        decode, trim, split, loop, repitch, write: the signal code
  build.py      runs the table and writes the files and SOURCES.md
  ratings.py    the page's ratings and notes, read out of Chrome's storage
                into assets/generated (`Scripts/Sound/read_sound_ratings.py`)
  selection.py  THE CHOICE: which takes were picked for which use, and which
                of them the game plays; the builders read the names from it
  install.py    writes the chosen takes to assets/generated/sounds, as the
                sounds the game imports (`Scripts/Sound/install_selected_sounds.py`)
  free_packs.py the small CC0 packs fetched whole, and what is fetched by
                hand (`Scripts/Sound/fetch_free_packs.py`)
  audition.py   the HTML page that plays every candidate and every sound the
                game has now, with a rating a take (`Scripts/Sound/build_sound_audition.py`)
  audition_selected.py  the page's second tab: the selection, use by use
"""
