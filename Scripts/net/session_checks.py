"""The verifiers' checks for the session (game_instance.py,
session_consts.py): BP_OtherworldGameInstance keeps the address and the
reason, the engine's two failure events write the reason, the engine is told
to use it, and the saved settings hold the server address.
"""

import os

import unreal

from combat.paths import SETTINGS_BP_PATH
from net import session_consts as S

BEL = unreal.BlueprintEditorLibrary
BGE = unreal.BlueprintGraphEditor
PIN = unreal.BlueprintGraphPinLibrary


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _literal(n, var):
    p = BEL.find_input_pin(n, var)
    return str(p.get_pin_value()) if p and not p.list_connected_pins() else None


def check_session(check):
    bp = unreal.load_asset(S.GAME_INSTANCE_BP_PATH)
    check("BP_OtherworldGameInstance exists, a GameInstance",
          bool(bp) and BEL.get_blueprint_parent_class(bp) == unreal.GameInstance.static_class()
          if hasattr(BEL, "get_blueprint_parent_class")
          else bool(bp) and bp.get_blueprint_parent_class() == unreal.GameInstance.static_class(),
          str(bp))
    if not bp:
        return
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    got = {str(v): cdo.get_editor_property(v) for v in S.TABLE}
    check("it starts in no session: no address, no reason, no join under way",
          got == {str(v): v.default for v in S.TABLE}, str(got))

    nodes = BGE.get_graph_editor_by_name(bp, "EventGraph").list_all_nodes()
    titles = [_title(n) for n in nodes]
    check("it handles the engine's NetworkError and TravelError events",
          sum("NetworkError" in t.replace(" ", "") for t in titles) == 1
          and sum("TravelError" in t.replace(" ", "") for t in titles) == 1,
          str(sorted(t for t in titles if "Event" in t)))
    reasons = sorted(v for n in nodes if _title(n) == f"Set {S.NetReason}"
                     for v in [_literal(n, S.NetReason)] if v is not None)
    want = sorted(list(S.NET_REASONS.values()) + [S.REASON_OTHER] * 3)
    check("a network failure sets the reason the player is told: one line per "
          "ENetworkFailure, the driver's three as the general one",
          reasons == want, str(reasons))
    wired = [n for n in nodes if _title(n) == f"Set {S.NetReason}"
             and _literal(n, S.NetReason) is None]
    check("a travel failure's reason is the engine's name for it",
          len(wired) == 1, str(len(wired)))
    firsts = [n for n in nodes if "Condition" in
              {str(PIN.get_pin_name(p)) for p in BEL.list_input_pins(n)}]
    asks = [_title(PIN.get_owning_node(q)).replace(" ", "") for n in firsts
            for q in BEL.find_input_pin(n, "Condition").list_connected_pins()]
    check("each sets it only while there is none (the first failure is the cause)",
          asks == ["IsEmpty", "IsEmpty"], str(asks))
    ends = sorted((t, _literal(n, v)) for n in nodes for v in (S.Connecting, S.JoinAddress)
                  for t in [_title(n)] if t == f"Set {v}")
    check("...and either ends the join and the session: Connecting false, no address",
          [t for t, _v in ends] == [f"Set {S.Connecting}"] * 2 + [f"Set {S.JoinAddress}"] * 2
          and all(v in ("", "false") for _t, v in ends), str(ends))

    ini = os.path.join(unreal.Paths.project_config_dir(), "DefaultEngine.ini")
    with open(ini, encoding="utf-8") as fh:
        check("DefaultEngine.ini names it as the GameInstanceClass",
              S.GAME_INSTANCE_INI in fh.read().splitlines(), S.GAME_INSTANCE_INI)

    settings = unreal.load_asset(SETTINGS_BP_PATH)
    saved = unreal.get_default_object(BEL.generated_class(settings)).get_editor_property(
        S.SERVER_ADDRESS_VAR) if settings else None
    check(f"BP_Settings keeps the server address, {S.DEFAULT_SERVER_ADDRESS} until changed",
          saved == S.DEFAULT_SERVER_ADDRESS, str(saved))
