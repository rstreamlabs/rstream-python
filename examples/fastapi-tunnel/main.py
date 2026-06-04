from __future__ import annotations

import asyncio
from contextlib import suppress

from fastapi import FastAPI

import rstream

app = FastAPI()


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok"}


async def main() -> None:
    async with rstream.Client.from_env() as client, await client.connect() as control:
        # Client.from_env reads the same config file and environment variables
        # used by the rstream CLI and the other SDKs.
        tunnel = await control.create_tunnel(
            protocol="http",
            http_version="http/1.1",
            publish=True,
        )
        print("Forwarding address:", tunnel.forwarding_address)
        # The ASGI helper parses each accepted rstream stream and dispatches it
        # to FastAPI in-process. No loopback HTTP server is started.
        await rstream.asgi.serve(app, tunnel)


def run() -> None:
    with suppress(KeyboardInterrupt):
        asyncio.run(main())


if __name__ == "__main__":
    run()
