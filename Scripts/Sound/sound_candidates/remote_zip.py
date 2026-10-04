"""Read single members of a zip that is on a web server, by HTTP range.

The Sonniss bundles are 20 to 35 GB a year and a year holds a few dozen files
this game wants. A zip's directory is at its end and each member is its own
byte range, so `zipfile` can list and extract over the network if the "file"
it is given answers seek and read with range requests.
"""

import io
import urllib.request
import zipfile

READ_AHEAD = 262144     # the directory is read in small steps: batch them
TIMEOUT_S = 120


class HttpFile(io.RawIOBase):
    """A read-only, seekable view of `url`."""

    def __init__(self, url):
        self.url = url
        self.pos = 0
        head = urllib.request.Request(url, method="HEAD")
        self.size = int(urllib.request.urlopen(head, timeout=TIMEOUT_S).headers["Content-Length"])
        self._start, self._data = 0, b""

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=io.SEEK_SET):
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self.pos, io.SEEK_END: self.size}[whence]
        self.pos = base + offset
        return self.pos

    def read(self, count=-1):
        if count < 0:
            count = self.size - self.pos
        count = min(count, self.size - self.pos)
        if count <= 0:
            return b""
        held = self.pos - self._start
        if not (0 <= held and held + count <= len(self._data)):
            last = min(self.size, self.pos + max(count, READ_AHEAD)) - 1
            ranged = urllib.request.Request(
                self.url, headers={"Range": f"bytes={self.pos}-{last}"})
            self._data = urllib.request.urlopen(ranged, timeout=TIMEOUT_S).read()
            self._start, held = self.pos, 0
        self.pos += count
        return self._data[held:held + count]

    def readinto(self, buffer):
        data = self.read(len(buffer))
        buffer[:len(data)] = data
        return len(data)


def open_zip(url):
    return zipfile.ZipFile(io.BufferedReader(HttpFile(url), buffer_size=1 << 20))
