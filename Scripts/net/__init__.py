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
    state_consts.py  where state lives: BP_OtherworldPlayerState (one player's:
                kills, is dead) and BP_OtherworldGameState (the world's: debug
                mode, difficulty), their paths and variables
    state.py    builds the two, every variable Replicated, and names them on
                the GameMode
    state_graph.py  how a graph reaches them: the casts every reader shares,
                and server_game_mode, the GameMode behind the authority switch
    state_checks.py  the verifiers' checks: the assets, and that no graph a
                client can run reads the GameMode
    players_consts.py  who is nearby: BPL_Players' path, its two functions
                (LivingPlayers, NearestLivingPlayer) and their pins
    players.py  builds that function library, and the fragments a world actor
                or a wanderer calls it with instead of GetPlayerPawn(0)
    owner_checks.py  the verifiers' check that no graph reads player 0's pawn:
                no GetPlayerPawn in any Blueprint, none named by any builder
    input_checks.py  the verifiers' check that keys are the local player's: a
                HUD polls its owning controller, the weapon component LocalPC
                (combat/weapon_component/local.py), no node asks by player index
"""
