# Flask tunnel

Run this application's HTTP handler directly on accepted tunnel streams.
Use the [checkout environment and project setup](../../docs/000-getting-started.md#build-and-test-the-checkout).
From the repository root:

```sh
python examples/flask-tunnel/main.py
```

Open the printed forwarding address and expect JSON with `framework` set to `flask` and `ok` set to `true`. Stop with
Ctrl+C. The [HTTP applications guide](../../docs/tunnels/000-http-applications.md)
explains the `wsgi` adapter and when to forward an existing server.
