# List and watch live tunnels

Use inventory when a service needs to find tunnel addresses or refresh its
view as tunnels change. This is the Engine API for a selected project or
direct Engine. It uses a separate HTTP connection from the agent that owns
a tunnel.

## List and watch from one client

Install the API extra and use a [context](../001-configuration.md) that can
list and watch tunnels visible to your application. On a managed project,
the credential needs the read-only tunnel resources permission and a tunnel
list scope for the demo tunnel. Include `id` if the scope restricts fields.
The Engine sends replacement snapshots when the projection omits `id`.

```sh
python -m pip install "rstreamlabs-rstream[api]"
```

Save this as `watch_tunnels.py`:

```python
import asyncio
from contextlib import suppress

import rstream


async def main() -> None:
    async with rstream.Client.from_env() as client:
        for entry in await client.list_tunnels():
            print(entry.properties.id, entry.status, flush=True)
        async with client.watch() as events:
            async for event in events:
                if event.type == "state.initial" and event.object is not None:
                    print("snapshot", event.object.get("tunnels", []), flush=True)
                else:
                    print(event.type, flush=True)


with suppress(KeyboardInterrupt):
    asyncio.run(main())
```

Run `python watch_tunnels.py`. While it is running, start and stop
a [sample tunnel](000-http-applications.md) in a second terminal
using the same project. Look for `tunnel.created` and `tunnel.deleted`
with the `id` field selected, or replacement snapshots otherwise.
The script closes the watch on Ctrl+C.

If the application needs a narrower set, use
`filters=rstream.TunnelFilters(labels={"role": "worker"})` for
`list_tunnels` and the same filter as `tunnels=filters` for `watch`.
Set that label on tunnel creation. To maintain a live view, replace it
at every `state.initial` and apply the subsequent create, update and
delete events. The watch can send a new snapshot on an existing
connection as well as after reconnecting.

Call `await client.list_clients(filters=...)` with a `rstream.ClientFilters`
instance to list runtime clients. Pass the same filter to `client.watch(clients=...)`
to watch client changes. A context needs permission and scope to see those
resources. Both list methods accept a `limit` for a bounded result.

The default transport is server-sent events. Install the `realtime` extra
and use `transport="websocket"` if the application requires WebSockets.
The SDK also supports [certificate-based inventory and watches](../001-configuration.md#engine-http-access-with-certificates)
on Engines configured for that access.
