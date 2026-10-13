"""textures.py -- read a texture's role and set off its file name.

A raw download's FBX rarely links its textures, so the names are all there is:
``T_1911_N.png`` is the normal map of the set ``T_1911``, ``AxeAlbedo.png`` the
base colour of ``Axe``. A name that says nothing is still imported, with no
role, and worn by nothing. This is a guess by design; the plan records it and
the import reports which slot got which set, so a wrong one is seen.
"""

import os

from asset_pipeline.fab_raw import rules


def _tail(stem, word):
    """Where ``word`` starts as the end of ``stem``, separators ignored; -1 if it is not."""
    i, left = len(stem), len(word)
    while left:
        i -= 1
        if i < 0:
            return -1
        ch = stem[i]
        if ch in rules.SEPARATORS:
            continue
        if ch.lower() != word[left - 1]:
            return -1
        left -= 1
    return i


def _starts_a_word(stem, i, word):
    if i == 0:
        return True
    before = stem[i - 1]
    if before in rules.SEPARATORS:
        return True
    if len(word) == 1:
        return False
    return before.isdigit() or (stem[i].isupper() and before.islower())


def role_of(stem):
    """(role, set key) for a texture's file stem; (None, stem) when the name says nothing."""
    best = None
    # T_1911_R2: one trailing digit is a variant of the map, not part of the name.
    for candidate in (stem, stem[:-1] if stem[-1:].isdigit() else ""):
        if not candidate:
            continue
        for role, words in rules.ROLE_WORDS:
            for word in words:
                i = _tail(candidate, word)
                if i >= 0 and _starts_a_word(candidate, i, word) and (
                        best is None or len(word) > len(best[1])):
                    best = (role, word, candidate[:i].rstrip(rules.SEPARATORS))
        if best:
            return best[0], best[2]
    return None, stem


def _preference(rel, size):
    """Lower sorts first: a file under textures/, then the shallower, then the larger."""
    parts = rel.lower().split("/")
    return (0 if "textures" in parts[:-1] else 1, len(parts), -size, rel)


def group(files):
    """Sort texture files into sets.

    ``files``: {rel: size}. Returns (sets, loose, repeats): sets is
    {set key: {role: rel}}; loose is the files with no role; repeats is the
    files dropped because another one already fills their set's role.
    """
    sets, loose, repeats = {}, [], []
    for rel in sorted(files, key=lambda r: _preference(r, files[r])):
        stem = os.path.splitext(os.path.basename(rel))[0]
        role, key = role_of(stem)
        if role is None:
            if any(os.path.basename(o) == os.path.basename(rel) for o in loose):
                repeats.append(rel)
            else:
                loose.append(rel)
        elif role in sets.setdefault(key, {}):
            repeats.append(rel)
        else:
            sets[key][role] = rel
    return sets, sorted(loose), sorted(repeats)


def _tokens(name):
    return {t for t in rules.NOT_A_NAME.sub(" ", name).lower().split() if len(t) > 1}


def assign(slot_names, set_keys):
    """Which set each material slot wears: [(set key, how)], one per slot.

    how is "only" (there is one set), "name" (the slot's name shares a word
    with the set's) or "order" (nothing matched: the n-th slot takes the n-th
    set, a guess the import reports).
    """
    keys = sorted(set_keys)
    if not keys:
        return [(None, "none")] * len(slot_names)
    if len(keys) == 1:
        return [(keys[0], "only")] * len(slot_names)
    out = []
    for n, slot in enumerate(slot_names):
        scores = [(len(_tokens(slot) & _tokens(key)), key) for key in keys]
        best = max(score for score, _key in scores)
        winners = [key for score, key in scores if score == best]
        if best and len(winners) == 1:
            out.append((winners[0], "name"))
        else:
            out.append((keys[n % len(keys)], "order"))
    return out
