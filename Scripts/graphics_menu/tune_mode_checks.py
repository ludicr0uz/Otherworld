"""verify_graphics_menu.py's checks for the tuning tabs by mode (task M32:
tune_mode.py on the HUD, game_tuner.py on the GameState).

    check_tune_mode     the HUD: a gameplay tab's cell moves only behind the
                        GameState's DevTuning; a client's table goes through
                        AskTune and single player's into its save slot; the
                        kept gameplay tables load in single player only; the
                        hint line says why the rows are read-only; the cheat
                        spawns only where this machine owns the game
    check_game_tuner    BP_GameTuner: on the GameState, the built tables, the
                        flag from the native switch, each inbox taken by
                        length and emptied, behind the authority switch
"""

import unreal

from combat import ask_consts as AC
from combat.gun_tuning import TUNE_STATS
from combat.verify.common import component_template
from graphics_menu import dev_consts as DC
from graphics_menu import game_tuner_consts as TC
from graphics_menu.game_tuner import tuner_defaults
from graphics_menu.pause_checks import _feeds, _pins, _sets, _sources, _title, _value
from graphics_menu.tune_tab import READ_ONLY_HINT
from graphics_menu.tune_tabs import TABS
from graphics_menu.umg_checks import text_literal
from net import state_consts as S
from npc.monster_tuning import MONSTER_STATS

BEL = unreal.BlueprintEditorLibrary
BGE = unreal.BlueprintGraphEditor
PIN = unreal.BlueprintGraphPinLibrary

DEV_TUNING = f"Get {S.DevTuning}"


def _into(node):
    """What runs ``node``: (the node, the name of its exec pin taken)."""
    pin = BEL.find_input_pin(node, "execute") or BEL.find_input_pin(node, "Execute")
    return [(PIN.get_owning_node(q), str(PIN.get_pin_name(q)))
            for q in (pin.list_connected_pins() if pin else [])]


def _arms(node, limit=40):
    """Every Branch upstream of ``node`` by exec, as (what its Condition is
    fed by, the arm taken), nearest first."""
    arms, seen, todo = [], [], [node]
    while todo and len(seen) < limit:
        cur = todo.pop(0)
        for src, pin in _into(cur):
            if src in seen:
                continue
            seen.append(src)
            todo.append(src)
            if "Condition" in _pins(src):
                arms.append((tuple(_feeds(src, "Condition")), pin))
    return arms


def _behind(node, title, arm, limit=40):
    return any(title in feeds and pin == arm for feeds, pin in _arms(node, limit))


def _check_tab(check, nodes, tab):
    values = f"Get {tab.values_var}"
    # The nudge's write is an Array_Set of the table at a computed index, the
    # one behind the gate (the guns' grip rows and the graphics tab's pick
    # write cells of their own, which are this machine's).
    writes = [n for n in nodes if {"TargetArray", "Index", "Item"} <= _pins(n)
              and values in _feeds(n, "TargetArray") and _sources(n, "Index")]
    gated = [n for n in writes if _behind(n, DEV_TUNING, "then", 6)]
    asks = [n for n in nodes if _title(n).replace(" ", "") == AC.ASK_TUNE
            and "self" in _pins(n) and values in _feeds(n, "Values")]
    saves = [n for n in nodes if {"SlotName", "SaveGameObject"} <= _pins(n)
             and _value(n, "SlotName") == tab.keep_slot]
    loads = [n for n in nodes if {"SlotName", "UserIndex"} <= _pins(n)
             and "SaveGameObject" not in _pins(n) and "Exist" in _title(n)
             and _value(n, "SlotName") == tab.keep_slot]
    alone = [n for n in loads if _behind(n, "IsStandalone", "then", 3)]
    if not tab.gameplay:
        check(f"{tab.title_text} is this machine's own: its nudge asks no GameState, "
              "sends nothing, and its kept table loads in any mode",
              writes and not gated and not asks and not alone,
              f"{len(writes)} writes, {len(gated)} gated, {len(asks)} asks, {len(alone)} alone")
        return
    check(f"{tab.title_text}: a nudge moves a cell only where the GameState's "
          f"{S.DevTuning} is true", len(gated) == 1,
          f"{len(writes)} writes, {len(gated)} gated")
    index = [_value(n, "Table") or "0" for n in asks]
    check(f"...a client then sends the whole table ({AC.ASK_TUNE}, table "
          f"{tab.table_index}: {tab.gameplay}), where this machine has no authority "
          "over the GameState",
          index == [str(tab.table_index)]
          and all(_behind(n, "HasAuthority", "else", 4) for n in asks), str(index))
    check("...and single player keeps it in its save slot instead, and loads the "
          "kept table at BeginPlay in single player only",
          len(saves) == 1 and _behind(saves[0], "HasAuthority", "then", 12)
          and len(loads) == 1 and len(alone) == 1,
          f"{len(saves)} saves, {len(loads)} loads, {len(alone)} behind IsStandalone")


def check_tune_mode(check, nodes):
    for tab in TABS:
        _check_tab(check, nodes, tab)
    texts = [n for n in nodes if {"self", "InText"} <= _pins(n)]
    why = [n for n in texts if text_literal(n) == READ_ONLY_HINT]
    own = [n for n in texts
           if text_literal(n) in {t.hint_text for t in TABS if t.gameplay}]
    count = sum(1 for t in TABS if t.gameplay)
    check("each gameplay tab's hint line reads its own words where the tables may "
          "be tuned, and why they are read-only where not",
          len(why) == count and all(_behind(n, DEV_TUNING, "else", 2) for n in why)
          and len(own) == count and all(_behind(n, DEV_TUNING, "then", 2) for n in own),
          f"{len(why)} read-only, {len(own)} own")
    # The cheat: its first write after the request is lowered.
    first = [n for n in _sets(nodes, DC.DEV_HAS_GUN_VAR)
             if any(_title(src) == "Branch" and "HasAuthority" in _feeds(src, "Condition")
                    and pin == "then" for src, pin in _into(n))]
    lowered = [n for n in _sets(nodes, DC.DEV_GUNS_REQUEST_VAR)
               if _value(n, DC.DEV_GUNS_REQUEST_VAR) == "false"]
    check("the dev-all-guns cheat spawns only where this machine has authority over "
          "the GameState (single player): a client's request is lowered and dropped",
          len(first) == 1 and len(lowered) == 1, f"{len(first)} gated, {len(lowered)} lowered")


def _same(a, b):
    a, b = list(a), list(b)
    return len(a) == len(b) and all(
        abs(x - y) < 1e-6 if isinstance(y, float) else x == y for x, y in zip(a, b))


def check_game_tuner(check):
    bp = unreal.load_asset(TC.GAME_TUNER_BP_PATH)
    check(f"{TC.GAME_TUNER_BP_PATH} exists", bool(bp))
    if not bp:
        return
    state = unreal.load_asset(S.GAME_STATE_BP_PATH)
    comp = component_template(state, TC.GAME_TUNER_COMPONENT)
    check(f"BP_OtherworldGameState carries it ({TC.GAME_TUNER_COMPONENT}): on a server, "
          "where there is no HUD, it is what applies a tuned table",
          bool(comp) and comp.get_class() == BEL.generated_class(bp),
          str(comp.get_class().get_name() if comp else None))
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    want = tuner_defaults()
    off = [str(tab.values_var) for tab in TC.GAMEPLAY_TABS
           if not _same(cdo.get_editor_property(tab.values_var), want[tab.values_var])]
    check("...starting on the built tables, as the HUD's tabs do", not off, str(off))

    nodes = BGE.get_graph_editor_by_name(bp, "EventGraph").list_all_nodes()
    flags = _sets(nodes, S.DevTuning)
    check(f"BeginPlay, with authority: GameState.{S.DevTuning} := ServerAllowsDevTuning "
          "(single player always, a server only with -AllowDevTuning)",
          len(flags) == 1 and _feeds(flags[0], S.DevTuning) == ["ServerAllowsDevTuning"]
          and any(_title(src) == "Switch Has Authority" and pin == "Authority"
                  for cast, _ in _into(flags[0]) for src, pin in _into(cast)),
          str([_feeds(n, S.DevTuning) for n in flags]))
    switches = [n for n in nodes if _title(n) == "Switch Has Authority"]
    remote = [n for s in switches for p in BEL.list_output_pins(s)
              if str(PIN.get_pin_name(p)) == "Remote" for n in p.list_connected_pins()]
    check("...and nothing in it runs on a client: both events go through Switch Has "
          "Authority, whose Remote arm is bare", len(switches) == 2 and not remote,
          f"{len(switches)} switches, {len(remote)} on Remote")
    for tab, inbox in zip(TC.GAMEPLAY_TABS, S.TUNED):
        box = f"Get {inbox}"
        takes = [n for n in _sets(nodes, tab.values_var) if box in _feeds(n, tab.values_var)]
        sized = [n for n in takes
                 if any(sorted(_feeds(eq, "A") + _feeds(eq, "B")) == ["Length", "Length"]
                        for src, pin in _into(n) if pin == "then"
                        for eq in _sources(src, "Condition"))]
        clears = [n for n in nodes if _title(n) == "Clear" and box in _feeds(n, "TargetArray")]
        touched = [n for n in _sets(nodes, tab.touched_var)
                   if _value(n, tab.touched_var) == "true"]
        check(f"Tick: {inbox}, when not empty, becomes {tab.values_var} only at the "
              f"table's own length, raises {tab.touched_var}, and is emptied either way",
              len(takes) == 1 and len(sized) == 1 and len(clears) == 1
              and len(_into(clears[0])) == 2 and len(touched) == 1,
              f"{len(takes)} takes, {len(sized)} sized, {len(clears)} clears, "
              f"{len(touched)} touched")
    titles = {_title(n) for n in nodes}
    missing = sorted(f"Set {var}" for var in
                     [st[1] for st in TUNE_STATS] + [st[1] for st in MONSTER_STATS]
                     if f"Set {var}" not in titles)
    finds = [n for n in nodes if "ActorClass" in _pins(n) and "OutActors" in
             {str(PIN.get_pin_name(p)) for p in BEL.list_output_pins(n)}
             and "BP_ThirdPersonCharacter" in _value(n, "ActorClass")]
    check("...then the tabs' own applies: every gun and monster stat is written, and "
          "the guns' and the player's tables go onto every player character",
          not missing and len(finds) == 2, f"missing {missing}, {len(finds)} player sweeps")
