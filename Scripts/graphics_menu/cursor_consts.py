"""The mouse cursor in the menus: its buttons, the HUD's variables, the words.

    a menu is up        the cursor shows (the menu, on the title and in play,
                        with its settings page and tuning tabs; death; the
                        loot window)
    over a row          the caret goes to it, once the mouse moves or clicks
    left click          the row's Enter (on the M panel: the row is taken)
    wheel up / down     Right / Left: a slider, the difficulty, a tuning stat
                        (in a scrolling tab: Up / Down, the list follows)

Constants only. The graph is cursor.py; menu_nav.py holds what the key polls
gain (the wheel), and Tick's test for a taken M-panel row.
"""

CLICK_KEY = "LeftMouseButton"
# The wheel stands in for Right (up) and Left (down). Not a second button: the
# right one is the shoulder aim, and it would zoom behind the M panel.
WHEEL_MORE, WHEEL_LESS = "MouseScrollUp", "MouseScrollDown"
CURSOR_KEYS = (CLICK_KEY, WHEEL_MORE, WHEEL_LESS)
# What takes a BACK row with the caret on it (a click on the row does too).
BACK_KEY = "Enter"

# What the frame's screens ask for, and what the controller was last given:
# the input mode is switched only when the two differ.
CURSOR_WANTED_VAR = "CursorWanted"
CURSOR_SHOWN_VAR = "CursorShown"
# Where the cursor was last frame (desktop space, as a widget's cached
# geometry is), and whether it has moved since. A resting cursor must not
# hold the caret against Up/Down.
CURSOR_POS_VAR = "CursorPos"
CURSOR_MOVED_VAR = "CursorMoved"
# The row under the cursor in the list being tested, NO_ROW when none.
CURSOR_ROW_VAR = "CursorRow"
NO_ROW = -1
# Raised by a click on a row of a DrawHUD-polled menu (settings, the
# death menu's hint); the menu's accept lowers it as it serves it, which is
# what lets a probe click without a mouse.
CURSOR_ACCEPT_VAR = "CursorAccept"
# The M panel's row taken this frame (a click on it, or Enter with the caret
# on it), NO_ROW otherwise. Tick serves it on the next frame as that row's
# action; DrawHUD lowers it at the top of every frame.
PAUSE_CLICK_VAR = "PauseClick"

# The weapon component's spent-press latch (combat/weapon_component/consume.py),
# held up while the cursor shows in a running game so a click fires nothing.
TRIGGER_SPENT_VAR = "TriggerSpent"

CURSOR_BOOLS = (CURSOR_WANTED_VAR, CURSOR_SHOWN_VAR, CURSOR_MOVED_VAR, CURSOR_ACCEPT_VAR)
CURSOR_INTS = (CURSOR_ROW_VAR, PAUSE_CLICK_VAR)
