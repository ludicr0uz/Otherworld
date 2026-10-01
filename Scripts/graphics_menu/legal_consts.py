"""The proprietary notices' words and places (the game is the property of
Ellivian Inc.; see LICENSE.txt at the repository root).

  WBP_MainMenu   LegalNotice: the copyright line and the confidentiality line,
                 bottom centre, outside both panels (title and settings pages)
  WBP_HUD        Watermark: the owner's mark and, when WATERMARK_RECIPIENT is
                 set, who this build was given to; bottom right of Root,
                 outside Body, so it shows over every screen

Static designer text only: no graph reads or writes either. Stamp a shared
build by setting WATERMARK_RECIPIENT and re-running build_graphics_menu.py.
"""

# --- the title screen's notice -------------------------------------------------
LEGAL_NOTICE = "LegalNotice"
LEGAL_COPYRIGHT, LEGAL_CONFIDENTIAL = "LegalCopyright", "LegalConfidential"
LEGAL_COPYRIGHT_TEXT = "© 2026 Ellivian Inc. All rights reserved."
LEGAL_CONFIDENTIAL_TEXT = ("Confidential pre-release build. "
                           "Do not distribute, stream or share.")
LEGAL_FONT = 13.0
LEGAL_BOTTOM = 18.0              # px up from the bottom edge
COL_LEGAL = "(R=0.620000,G=0.640000,B=0.680000,A=1.000000)"

# Both notices lie over the world, bright sand as often as night: a soft drop
# shadow keeps small dim text readable on either.
NOTICE_SHADOW = "(R=0.000000,G=0.000000,B=0.000000,A=0.700000)"
NOTICE_SHADOW_OFFSET = (1.0, 1.0)

# --- the watermark -------------------------------------------------------------
WATERMARK = "Watermark"
WATERMARK_OWNER, WATERMARK_ISSUED = "WatermarkOwner", "WatermarkRecipient"
WATERMARK_TEXT = "ELLIVIAN INC. · CONFIDENTIAL"
WATERMARK_RECIPIENT = ""         # who this build was given to; empty = no line
WATERMARK_RECIPIENT_FORMAT = "ISSUED TO  {}"
WATERMARK_FONT = 13.0
WATERMARK_OPACITY = 0.5
# In from the bottom-right corner: right of the inventory strip (bottom centre)
# and under the loot window (right edge, centred vertically).
WATERMARK_RIGHT, WATERMARK_BOTTOM = 24.0, 14.0
COL_WATERMARK = "(R=1.000000,G=1.000000,B=1.000000,A=1.000000)"


def watermark_lines():
    """(widget name, words) of each watermark line, top to bottom."""
    lines = [(WATERMARK_OWNER, WATERMARK_TEXT)]
    if WATERMARK_RECIPIENT.strip():
        lines.append((WATERMARK_ISSUED,
                      WATERMARK_RECIPIENT_FORMAT.format(WATERMARK_RECIPIENT.strip())))
    return lines
