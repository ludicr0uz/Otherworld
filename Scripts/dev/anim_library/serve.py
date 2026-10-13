#!/usr/bin/env python3
"""serve.py -- serve Saved/AnimLibrary (the animation library viewer) locally.

    python3 Scripts/dev/anim_library/serve.py [port]

A browser will not fetch the catalogue from a file:// page, so this is a plain
static server on localhost. Ctrl+C stops it.
"""
import functools
import http.server
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "Saved", "AnimLibrary")


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    if not os.path.exists(os.path.join(LIB, "catalog.json")):
        sys.exit("no catalogue: run export_poses.py (uepy --cold) then build_library.py")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=LIB)
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as srv:
        print(f"animation library: http://localhost:{port}/")
        srv.serve_forever()


if __name__ == "__main__":
    main()
