# Standing failures. dev-team's gate (devteam/gate.py) reads this file.
# <verifier or probe> | <check label (a substring of the failing check)> | since <date> | <why>
# A listed check that fails is "known", never a regression; one that passes is "fixed, remove the line".
# Check labels below are substrings of the verifier's own check text; tighten them when one fails.
# A probe is named as its sweep row is: probe:<probe name>.
#
# The four net probes below fail in the SMOKE set's shared --net launch (one server, two clients,
# every probe in turn with no level reset between them, Lvl_Probe_50m): an earlier probe's
# wanderers are still about, and one probe's leavings fail the next. Each passes run alone
# (run 20261010-140955's final sweep re-ran them one by one: all ok).
probe:probe_net_melee | client 1 sees the body the server stood in front of it | since 2026-10-10 | other probes' wanderers in the shared net launch
probe:probe_net_melee | the probe raised | since 2026-10-10 | the check above raised on its way out
probe:probe_net_pvp | client 1's slash takes the knife's damage off client 2's character | since 2026-10-10 | a wendigo left by an earlier probe killed client 2's character first
probe:probe_net_pvp | client 1's thrown knife takes a thrown blade's damage off client 2 | since 2026-10-10 | the same: client 2's character was dead
probe:probe_net_pvp | client 1 holds its gun and sees the other player | since 2026-10-10 | the same
probe:probe_net_pvp | client 2 holds the server's health for its own character | since 2026-10-10 | the same
probe:probe_net_see_each_other | the probe raised | since 2026-10-10 | the level as the probe before it left it
probe:probe_net_see_each_other | client 2 saw client 1's character move | since 2026-10-10 | the same
probe:probe_net_see_each_other | client 2 walked | since 2026-10-10 | the same
probe:probe_net_survival | the server has both clients' characters | since 2026-10-10 | characters left by earlier probes in the shared launch
probe:probe_net_survival | the probe raised | since 2026-10-10 | the check above raised on its way out
