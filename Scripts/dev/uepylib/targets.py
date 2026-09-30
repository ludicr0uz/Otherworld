"""TargetResult: one script (or -c statement) and what running it produced.

Every transport -- inbox, multicast, cold boot -- reports through this, so the
CLI prints, summarises and exits the same way whichever one ran the work.
"""

import os


class TargetResult(object):

    def __init__(self, label, ok, seconds, text):
        self.label = label          # the script's basename, or "<statement>"
        self.ok = bool(ok)          # the transport's verdict: ran without raising
        self.seconds = float(seconds or 0.0)
        self.text = text or ""      # everything the script logged or printed


def label_for(kind, value):
    return os.path.basename(value) if kind == "file" else "<statement>"
