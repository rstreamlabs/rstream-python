# Forward an existing HTTP server

Use this when the service already listens on a local port. Select a context
that allows published HTTP tunnels using [SDK setup](../../docs/000-getting-started.md).
From the checkout root, install the SDK and start a disposable origin.

```sh
python -m pip install -e ".[api]"
demo_dir=$(mktemp -d) &&
  printf 'Hello from the local server\n' > "$demo_dir/index.html" &&
  python -m http.server 8000 --bind 127.0.0.1 --directory "$demo_dir"
```

Keep the origin running. From the checkout root in a second terminal using
the same Python environment, run the forwarder.

```sh
python examples/forward-local-port/main.py 127.0.0.1 8000
```

Open the printed HTTPS URL. Expect HTTP 200 and `Hello from the local server`.
Stop the forwarder and origin with Ctrl+C, then remove the temporary directory.
