"""combat.verify -- reads the saved combat assets back and checks them.

Run through Scripts/verify_weapons_and_combat.py, which calls each module's
run() in SECTIONS order and prints the PASS/FAIL summary.

One module per area, mirroring the builder: a change to combat/<x>.py is
usually checked in verify/<x>.py or the module named for the same feature.
Each check_* function is one section and is self-contained: what it reads it
either loads itself or imports from fixtures (assets several sections share),
and it never relies on a variable another section left behind.

  common      check(), the PASS/FAIL ledger, pin/graph/component readers
  fixtures    shared loaded assets (health, weapon component, characters, ...)
  anim_blueprint  weapons  grip_fit  audio  health  weapon_inputs  install
  player_body  blood  hit_reactions  ragdoll  aiming  settings_and_tuning
  firing  consume  drops  noise  combat_trace
"""

SECTIONS = (
    "anim_blueprint", "weapons", "grip_fit", "audio", "health", "weapon_inputs", "install",
    "player_body", "blood", "hit_reactions", "ragdoll", "aiming",
    "settings_and_tuning", "firing", "consume", "drops", "noise", "combat_trace",
)
