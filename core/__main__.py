"""Run the core server:  python -m core  [--name <pipe-suffix>]

Starts the named-pipe server and blocks until Ctrl+C.
"""

import argparse
import time

from core import CORE_VERSION
from core.pipe import default_pipe_name
from core.server import CoreServer


def main():
    ap = argparse.ArgumentParser(description="BelegTool headless core (Step 0a)")
    ap.add_argument("--name", default="", help="pipe-name suffix (default: per-user)")
    args = ap.parse_args()

    pipe_name = default_pipe_name(args.name)
    server = CoreServer(pipe_name)
    server.start()
    print(f"BelegTool core {CORE_VERSION} listening on {pipe_name}")
    print("Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nstopping…")
        server.stop()


if __name__ == "__main__":
    main()
