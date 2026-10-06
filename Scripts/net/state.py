"""Builds BP_OtherworldPlayerState and BP_OtherworldGameState and names them
on the GameMode (state_consts.py says what each holds and why).

Variables only, every one Replicated: the server's graphs write them
(combat/death.py, and the HUD where its machine owns the GameState) and each
client reads its own copy (state_graph.py). Both actors replicate already:
the engine's PlayerState and GameStateBase do.

The parent is GameStateBase, not GameState: BP_ThirdPersonGameMode is a
GameModeBase, and the engine refuses to pair the two families.

build_weapons_and_combat.py calls build_state() before any Blueprint whose
graph casts to either.
"""

import unreal

from combat.paths import GAME_MODE_BP_PATH
from net import state_consts as S
from uebp import net
from uebp.graph import BEL, BGE, _apply_defaults, _assets, _create_blueprint
from uebp.vars import declare, defaults


def _build(path, parent, table):
    bp = _create_blueprint(path, parent)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    if not ed:
        raise RuntimeError(f"{path} has no EventGraph")
    # Declare, then replicate: a re-declare drops the flag (uebp/CLAUDE.md).
    declare(ed, table)
    for var in table:
        net.replicate(bp, var)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{path} failed to compile")
    _apply_defaults(bp, defaults(table))
    return bp


def _attach(player_bp, game_bp):
    """GameMode.PlayerStateClass and GameStateClass: every level's, since
    BP_ThirdPersonGameMode is the project's one game mode."""
    eas = _assets()
    mode = eas.load_asset(GAME_MODE_BP_PATH)
    if not mode:
        raise RuntimeError(f"could not load {GAME_MODE_BP_PATH}")
    cdo = unreal.get_default_object(BEL.generated_class(mode))
    wanted = {S.PLAYER_STATE_PROP: BEL.generated_class(player_bp),
              S.GAME_STATE_PROP: BEL.generated_class(game_bp)}
    if all(cdo.get_editor_property(k) == v for k, v in wanted.items()):
        return
    for prop, value in wanted.items():
        cdo.set_editor_property(prop, value)
    if not BEL.compile_blueprint(mode):
        raise RuntimeError("BP_ThirdPersonGameMode failed to compile")
    eas.save_loaded_asset(mode)
    fresh = unreal.get_default_object(BEL.generated_class(mode))
    for prop, value in wanted.items():
        if fresh.get_editor_property(prop) != value:
            raise RuntimeError(f"GameMode.{prop} did not stick")


def build_state():
    """Create (or re-declare) both Blueprints. Returns (player state, game state)."""
    player_bp = _build(S.PLAYER_STATE_BP_PATH, unreal.PlayerState, S.PLAYER_TABLE)
    game_bp = _build(S.GAME_STATE_BP_PATH, unreal.GameStateBase, S.GAME_TABLE)
    _attach(player_bp, game_bp)
    return player_bp, game_bp
