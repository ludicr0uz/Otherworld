"""net: what the builders share to keep one graph right in both modes
(`Scripts/net/CLAUDE.md` has the conventions; `uebp.net` the RPC and
replication authoring).

    pause.py    the world pauses in standalone only: the one SetGamePaused
                fragment every pause and unpause in the game is authored with
    pause_checks.py  the verifiers' check that a graph's pause is behind it
    session_consts.py  the session: BP_OtherworldGameInstance's path and
                variables (the server joined, why the last session ended),
                the default server address, the reasons' words
    game_instance.py  builds that GameInstance: the engine's NetworkError and
                TravelError events write the reason the title shows
    session_checks.py  the verifiers' checks for it
"""
