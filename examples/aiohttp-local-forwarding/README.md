# Publish an aiohttp application

aiohttp owns a loopback HTTP listener. The rstream SDK creates and owns a
published tunnel that forwards to it.

Select a context that allows published HTTP tunnels using
[SDK setup](../../docs/000-getting-started.md). From the checkout root, run:

```sh
python -m pip install -e ".[api,examples]"
python examples/aiohttp-local-forwarding/main.py
```

Open the printed HTTPS URL and expect HTTP 200 with
`{"framework":"aiohttp","ok":true}`. Stop with Ctrl+C to close the tunnel and
the local server.
