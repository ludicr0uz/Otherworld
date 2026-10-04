"""The ratings given on the audition page, read out of the browser.

The page keeps its ratings and notes in the browser's local storage, which
for Chrome is a LevelDB folder in the profile. Nothing on the page can write
a file, so this reads that folder (its logs and its packed tables), and of
the records of the page's two keys takes the last one written. It copies them to
`assets/generated/sound_ratings.json` and `sound_notes.json`, and says what
changed since the copy before.

It reads Chrome's default profile only, and only those two keys. A page
opened in another browser has its ratings somewhere else: copy the list at
the foot of the page instead.
"""

import glob
import json
import os

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
GENERATED_DIR = os.path.join(_PROJECT_DIR, "assets", "generated")
RATINGS_PATH = os.path.join(GENERATED_DIR, "sound_ratings.json")
NOTES_PATH = os.path.join(GENERATED_DIR, "sound_notes.json")
CHROME_STORE = os.path.expanduser(
    "~/Library/Application Support/Google/Chrome/Default/Local Storage/leveldb")
RATINGS_KEY, NOTES_KEY = "otherworld-sound-ratings", "otherworld-sound-notes"
LOG_BLOCK, LOG_HEADER = 32768, 7
TABLE_FOOTER = 48


def _varint(data, at):
    value = shift = 0
    while True:
        byte = data[at]
        at += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, at
        shift += 7


def _unsnappy(data):
    """Snappy's block format, which LevelDB packs its table blocks with."""
    _length, at = _varint(data, 0)
    out = bytearray()
    while at < len(data):
        tag = data[at]
        at += 1
        kind = tag & 3
        if kind == 0:
            size = tag >> 2
            if size >= 60:
                extra = size - 59
                size = int.from_bytes(data[at:at + extra], "little")
                at += extra
            out += data[at:at + size + 1]
            at += size + 1
            continue
        if kind == 1:
            size, offset = ((tag >> 2) & 7) + 4, ((tag >> 5) << 8) | data[at]
            at += 1
        else:
            width = 2 if kind == 2 else 4
            size, offset = (tag >> 2) + 1, int.from_bytes(data[at:at + width], "little")
            at += width
        for _ in range(size):      # a copy may overlap what it writes
            out.append(out[-offset])
    return bytes(out)


def _block(raw, offset, size):
    body = raw[offset:offset + size]
    return _unsnappy(body) if raw[offset + size] == 1 else body


def _entries(block):
    """A table block's (key, value) pairs: keys are stored as what they do
    not share with the key before."""
    restarts = int.from_bytes(block[-4:], "little")
    end, at, key = len(block) - 4 * (restarts + 1), 0, b""
    while at < end:
        shared, at = _varint(block, at)
        fresh, at = _varint(block, at)
        length, at = _varint(block, at)
        key = key[:shared] + block[at:at + fresh]
        at += fresh
        yield key, block[at:at + length]
        at += length


def _table_records(path):
    """(sequence, key, value) for every live record of a .ldb table."""
    with open(path, "rb") as f:
        raw = f.read()
    footer = raw[-TABLE_FOOTER:]
    _meta_offset, at = _varint(footer, 0)
    _meta_size, at = _varint(footer, at)
    index_offset, at = _varint(footer, at)
    index_size, at = _varint(footer, at)
    for _last_key, handle in _entries(_block(raw, index_offset, index_size)):
        offset, at = _varint(handle, 0)
        size, _ = _varint(handle, at)
        for key, value in _entries(_block(raw, offset, size)):
            trailer = int.from_bytes(key[-8:], "little")
            if trailer & 0xFF == 1:           # a value, not a deletion
                yield trailer >> 8, key[:-8], value


def _log_records(path):
    """(sequence, key, value) for every write in a .log: batches of puts and
    deletes, each batch with the sequence of its first write."""
    with open(path, "rb") as f:
        raw = f.read()
    stream, pos = bytearray(), 0
    while pos + LOG_HEADER <= len(raw):
        left = LOG_BLOCK - pos % LOG_BLOCK
        if left < LOG_HEADER:
            pos += left
            continue
        length = int.from_bytes(raw[pos + 4:pos + 6], "little")
        stream += raw[pos + LOG_HEADER:pos + LOG_HEADER + length]
        pos += LOG_HEADER + length
    data, at = bytes(stream), 0
    while at + 12 <= len(data):
        sequence = int.from_bytes(data[at:at + 8], "little")
        count = int.from_bytes(data[at + 8:at + 12], "little")
        at += 12
        for i in range(count):
            kind = data[at]
            length, at = _varint(data, at + 1)
            key = data[at:at + length]
            at += length
            if kind == 1:
                length, at = _varint(data, at)
                yield sequence + i, key, data[at:at + length]
                at += length


def _latest(key):
    """The newest JSON object stored under the page's `key`, or None. Chrome
    only rewrites a key whose value changed, so the notes can sit in an old
    packed table while the ratings are in the newest log: every file is read
    and the highest sequence wins."""
    needle, best = key.encode(), (-1, None)
    for path in glob.glob(CHROME_STORE + "/*.ldb") + glob.glob(CHROME_STORE + "/*.log"):
        records = _log_records(path) if path.endswith(".log") else _table_records(path)
        try:
            for sequence, name, value in records:
                if name.endswith(needle) and sequence > best[0]:
                    best = (sequence, value)
        except (IndexError, ValueError):
            continue      # a file Chrome is in the middle of writing
    if best[1] is None:
        return None
    # The value's first byte says how its text is stored.
    text = best[1][1:].decode("utf-16-le" if best[1][0] == 0 else "latin1")
    return json.loads(text)


def _load(path):
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def read():
    """Copy the page's ratings and notes to assets/generated. Returns
    `(ratings, notes, changed)`, `changed` being the take ids whose rating
    or note differs from the copy before."""
    ratings, notes = _latest(RATINGS_KEY), _latest(NOTES_KEY) or {}
    if ratings is None:
        raise RuntimeError(f"no ratings under {CHROME_STORE}: was the page opened in Chrome?")
    before, noted = _load(RATINGS_PATH), _load(NOTES_PATH)
    changed = sorted(k for k in set(before) | set(ratings) | set(noted) | set(notes)
                     if before.get(k) != ratings.get(k) or noted.get(k) != notes.get(k))
    for path, value in ((RATINGS_PATH, ratings), (NOTES_PATH, notes)):
        with open(path, "w") as out:
            json.dump(value, out, indent=1, sort_keys=True)
    return ratings, notes, changed
