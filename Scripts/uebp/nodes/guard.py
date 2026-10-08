"""uebp.nodes.guard -- the game's own RPC guard (C++, the Otherworld module:
Source/Otherworld/Public/OtherworldRpcGuard.h), a component on the player.
What a Server event asks before it does anything (task A5; net/guard.py is
the fragment that calls these).
"""

GUARD_CLASS = "/Script/Otherworld.OtherworldRpcGuard"

# self (the guard), Name -> ReturnValue: may this Server event run now?
FN_GUARD_ALLOW = GUARD_CLASS + ".Allow"
# self, AimPoint -> ReturnValue: could this player's view rest on it?
FN_GUARD_AIM_ALLOWED = GUARD_CLASS + ".AimAllowed"
