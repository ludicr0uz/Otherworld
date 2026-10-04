"""Freesound previews: something to listen to before anyone logs in.

Freesound gives a sound's original file only to a signed-in account, but its
MP3 preview to anybody. This searches the CC0 half of Freesound for each gap
in the table, and saves the best-rated results' previews under
`assets/cache/sounds/freesound_previews/<need>/`, named by their Freesound id.

A preview is for judging, not for shipping: it is a ~128 kbps MP3. A take
that is liked is downloaded as its original, by hand, from the page its id
names (`index.json` holds each one's page).
"""

import html
import json
import os
import re
import time
import urllib.parse
import urllib.request

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
OUT_DIR = os.path.join(_PROJECT_DIR, "assets", "cache", "sounds", "freesound_previews")
INDEX_PATH = os.path.join(OUT_DIR, "index.json")

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15"
SEARCH = "https://freesound.org/search/?"
CC0 = 'license:"Creative Commons 0"'
CC0_MARK = "creativecommons.org/publicdomain/zero"
PAUSE_S = 2.5   # the site answers 429 to anything quicker

# (need, query, longest take in seconds, how many). A need is one folder.
NEEDS = (
    ("match_strike", "match strike", 10, 5),
    ("matchbox", "matchbox", 8, 3),
    ("eating", "eating bite chew", 15, 5),
    ("drinking", "drinking gulp", 12, 5),
    ("owl", "owl hoot", 40, 5),
    ("wolf_howl", "wolf howl", 40, 3),
    ("tree_creak", "tree creak", 40, 4),
    ("branch_snap", "branch snap", 8, 5),
    ("axe_chop", "axe chop wood", 30, 6),
    ("heartbeat", "heartbeat", 30, 4),
    ("knife_stab", "knife stab flesh", 6, 5),
    ("body_fall", "body fall ground", 6, 4),
    ("bullet_dirt", "bullet impact dirt", 6, 4),
    ("torch", "torch fire whoosh", 15, 3),
    ("zombie_groan", "zombie groan", 12, 6),
    ("zombie_death", "zombie death", 12, 3),
    ("creature_growl", "creature growl", 12, 5),
    ("ui_click", "menu click", 2, 5),
    ("ui_confirm", "menu confirm select", 3, 4),
    # The third round: what two rounds of packs still left open. The electronic
    # menu sounds and the cinematic drones were all turned down, so these ask
    # for the opposite: paper, leather and wood for the menu, wind and low
    # tone for the bed.
    ("ui_soft_click", "soft click", 1, 6),
    ("ui_page", "page turn", 3, 5),
    ("ui_pouch", "leather pouch open", 4, 4),
    ("tension_dark_ambient", "dark ambient drone", 240, 6),
    ("tension_eerie_wind", "eerie wind", 240, 5),
    ("tension_low_rumble", "low rumble ambience", 240, 4),
    ("player_pain", "male pain grunt", 4, 6),
    ("zombie_hurt", "monster hurt", 5, 5),
    ("drinking_glug", "glug water bottle", 12, 5),
)

_RESULT = re.compile(
    r'data-sound-id="(\d+)".*?data-username="([^"]+)".*?data-mp3="([^"]+)".*?'
    r'data-title="([^"]*)".*?data-duration="([\d.]+)"', re.S)


def _get(url):
    time.sleep(PAUSE_S)
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(request, timeout=60).read()


def _search(query):
    """`[(id, author, preview_url, title, seconds)]`, best rated first, CC0 only."""
    params = urllib.parse.urlencode({"q": query, "f": CC0, "s": "Rating (highest first)"})
    page = _get(SEARCH + params).decode("utf-8", "replace")
    seen, results = set(), []
    for sid, author, mp3, title, seconds in _RESULT.findall(page):
        if sid not in seen:   # a result's player is in the page more than once
            seen.add(sid)
            results.append((sid, author, mp3.replace("-lq.mp3", "-hq.mp3"),
                            html.unescape(title), float(seconds)))
    return results


def fetch(only=(), log=print):
    """Save the previews not already held, for the needs named in `only` or
    for all of them. Returns the index it wrote."""
    unknown = set(only) - {need for need, _q, _s, _n in NEEDS}
    if unknown:
        raise ValueError(f"no such need: {sorted(unknown)}")
    index = {}
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH) as held:
            index = json.load(held)
    for need, query, longest, wanted in NEEDS:
        if only and need not in only:
            continue
        have = [k for k, v in index.items() if v["need"] == need]
        if len(have) >= wanted:
            continue
        taken = len(have)
        for sound_id, author, preview, title, seconds in _search(query):
            if taken >= wanted:
                break
            if sound_id in index or not 0.15 <= seconds <= longest:
                continue
            page = _get(f"https://freesound.org/s/{sound_id}/").decode("utf-8", "replace")
            if CC0_MARK not in page:
                continue   # the search filter said CC0; the sound's own page did not
            name = f"{sound_id}_{re.sub(r'[^A-Za-z0-9]+', '_', author).strip('_')}.mp3"
            path = os.path.join(OUT_DIR, need, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as out:
                out.write(_get(preview))
            index[sound_id] = dict(
                need=need, file=f"{need}/{name}", title=title, author=author,
                seconds=seconds, licence="CC0",
                page=f"https://freesound.org/people/{author}/sounds/{sound_id}/")
            taken += 1
            log(f"{need:15s} {seconds:5.1f}s  {sound_id}  {title[:60]}")
            with open(INDEX_PATH, "w") as out:
                json.dump(index, out, indent=1, sort_keys=True)
    return index
