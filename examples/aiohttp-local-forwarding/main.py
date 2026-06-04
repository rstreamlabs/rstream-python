from __future__ import annotations

import asyncio
import socket
from contextlib import closing, suppress

from aiohttp import web

import rstream


async def root(_request: web.Request) -> web.Response:
    return web.json_response({"framework": "aiohttp", "ok": True})


async def main() -> None:
    app = web.Application()
    app.router.add_get("/", root)
    runner = web.AppRunner(app)
    port = free_port()
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", port)
    await site.start()
    try:
        async with (
            rstream.Client.from_env() as client,
            await client.connect() as control,
        ):
            # aiohttp is intentionally demonstrated through local forwarding;
            # direct framework serving is covered by the ASGI and WSGI examples.
            tunnel = await control.create_tunnel(
                protocol="http",
                http_version="http/1.1",
                publish=True,
            )
            print("Forwarding address:", tunnel.forwarding_address)
            await tunnel.forward_to("127.0.0.1", port)
    finally:
        await runner.cleanup()


def free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def run() -> None:
    with suppress(KeyboardInterrupt):
        asyncio.run(main())


if __name__ == "__main__":
    run()
