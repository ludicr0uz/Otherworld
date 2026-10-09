# Standing failures. dev-team's gate (devteam/gate.py) reads this file.
# <verifier or probe> | <check label (a substring of the failing check)> | since <date> | <why>
# A listed check that fails is "known", never a regression; one that passes is "fixed, remove the line".
# Check labels below are substrings of the verifier's own check text; tighten them when one fails.
probe_headshot.py | headshot | since 2026-10-09 | flaky in -game (timing of the shot against the spawn)
probe_gas_traversal.py | traversal | since 2026-10-09 | flaky in -game (nothing traversable is placed)
