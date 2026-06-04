from __future__ import annotations

import asyncio
import sys

import rstream


async def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else "private-api"
    async with rstream.Client.from_env() as client, await client.dial(target) as stream:
        # Private tunnels are addressed by name or ID and return a raw
        # bidirectional byte stream.
        stream.write(b"ping")
        await stream.drain()
        print((await stream.read(1024)).decode(errors="replace"))


if __name__ == "__main__":
    asyncio.run(main())
