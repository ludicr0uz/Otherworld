#!/bin/sh
# The full builder sweep, a fingerprint, then the full verifier sweep.
#   Scripts/dev/plans/sweep.sh <fingerprint label>
cd "$(dirname "$0")/../../.." || exit 2
# A warm headless editor of this run's own (uepylib/server.py), unless one is named.
export UEPY_SERVE="${UEPY_SERVE:-$PWD/Saved/uepy/claude}"
python3 Scripts/dev/uepy.py --summary \
  Scripts/build_weapons_and_combat.py Scripts/build_survival.py \
  Scripts/build_npc_blueprints.py Scripts/build_graphics_menu.py \
  Scripts/build_day_night.py Scripts/build_clothing.py || exit 1
python3 Scripts/dev/graph_fingerprint.py "$1" || exit 1
python3 Scripts/dev/uepy.py --summary \
  Scripts/verify_weapons_and_combat.py Scripts/verify_survival.py \
  Scripts/verify_npc_blueprints.py Scripts/verify_graphics_menu.py \
  Scripts/verify_day_night.py Scripts/verify_clothing.py
