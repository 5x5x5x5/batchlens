#!/usr/bin/env python3
"""One address for the local demo: PlantCraft and every app under their path prefixes.

PlantCraft opens an app inside its own page only when the app is served from the same origin
(in an installed suite, the suite's proxy does this). ``make dev`` has no proxy, so the demo
runs this one:

    python tools/gateway.py 8088 8060 /batchlens/=9100 /hist/=8100

sends ``/batchlens/...`` to port 9100, ``/hist/...`` to 8100 and everything else to 8060, all
on 127.0.0.1. Standard library only.
"""

from __future__ import annotations

import asyncio
import logging
import sys

LOGGER = logging.getLogger("batchlens.gateway")
HOST = "127.0.0.1"
MAX_HEAD = 64 * 1024


def upstream(path: str, routes: dict[str, int], default: int) -> int:
    """The port that serves ``path``: the longest prefix that matches, else the default."""

    for prefix in sorted(routes, key=len, reverse=True):
        if path.startswith(prefix) or path == prefix.rstrip("/"):
            return routes[prefix]
    return default


def one_request(head: bytes) -> bytes:
    """The request head, asking the server to close after answering.

    shortcut: one request per connection, so a connection never carries requests for two
    apps; replace with a real proxy (the suite's own) if the demo ever needs speed.
    """

    lines = head.split(b"\r\n")
    if any(line.lower().startswith(b"upgrade:") for line in lines):
        return head  # a WebSocket keeps its connection
    kept = [line for line in lines[:-2] if not line.lower().startswith(b"connection:")]
    return b"\r\n".join([*kept, b"Connection: close", b"", b""])


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        writer.close()


async def _serve(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter, routes: dict[str, int], default: int
) -> None:
    try:
        head = await reader.readuntil(b"\r\n\r\n")
        path = head.split(b" ", 2)[1].decode("latin-1")
        port = upstream(path.split("?", 1)[0], routes, default)
        back_reader, back_writer = await asyncio.open_connection(HOST, port)
    except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, IndexError, OSError) as error:
        LOGGER.debug("request dropped: %s", error)
        writer.close()
        return
    back_writer.write(one_request(head))
    await asyncio.gather(_pipe(reader, back_writer), _pipe(back_reader, writer))


async def run(port: int, default: int, routes: dict[str, int]) -> None:
    server = await asyncio.start_server(
        lambda r, w: _serve(r, w, routes, default), HOST, port, limit=MAX_HEAD
    )
    LOGGER.info("gateway on http://%s:%s", HOST, port)
    async with server:
        await server.serve_forever()


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        sys.stderr.write(__doc__ or "")
        return 2
    routes = {prefix: int(port) for prefix, _, port in (entry.partition("=") for entry in argv[2:])}
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(run(int(argv[0]), int(argv[1]), routes))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
