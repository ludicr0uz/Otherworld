"""verify_graphics_menu.py's checks for the title level (Scripts/title) in
the HUD's graph: BeginPlay shows the title on that level alone, and on it
Tick dresses the figure once from the saved profile (title_figure.py)."""

from graphics_menu import profile_consts as PC
from graphics_menu import umg_consts as UC
from graphics_menu.menu_main_checks import _arm
from graphics_menu.mode_checks import _deep, _upstream
from graphics_menu.pause_checks import _feeds, _pins, _sets, _sources, _title, _value
from graphics_menu.title_figure import TITLE_DRESSED_VAR, TITLE_STOWED_VAR
from combat.ask_consts import ASK_MOVE, FROM_PARAM, TO_PARAM
from combat.record_vars import VIEW_WORN
from combat.slot_tuning import HAND, PRIMARY
from combat.weapon_component.vars import Held as HELD_VAR
from title.paths import TITLE_LEVEL_NAME


def _check_begin(check, nodes, skip_switch):
    eq = [n for n in nodes if {"A", "B"} <= _pins(n) and _value(n, "B") == TITLE_LEVEL_NAME]
    by_level = [n for n in eq if any("Level" in t for t in _feeds(n, "A"))]
    gates = [g for g in nodes if "Condition" in _pins(g) and any(e in _deep(g) for e in eq)]
    skipped = [c for g in gates for c in _deep(g)
               if "Substring" in _pins(c) and _value(c, "Substring") == skip_switch]
    skips = [n for n in _sets(nodes, UC.GAME_STARTED_VAR)
             if _value(n, UC.GAME_STARTED_VAR) == "true"
             and any(n in _arm(g, False) for g in gates)]
    check(f"BeginPlay shows the title on {TITLE_LEVEL_NAME} alone (GetCurrentLevelName "
          f"against it, beside the {skip_switch} switch): on any other level the "
          f"game starts at once",
          len(eq) == 1 and len(by_level) == 1 and len(gates) == 1 and len(skipped) == 1
          and len(skips) == 1,
          f"{len(eq)} compares ({len(by_level)} off the level name), {len(gates)} gates, "
          f"{len(skipped)} switch tests, {len(skips)} starts off the false arm")


def _check_figure(check, nodes):
    wears = [n for n in nodes if _title(n).replace(" ", "") == VIEW_WORN
             and {"Slot", "Class", "self"} <= _pins(n)]
    mine = [n for n in wears
            if any(_title(u) == f"Set {TITLE_DRESSED_VAR}" for u in _upstream(n))]
    loaded = [n for n in mine
              if any("Load" in _title(u) and _value(u, "SlotName") == PC.PROFILE_SLOT
                     for u in _upstream(n))]
    on_title = [n for n in mine
                if any(_title(g) == "Branch" and f"Get {UC.GAME_STARTED_VAR}" in _feeds(g, "Condition")
                       and n in [d for a in _arm(g, False) for d in [a] + _downstream(a, nodes)]
                       for g in _upstream(n))]
    check(f"on the title, Tick dresses the figure from the saved profile: one {VIEW_WORN} "
          f"behind {TITLE_DRESSED_VAR} and the profile's load, off GameStarted's false arm",
          len(mine) == 1 and len(loaded) == 1 and len(on_title) == 1,
          f"{len(wears)} calls, {len(mine)} the figure's, {len(loaded)} loaded, "
          f"{len(on_title)} on the title")
    raised = [n for n in _sets(nodes, TITLE_DRESSED_VAR) if _value(n, TITLE_DRESSED_VAR) == "true"]
    once = [n for n in raised if any(f"Get {TITLE_DRESSED_VAR}" in _feeds(c, "A")
                                     for g in _upstream(n) for c in _sources(g, "Condition"))]
    check(f"...once: {TITLE_DRESSED_VAR} is raised behind a Branch on itself",
          len(raised) == 1 and len(once) == 1, f"{len(raised)} raised, {len(once)} gated")


def _check_stowed(check, nodes):
    moves = [n for n in nodes if _title(n).split(" ")[0] == ASK_MOVE
             and {FROM_PARAM, TO_PARAM, "self"} <= _pins(n)]
    mine = [n for n in moves
            if any(_title(u) == f"Set {TITLE_STOWED_VAR}" for u in _upstream(n))]
    hand = [n for n in mine if _value(n, FROM_PARAM) in (str(HAND), "")
            and _value(n, TO_PARAM) == str(PRIMARY)]
    # The wear is the loop's body, so what follows the loop has the loop
    # itself upstream, not the ViewWorn call.
    after = [n for n in hand if any("ForEach" in _title(u).replace(" ", "")
                                    for u in _upstream(n))]
    raised = [n for n in _sets(nodes, TITLE_STOWED_VAR) if _value(n, TITLE_STOWED_VAR) == "true"]
    gates = [c for n in raised for g in _upstream(n) for c in _sources(g, "Condition")]
    once = [c for c in gates if f"Get {TITLE_STOWED_VAR}" in _feeds(c, "A")]
    holding = [c for c in gates if "Object" in _pins(c)
               and f"Get {HELD_VAR}" in _feeds(c, "Object")]
    check(f"...and stows the issued gun, dressed or bare: one {ASK_MOVE} from the hand "
          f"({HAND}) to the primary slot ({PRIMARY}), after the {VIEW_WORN} loop (the "
          f"loop upstream of it) -- the figure holds nothing",
          len(mine) == 1 and len(hand) == 1 and len(after) == 1,
          f"{len(moves)} moves, {len(mine)} the figure's, {len(hand)} hand->primary, "
          f"{len(after)} after the loop")
    check(f"...once ({TITLE_STOWED_VAR}, behind a Branch on itself), and only when "
          f"something is held (IsValid on {HELD_VAR}): the gun reaches the hand after "
          f"the loadout is issued, and a move asked sooner finds the hand empty",
          len(raised) == 1 and len(once) == 1 and len(holding) == 1,
          f"{len(raised)} raised, {len(once)} gated on itself, {len(holding)} on {HELD_VAR}")


def _downstream(n, nodes):
    """Every node ``n``'s exec leads to."""
    return [m for m in nodes if n in _upstream(m)]


def check_title_level(check, nodes, skip_switch):
    _check_begin(check, nodes, skip_switch)
    _check_figure(check, nodes)
    _check_stowed(check, nodes)
