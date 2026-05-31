"""CLI test client for the core service.

Examples:
    python -m core.cli                       # hello, then open with no file
    python -m core.cli --file some.belegtool # hello, then open the file
    python -m core.cli --name test           # connect to a suffixed pipe
"""

import argparse
import json

from core.client import CoreClient
from core.pipe import default_pipe_name


def main():
    ap = argparse.ArgumentParser(description="BelegTool core CLI client")
    ap.add_argument("--file", default=None, help="path to a .belegtool/PDF to open")
    ap.add_argument("--name", default="", help="pipe-name suffix")
    args = ap.parse_args()

    with CoreClient(default_pipe_name(args.name)) as client:
        hello = client.hello()
        print("hello ->", json.dumps(hello, ensure_ascii=False))

        opened = client.open(path=args.file, session=hello.get("session"))
        tree = opened.get("tree")
        summary = "(no file)" if tree is None else f"root '{tree.get('name')}' with {len(tree.get('children', []))} top-level node(s)"
        print("open  ->", "ok" if opened.get("ok") else "FAIL", "|", summary)


if __name__ == "__main__":
    main()
