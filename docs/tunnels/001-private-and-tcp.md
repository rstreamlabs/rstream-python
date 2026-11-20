# Connect to private and TCP services

Choose private access when callers can use a rstream SDK or CLI. Use
public TCP when an ordinary client must connect by hostname and port, and
the application protocol provides its own encryption and authentication.

## Dial a private HTTP service

Use a context permitted to create and dial private tunnels in the same
project or on the same Engine. On macOS or Linux, start a loopback service containing one file:

```sh
demo_dir=$(mktemp -d)
printf 'hello through Python\n' > "$demo_dir/index.html"
python -m http.server 8000 --bind 127.0.0.1 --directory "$demo_dir"
```

In another terminal, create a private tunnel with the CLI:

```sh
rstream forward 127.0.0.1:8000 --no-publish --name python-private-http
```

When the CLI reports that the tunnel is online, dial it from the checkout.
Install the SDK as in [Getting started](../000-getting-started.md#build-and-test-the-checkout).

```sh
python examples/private-dial/main.py python-private-http
```

Expect an HTTP 200 status and `hello through Python`. The caller opens the stream by name or ID, sends an HTTP
request and reads until EOF. The tunnel carries bytes and can carry another
protocol when both endpoints speak it. Keep the loopback service and tunnel
owner running until the request completes. Then stop both with Ctrl+C.
From the origin's terminal, remove the test directory with
`rm -r -- "$demo_dir"`.

To own the server side in Python, create a tunnel with `publish=False`
and `name="python-private-http"`. Use `await tunnel.accept()` for one
connection or iterate over the tunnel in a server loop. Wrap each accepted
stream in `async with` and keep requests bounded by the protocol's own
read and write deadlines. See [connection lifecycle](002-lifecycle.md).

## Publish a TCP service

Set `publish=True` and `protocol="tcp"` when creating the tunnel.
Leave `port` unset for an ephemeral port or supply a port already reserved
by the project. The SDK can accept those connections in-process or
`await tunnel.forward_to(host, port)` to an existing service.

For SSH, forward to the loopback SSH service and connect to the printed
host and port with `ssh -p PORT USER@HOST` after replacing the values.
Verify the host key and authenticate with your usual SSH credential.
[Published TCP](https://rstream.io/docs/tunnels/tcp-tunnels) explains
availability, reservations and access policy.
