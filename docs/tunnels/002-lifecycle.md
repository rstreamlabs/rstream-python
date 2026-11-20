# Own the tunnel lifecycle

Give one service or worker ownership of its `Client` and control channel.
Create the tunnel as part of startup. Use an async context for the client,
the control channel and each accepted or dialed stream. When several
tunnels share one control channel, close an individual tunnel with
`await tunnel.close()` to keep the remaining tunnels running.

| Signal | Meaning | Application action |
| --- | --- | --- |
| `await control.done()` completes | The control channel has ended. | Stop admission and decide whether to reopen the channel. |
| A stream reaches EOF or raises an I/O error | The payload exchange has ended or failed. | Release that stream and its application resources. |
| The service is asked to stop | The application owns shutdown. | Cancel its supervisor, close its tunnels and drain or cancel application tasks. |

New accepts stop when a control heartbeat expires or the control connection
ends unexpectedly. Accepted streams and forwarding relays can continue on
their own connections. Explicit closure or Engine revocation can terminate
those connections. Direct ASGI and WSGI serving cancels its request
tasks when its serving loop ends. Forwarding relays can keep running
after an unexpected control loss while the application's event loop
remains alive. Use the stream's result to finish application-owned
requests and decide how long to drain them.

The application owns reconnection. When a serving task ends unexpectedly,
classify the error, close its old owners when their work is done and create
a new control channel and tunnel with bounded backoff. Surface configuration
or authorization errors. Keep the backoff cancellable and let clients retry
requests according to the application protocol.

If a managed HTTPS endpoint must remain the same, persist the stable
hostname and pass it on each creation. `await client.generate_stable_hostname()`
derives a project-scoped name for supported managed hosts. It returns
`None` for an Engine outside that model. See
[stable domains](https://rstream.io/docs/tunnels/stable-domains) for what
the domain identifies.
