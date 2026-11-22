from __future__ import annotations

import asyncio
import sys

import rstream


async def request(target: str) -> None:
    async with rstream.Client.from_env() as client, await client.dial(target) as stream:
        stream.write(b"GET / HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n")
        await stream.drain()
        while chunk := await stream.read(65536):
            sys.stdout.buffer.write(chunk)


async def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else "python-private-http"
    await asyncio.wait_for(request(target), timeout=15)


if __name__ == "__main__":
    asyncio.run(main())
