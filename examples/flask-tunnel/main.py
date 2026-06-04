from __future__ import annotations

import asyncio
from contextlib import suppress

from flask import Flask, jsonify

import rstream

app = Flask(__name__)


@app.get("/")
def root() -> object:
    return jsonify(framework="flask", ok=True)


async def main() -> None:
    async with (
        rstream.Client.from_env() as client,
        await client.connect() as control,
    ):
        # Client.from_env reads the same config file and environment variables
        # used by the rstream CLI and the other SDKs.
        tunnel = await control.create_tunnel(
            protocol="http",
            http_version="http/1.1",
            publish=True,
        )
        print("Forwarding address:", tunnel.forwarding_address)
        # The WSGI helper dispatches accepted rstream streams directly to Flask.
        await rstream.wsgi.serve(app, tunnel)


def run() -> None:
    with suppress(KeyboardInterrupt):
        asyncio.run(main())


if __name__ == "__main__":
    run()
