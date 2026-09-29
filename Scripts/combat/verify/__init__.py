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
  sights      the two aim keys, each weapon's eye point, the sight camera
  aim_pitch   down the sights the anim BP pitches two spine bones by AimPitch,
              which the component writes from the view pitch x SightBlend
  body_pose   the crouch, prone and guard poses: the anim BP's weighted
              ModifyBones match body_pose.pose_plan, the plan replayed on the
              skeleton lands where each pose says, the component's weights
  block       the guard: its key, the Blocking stance, the fire gate refusing
  stance      crouch/prone: keys, the character may crouch, the Stance toggle,
              the crouch it drives, the footsteps' volume and reach per stance
"""

SECTIONS = (
    "anim_blueprint", "weapons", "grip_fit", "audio", "health", "weapon_inputs", "install",
    "player_body", "blood", "hit_reactions", "ragdoll", "aiming", "sights", "aim_pitch", "body_pose", "block", "stance",
    "settings_and_tuning", "firing", "consume", "drops", "noise", "combat_trace",
)
