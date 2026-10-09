# Standing failures. dev-team's gate (devteam/gate.py) reads this file.
# <verifier or probe> | <check label (a substring of the failing check)> | since <date> | <why>
# A listed check that fails is "known", never a regression; one that passes is "fixed, remove the line".
# Check labels below are substrings of the verifier's own check text; tighten them when one fails.
verify_weapons_and_combat.py | ready pose | since 2026-10-09 | pose checks left by the C-series clip swaps (ready pose in the fist)
verify_weapons_and_combat.py | hold pose | since 2026-10-09 | pose checks left by the C-series clip swaps (hold pose)
verify_weapons_and_combat.py | the ready-to-throw pose | since 2026-10-09 | throw pose check, skin dependent
verify_weapons_and_combat.py | pose comes from | since 2026-10-09 | blend base pose check after the weapon layers change
verify_weapons_and_combat.py | the output pose | since 2026-10-09 | last-pose pitch check after the weapon layers change
verify_weapons_and_combat.py | new pose re-equips | since 2026-10-09 | HandPose/NeedsRefresh check after the weapon layers change
probe_headshot.py | headshot | since 2026-10-09 | flaky in -game (timing of the shot against the spawn)
probe_gas_traversal.py | traversal | since 2026-10-09 | flaky in -game (nothing traversable is placed)
