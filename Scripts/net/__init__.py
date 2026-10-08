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
    random_consts.py  the audit of every random draw a graph makes: state (the
                server's, rolled once) or cosmetic (each machine's own)
    random_checks.py  the verifiers' check that no builder draws outside it
    relevancy_consts.py  what a server sends about each kind of actor and how
                often (A2): the cull distance and the update rates, one row
                per kind (characters, items, campfires)
    relevancy.py  writes a row onto a class's defaults and reads it back
    guard_consts.py  what a Server event may be asked (A5): each event's asks
                a second, when refusals close a connection, the aim a shot
                may name; the RPC guard's table
    guard.py    the fragment at the head of every Server event: Allow, and
                the shot's AimAllowed, asked of the player's guard component
"""
