"""`python -m advisor_mcp --port 8002`: serve MCP over streamable HTTP."""

from __future__ import annotations

import argparse

from advisor_mcp.server import server


def main() -> None:
    parser = argparse.ArgumentParser(prog="advisor_mcp")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8002)
    args = parser.parse_args()
    server.run(transport="streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
