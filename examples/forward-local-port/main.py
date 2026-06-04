from __future__ import annotations

import asyncio
import sys
from contextlib import suppress

import rstream


async def main() -> None:
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    async with rstream.Client.from_env() as client, await client.connect() as control:
        # Open a published HTTP tunnel on the selected rstream project.
        tunnel = await control.create_tunnel(
            protocol="http",
            http_version="http/1.1",
            publish=True,
        )
        print("Forwarding address:", tunnel.forwarding_address)
        # Forward each incoming tunnel stream to an existing local TCP service.
        await tunnel.forward_to(host, port)


def run() -> None:
    with suppress(KeyboardInterrupt):
        asyncio.run(main())


if __name__ == "__main__":
    run()
